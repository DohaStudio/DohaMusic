"""Provider 결과를 Workspace Job 성공으로 확정하는 Completion Unit of Work."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
import logging
from pathlib import Path
import re
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError
from backend.models.workspace import (
    AssetVersion,
    Job,
    JobOutput,
    JobStatus,
    ModelUsage,
)
from backend.models.workspace.identifiers import generate_uuid
from backend.repositories.workspace import AssetRepository, JobRepository
from backend.services.workspace.artifact_ingestion_service import (
    ArtifactIngestionError,
    ArtifactIngestionRequest,
    ArtifactIngestionService,
    PreparedArtifactIngestion,
)
from backend.services.workspace.job_service import JobAggregate

logger = logging.getLogger(__name__)

MAX_OUTPUTS = 8
MAX_TEXT = 256
_UNSAFE_TEXT = re.compile(
    r"(?:[A-Za-z]:[\\/]|/(?:home|users?|var|tmp|opt|data|models?)/|"
    r"authorization|bearer\s+|api[_-]?key|credential|password|secret|token)",
    re.IGNORECASE,
)
_SAFE_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,127}\Z")
OUTPUT_CONTRACT: dict[str, dict[str, str]] = {
    "lyrics_generation": {"lyrics": "lyrics_text"},
    "music_generation": {"generated_audio": "audio"},
    "stem_separation": {
        "vocal_stem": "stem",
        "instrumental_stem": "stem",
    },
    "voice_conversion": {"converted_vocal": "audio"},
    "audio_analysis": {"analysis": "evaluation"},
    "mix": {"mix": "audio"},
    "export": {"export": "audio"},
}
STORAGE_DOMAIN_BY_JOB_TYPE = {
    "lyrics_generation": "lm",
    "music_generation": "audio",
    "stem_separation": "audio",
    "voice_conversion": "vocal",
    "audio_analysis": "audio",
    "mix": "music",
    "export": "music",
}


class ProviderResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class JobCompletionErrorCode(StrEnum):
    INVALID_RESULT = "INVALID_PROVIDER_RESULT"
    INVALID_STATE = "INVALID_JOB_COMPLETION_STATE"
    CANCELLED = "JOB_COMPLETION_CANCELLED"
    CONFLICT = "JOB_COMPLETION_CONFLICT"
    INGESTION_FAILED = "JOB_COMPLETION_INGESTION_FAILED"
    PERSISTENCE_FAILED = "JOB_COMPLETION_PERSISTENCE_FAILED"
    INTEGRITY_FAILED = "JOB_COMPLETION_INTEGRITY_FAILED"


_SAFE_MESSAGES = {
    JobCompletionErrorCode.INVALID_RESULT: "Provider completion result is invalid.",
    JobCompletionErrorCode.INVALID_STATE: "Workspace Job cannot be completed.",
    JobCompletionErrorCode.CANCELLED: "Workspace Job completion was cancelled.",
    JobCompletionErrorCode.CONFLICT: "Workspace Job completion conflicts with the existing result.",
    JobCompletionErrorCode.INGESTION_FAILED: "Workspace Job output ingestion failed.",
    JobCompletionErrorCode.PERSISTENCE_FAILED: "Workspace Job completion could not be persisted.",
    JobCompletionErrorCode.INTEGRITY_FAILED: "Workspace Job output integrity verification failed.",
}


class JobCompletionError(AppError):
    def __init__(self, code: JobCompletionErrorCode) -> None:
        status_code = (
            409
            if code
            in {
                JobCompletionErrorCode.INVALID_STATE,
                JobCompletionErrorCode.CANCELLED,
                JobCompletionErrorCode.CONFLICT,
            }
            else 422
            if code is JobCompletionErrorCode.INVALID_RESULT
            else 500
        )
        super().__init__(code.value, _SAFE_MESSAGES[code], status_code)
        self.completion_code = code


@dataclass(frozen=True, slots=True)
class ProviderOutput:
    output_order: int
    output_role: str
    temporary_path: Path
    artifact_kind: str
    target_asset_id: UUID | None = None
    target_asset_version_id: UUID | None = None
    parent_asset_version_id: UUID | None = None
    expected_media_type: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderResult:
    status: ProviderResultStatus
    provider_id: str
    capability: str
    provider_contract_version: str
    model_manifest_id: str
    model_id: str
    model_version: str
    license_status: str
    commercial_usage_status: str
    outputs: tuple[ProviderOutput, ...] = ()
    checkpoint_version: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    error_retryable: bool = False


@dataclass(frozen=True, slots=True)
class JobCompletionResult:
    aggregate: JobAggregate
    replayed: bool


@dataclass(frozen=True, slots=True)
class _PlannedOutput:
    request: ProviderOutput
    asset_version_id: UUID
    creates_version: bool


class JobCompletionService:
    """Filesystem 보상과 단일 DB transaction으로 Workspace 성공을 확정한다."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        ingestion_service: ArtifactIngestionService,
    ) -> None:
        self._session_factory = session_factory
        self._ingestion = ingestion_service

    def complete_job_with_provider_result(
        self,
        job_id: UUID,
        *,
        effective_owner_id: UUID,
        provider_result: ProviderResult,
        execution_claim_token: UUID | None = None,
    ) -> JobCompletionResult:
        result = _validate_provider_result(provider_result)
        job = self._load_job(job_id, effective_owner_id)
        self._validate_execution_identity(job, result, execution_claim_token)

        if result.status is ProviderResultStatus.FAILED:
            return self._complete_provider_failure(
                job_id,
                effective_owner_id=effective_owner_id,
                result=result,
                execution_claim_token=execution_claim_token,
            )

        try:
            plans = self._plan_outputs(job, result, effective_owner_id)
        except JobCompletionError:
            self._discard_outputs(result.outputs)
            self._mark_completion_failed(job_id, effective_owner_id)
            raise
        prepared: list[tuple[_PlannedOutput, PreparedArtifactIngestion]] = []
        try:
            for plan in plans:
                request = ArtifactIngestionRequest(
                    asset_version_id=plan.asset_version_id,
                    artifact_kind=plan.request.artifact_kind,
                    producer_type="provider",
                    storage_domain=STORAGE_DOMAIN_BY_JOB_TYPE[job.job_type],
                    temporary_path=plan.request.temporary_path,
                    producer_id=result.provider_id,
                    run_id=str(job.job_id),
                    expected_media_type=plan.request.expected_media_type,
                )
                prepared.append((plan, self._ingestion.prepare(request)))
        except (ArtifactIngestionError, OSError):
            self._compensate_and_discard(prepared, result.outputs)
            self._mark_completion_failed(job_id, effective_owner_id)
            raise JobCompletionError(JobCompletionErrorCode.INGESTION_FAILED) from None

        cancelled = False
        replayed = False
        aggregate: JobAggregate | None = None
        try:
            with self._session_factory() as session, session.begin():
                repository = JobRepository(session)
                current = repository.get_job_for_owner(job_id, effective_owner_id)
                if current is None:
                    raise JobCompletionError(JobCompletionErrorCode.INVALID_STATE)
                self._validate_execution_identity(
                    current, result, execution_claim_token
                )
                if current.status is JobStatus.SUCCEEDED:
                    if not self._matches_existing(
                        session, repository, current, result, prepared
                    ):
                        raise JobCompletionError(JobCompletionErrorCode.CONFLICT)
                    replayed = True
                    aggregate = _load_aggregate(repository, current)
                elif current.status is not JobStatus.RUNNING:
                    raise JobCompletionError(JobCompletionErrorCode.INVALID_STATE)
                elif current.cancel_requested_at is not None:
                    repository.update_job_status(
                        current, JobStatus.CANCELLED, completed_at=datetime.now(UTC)
                    )
                    cancelled = True
                    aggregate = _load_aggregate(repository, current)
                else:
                    self._persist_outputs(
                        session, repository, current, result, prepared
                    )
                    session.refresh(current, attribute_names=["cancel_requested_at"])
                    if current.cancel_requested_at is not None:
                        raise JobCompletionError(JobCompletionErrorCode.CANCELLED)
                    current.progress_percent = 100
                    repository.update_job_status(
                        current, JobStatus.SUCCEEDED, completed_at=datetime.now(UTC)
                    )
                    aggregate = _load_aggregate(repository, current)
        except JobCompletionError as error:
            self._compensate_and_discard(prepared, result.outputs)
            if error.completion_code is JobCompletionErrorCode.CANCELLED:
                self._mark_cancelled(job_id, effective_owner_id)
            if error.completion_code not in {
                JobCompletionErrorCode.CONFLICT,
                JobCompletionErrorCode.INVALID_STATE,
                JobCompletionErrorCode.CANCELLED,
            }:
                self._mark_completion_failed(job_id, effective_owner_id)
            raise
        except (ArtifactIngestionError, IntegrityError, OSError, RuntimeError):
            self._compensate_and_discard(prepared, result.outputs)
            self._mark_completion_failed(job_id, effective_owner_id)
            raise JobCompletionError(
                JobCompletionErrorCode.PERSISTENCE_FAILED
            ) from None

        if cancelled:
            self._compensate_and_discard(prepared, result.outputs)
            raise JobCompletionError(JobCompletionErrorCode.CANCELLED)
        if replayed:
            self._compensate_and_discard(prepared, result.outputs)
        else:
            self._finalize(prepared)
        if aggregate is None:
            raise JobCompletionError(JobCompletionErrorCode.PERSISTENCE_FAILED)
        return JobCompletionResult(aggregate, replayed=replayed)

    def _load_job(self, job_id: UUID, owner_id: UUID) -> Job:
        with self._session_factory() as session:
            job = JobRepository(session).get_job_for_owner(job_id, owner_id)
            if job is None:
                raise JobCompletionError(JobCompletionErrorCode.INVALID_STATE)
            return job

    def _validate_execution_identity(
        self,
        job: Job,
        result: ProviderResult,
        claim_token: UUID | None,
    ) -> None:
        if job.status not in {JobStatus.RUNNING, JobStatus.SUCCEEDED}:
            raise JobCompletionError(JobCompletionErrorCode.INVALID_STATE)
        if job.claim_token != claim_token:
            raise JobCompletionError(JobCompletionErrorCode.INVALID_STATE)
        if result.capability != job.job_type:
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
        if result.provider_contract_version != job.api_contract_version:
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
        if job.provider_id is not None and result.provider_id != job.provider_id:
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
        if (
            job.model_manifest_id is not None
            and result.model_manifest_id != job.model_manifest_id
        ):
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)

    def _plan_outputs(
        self, job: Job, result: ProviderResult, owner_id: UUID
    ) -> tuple[_PlannedOutput, ...]:
        contract = OUTPUT_CONTRACT[job.job_type]
        if len(result.outputs) != len(contract):
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
        roles = [item.output_role for item in result.outputs]
        orders = [item.output_order for item in result.outputs]
        if set(roles) != set(contract) or len(set(roles)) != len(roles):
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
        if sorted(orders) != list(range(len(result.outputs))):
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)

        plans: list[_PlannedOutput] = []
        with self._session_factory() as session:
            assets = AssetRepository(session)
            for output in sorted(result.outputs, key=lambda item: item.output_order):
                if output.artifact_kind != contract[output.output_role]:
                    raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                creates_version = output.target_asset_id is not None
                if creates_version == (output.target_asset_version_id is not None):
                    raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                if creates_version:
                    asset = assets.get_asset(output.target_asset_id)
                    if (
                        asset is None
                        or asset.owner_id != owner_id
                        or (
                            asset.workspace_id is not None
                            and asset.workspace_id != job.workspace_id
                        )
                    ):
                        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                    if output.parent_asset_version_id is not None:
                        parent = assets.get_asset_version(
                            output.parent_asset_version_id
                        )
                        if parent is None or parent.asset_id != asset.asset_id:
                            raise JobCompletionError(
                                JobCompletionErrorCode.INVALID_RESULT
                            )
                    version_id = generate_uuid()
                else:
                    if output.parent_asset_version_id is not None:
                        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                    version = assets.get_asset_version(output.target_asset_version_id)
                    if version is None:
                        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                    asset = assets.get_asset(version.asset_id)
                    if (
                        asset is None
                        or asset.owner_id != owner_id
                        or (
                            asset.workspace_id is not None
                            and asset.workspace_id != job.workspace_id
                        )
                    ):
                        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                    version_id = version.asset_version_id
                plans.append(_PlannedOutput(output, version_id, creates_version))
        if len({item.asset_version_id for item in plans}) != len(plans):
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
        return tuple(plans)

    def _persist_outputs(
        self,
        session: Session,
        repository: JobRepository,
        job: Job,
        result: ProviderResult,
        prepared: Sequence[tuple[_PlannedOutput, PreparedArtifactIngestion]],
    ) -> None:
        assets = AssetRepository(session)
        for plan, payload in prepared:
            if plan.creates_version:
                asset_id = plan.request.target_asset_id
                asset = assets.get_asset(asset_id)
                if asset is None:
                    raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
                latest = assets.get_latest_asset_version(asset.asset_id)
                version = assets.add_asset_version(
                    AssetVersion(
                        asset_version_id=plan.asset_version_id,
                        asset_id=asset.asset_id,
                        version_number=1
                        if latest is None
                        else latest.version_number + 1,
                        version_origin="provider_generated",
                        parent_asset_version_id=plan.request.parent_asset_version_id,
                        provider_id=result.provider_id,
                        model_manifest_id=result.model_manifest_id,
                        settings_snapshot=dict(job.settings_snapshot),
                        created_by=job.requested_by,
                    )
                )
            else:
                version = assets.get_asset_version(plan.asset_version_id)
                if version is None:
                    raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
            artifact = self._ingestion.register_prepared(session, payload)
            self._ingestion.verify_registered(session, artifact, payload)
            repository.add_job_output(
                JobOutput(
                    job_id=job.job_id,
                    output_order=plan.request.output_order,
                    output_role=plan.request.output_role,
                    artifact_id=artifact.artifact_id,
                )
            )
            repository.add_model_usage(
                ModelUsage(
                    job_id=job.job_id,
                    asset_version_id=version.asset_version_id,
                    provider_id=result.provider_id,
                    model_manifest_id=result.model_manifest_id,
                    model_id=result.model_id,
                    model_version=result.model_version,
                    checkpoint_version=result.checkpoint_version,
                    api_contract_version=result.provider_contract_version,
                    license_status=result.license_status,
                    commercial_usage_status=result.commercial_usage_status,
                )
            )
        if len(repository.list_job_outputs(job.job_id, limit=MAX_OUTPUTS + 1)) != len(
            prepared
        ):
            raise JobCompletionError(JobCompletionErrorCode.INTEGRITY_FAILED)

    def _matches_existing(
        self,
        session: Session,
        repository: JobRepository,
        job: Job,
        result: ProviderResult,
        prepared: Sequence[tuple[_PlannedOutput, PreparedArtifactIngestion]],
    ) -> bool:
        outputs = repository.list_job_outputs(job.job_id, limit=MAX_OUTPUTS + 1)
        usages = repository.list_model_usages(job.job_id, limit=MAX_OUTPUTS + 1)
        if len(outputs) != len(prepared) or len(usages) != len(prepared):
            return False
        usage_by_version = {item.asset_version_id: item for item in usages}
        assets = AssetRepository(session)
        for existing, (plan, incoming) in zip(outputs, prepared, strict=True):
            artifact = assets.get_artifact(existing.artifact_id)
            if artifact is None or existing.output_order != plan.request.output_order:
                return False
            if existing.output_role != plan.request.output_role:
                return False
            version = assets.get_asset_version(artifact.asset_version_id)
            if version is None:
                return False
            if artifact.storage_location is None:
                return False
            target_matches = (
                (
                    version.asset_id == plan.request.target_asset_id
                    and version.parent_asset_version_id
                    == plan.request.parent_asset_version_id
                    and version.version_origin == "provider_generated"
                    and version.provider_id == result.provider_id
                    and version.model_manifest_id == result.model_manifest_id
                    and version.settings_snapshot == job.settings_snapshot
                )
                if plan.creates_version
                else (version.asset_version_id == plan.request.target_asset_version_id)
            )
            if not target_matches or (
                artifact.artifact_kind != incoming.request.artifact_kind
                or artifact.media_type != incoming.published.media.media_type
                or artifact.size_bytes != incoming.published.size_bytes
                or artifact.artifact_checksum != incoming.published.checksum
            ):
                return False
            usage = usage_by_version.get(version.asset_version_id)
            if usage is None or not _usage_matches(usage, result):
                return False
        return True

    def _complete_provider_failure(
        self,
        job_id: UUID,
        *,
        effective_owner_id: UUID,
        result: ProviderResult,
        execution_claim_token: UUID | None,
    ) -> JobCompletionResult:
        with self._session_factory() as session, session.begin():
            repository = JobRepository(session)
            job = repository.get_job_for_owner(job_id, effective_owner_id)
            if job is None:
                raise JobCompletionError(JobCompletionErrorCode.INVALID_STATE)
            self._validate_execution_identity(job, result, execution_claim_token)
            if job.status is JobStatus.SUCCEEDED:
                raise JobCompletionError(JobCompletionErrorCode.CONFLICT)
            if job.cancel_requested_at is not None:
                repository.update_job_status(
                    job, JobStatus.CANCELLED, completed_at=datetime.now(UTC)
                )
            else:
                job.error_code = result.error_code or "PROVIDER_EXECUTION_FAILED"
                job.error_message = result.error_message or "Provider execution failed."
                job.error_retryable = result.error_retryable
                repository.update_job_status(
                    job, JobStatus.FAILED, completed_at=datetime.now(UTC)
                )
            aggregate = _load_aggregate(repository, job)
        return JobCompletionResult(aggregate, replayed=False)

    def _mark_completion_failed(self, job_id: UUID, owner_id: UUID) -> None:
        try:
            with self._session_factory() as session, session.begin():
                repository = JobRepository(session)
                job = repository.get_job_for_owner(job_id, owner_id)
                if job is None or job.status is not JobStatus.RUNNING:
                    return
                if job.cancel_requested_at is not None:
                    repository.update_job_status(
                        job, JobStatus.CANCELLED, completed_at=datetime.now(UTC)
                    )
                    return
                job.error_code = "JOB_COMPLETION_FAILED"
                job.error_message = "Workspace Job completion failed."
                job.error_retryable = True
                repository.update_job_status(
                    job, JobStatus.FAILED, completed_at=datetime.now(UTC)
                )
        except Exception:
            logger.exception(
                "Workspace Job completion failure state could not be persisted.",
                extra={"job_id": str(job_id)},
            )

    def _mark_cancelled(self, job_id: UUID, owner_id: UUID) -> None:
        try:
            with self._session_factory() as session, session.begin():
                repository = JobRepository(session)
                job = repository.get_job_for_owner(job_id, owner_id)
                if (
                    job is None
                    or job.status is not JobStatus.RUNNING
                    or job.cancel_requested_at is None
                ):
                    return
                repository.update_job_status(
                    job, JobStatus.CANCELLED, completed_at=datetime.now(UTC)
                )
        except Exception:
            logger.exception(
                "Workspace Job cancellation state could not be persisted.",
                extra={"job_id": str(job_id)},
            )

    def _compensate_and_discard(
        self,
        prepared: Sequence[tuple[_PlannedOutput, PreparedArtifactIngestion]],
        outputs: Sequence[ProviderOutput],
    ) -> None:
        for _, payload in reversed(prepared):
            self._ingestion.compensate_prepared(
                payload, reason_code="JOB_COMPLETION_ROLLBACK"
            )
        self._discard_outputs(outputs)

    def _discard_outputs(self, outputs: Sequence[ProviderOutput]) -> None:
        for output in outputs:
            if not self._ingestion.discard_staging_path(output.temporary_path):
                logger.warning(
                    "Workspace Job staging cleanup requires reconciliation.",
                    extra={
                        "output_order": output.output_order,
                        "output_role": output.output_role,
                    },
                )

    def _finalize(
        self,
        prepared: Sequence[tuple[_PlannedOutput, PreparedArtifactIngestion]],
    ) -> None:
        for _, payload in prepared:
            if not self._ingestion.finalize_prepared(payload):
                logger.warning(
                    "Workspace Job staging cleanup requires reconciliation.",
                    extra={"artifact_id": str(payload.artifact_id)},
                )


def _validate_provider_result(result: ProviderResult) -> ProviderResult:
    if not isinstance(result, ProviderResult) or not isinstance(
        result.status, ProviderResultStatus
    ):
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    text_fields = (
        result.provider_id,
        result.capability,
        result.provider_contract_version,
        result.model_manifest_id,
        result.model_id,
        result.model_version,
        result.license_status,
        result.commercial_usage_status,
    )
    normalized_text = tuple(_required_safe_text(value) for value in text_fields)
    normalized = replace(
        result,
        provider_id=normalized_text[0],
        capability=normalized_text[1],
        provider_contract_version=normalized_text[2],
        model_manifest_id=normalized_text[3],
        model_id=normalized_text[4],
        model_version=normalized_text[5],
        license_status=normalized_text[6],
        commercial_usage_status=normalized_text[7],
        checkpoint_version=_optional_text(result.checkpoint_version),
        error_code=_optional_error_code(result.error_code),
        error_message=_optional_text(result.error_message),
    )
    if normalized.status is ProviderResultStatus.FAILED:
        if normalized.outputs:
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    elif not normalized.outputs or len(normalized.outputs) > MAX_OUTPUTS:
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    for output in normalized.outputs:
        if (
            not isinstance(output, ProviderOutput)
            or type(output.output_order) is not int
            or output.output_order < 0
            or type(output.output_role) is not str
            or not output.output_role.strip()
            or not isinstance(output.temporary_path, Path)
            or type(output.artifact_kind) is not str
            or not output.artifact_kind.strip()
        ):
            raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    return normalized


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip() or len(value) > MAX_TEXT:
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    normalized = value.strip()
    if _UNSAFE_TEXT.search(normalized) or any(ord(char) < 32 for char in normalized):
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    return normalized


def _optional_error_code(value: str | None) -> str | None:
    if value is None:
        return None
    if type(value) is not str or _SAFE_ERROR_CODE.fullmatch(value) is None:
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    return value


def _required_safe_text(value: object) -> str:
    if type(value) is not str or not value.strip() or len(value) > MAX_TEXT:
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    normalized = value.strip()
    if _UNSAFE_TEXT.search(normalized) or any(ord(char) < 32 for char in normalized):
        raise JobCompletionError(JobCompletionErrorCode.INVALID_RESULT)
    return normalized


def _usage_matches(usage: ModelUsage, result: ProviderResult) -> bool:
    return (
        usage.provider_id == result.provider_id
        and usage.model_manifest_id == result.model_manifest_id
        and usage.model_id == result.model_id
        and usage.model_version == result.model_version
        and usage.checkpoint_version == result.checkpoint_version
        and usage.api_contract_version == result.provider_contract_version
        and usage.license_status == result.license_status
        and usage.commercial_usage_status == result.commercial_usage_status
    )


def _load_aggregate(repository: JobRepository, job: Job) -> JobAggregate:
    return JobAggregate(
        job=job,
        inputs=tuple(repository.list_job_inputs(job.job_id)),
        outputs=tuple(repository.list_job_outputs(job.job_id)),
        model_usages=tuple(repository.list_model_usages(job.job_id)),
    )
