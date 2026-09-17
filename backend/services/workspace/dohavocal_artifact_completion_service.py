"""DohaVocal verified staging을 Workspace Artifact authority로 원자 승격한다."""

from __future__ import annotations

import re
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import NoReturn, Protocol
from uuid import UUID

from sqlalchemy.orm import Session, sessionmaker

from backend.contracts.vocal_jobs import (
    VOCAL_JOB_INPUT_SETTINGS_KEY,
    VOCAL_JOB_OUTPUT_ROLES,
    VOCAL_JOB_TYPES,
)
from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorRecord,
    PayloadLocatorStatus,
    parse_locator_id,
)
from backend.models.workspace import (
    Asset,
    AssetType,
    AssetVersion,
    Job,
    JobOutput,
    JobStatus,
    ModelUsage,
    MusicProject,
    ProjectAsset,
    ProviderJobBinding,
    Workspace,
)
from backend.models.workspace.identifiers import generate_uuid
from backend.repositories.workspace import (
    ArtifactStorageRepository,
    AssetRepository,
    CompositionRepository,
    JobRepository,
    PayloadLocatorRepository,
    ProviderJobRepository,
    WorkspaceRepository,
)
from backend.services.workspace.artifact_ingestion_service import (
    ArtifactIngestionError,
    ArtifactIngestionService,
    PreparedArtifactIngestion,
    VerifiedArtifactStreamFacts,
    VerifiedStreamArtifactIngestionRequest,
)
from backend.services.workspace.payload_staging_service import staged_payload_from_record
from backend.services.workspace.provider_result_ingestion_service import (
    TrustedProviderResultCandidate,
)
from backend.storage.artifact_resolver import SUPPORTED_LOCATOR_VERSION, SUPPORTED_STORAGE_BACKEND
from backend.storage.verified_payload_staging import (
    VerifiedPayloadStagingPort,
)

_CANONICAL_OUTPUT_ROLES = {
    "vocal_generation": "generated_vocal",
    "voice_conversion": "converted_vocal",
    "vocal_correction": "corrected_vocal",
    "vocal_analysis": "vocal_analysis",
}
_UNSAFE_TEXT = re.compile(
    r"(?:[A-Za-z]:[\\/]|/(?:home|users?|var|tmp|opt|data|models?)/|"
    r"authorization|bearer\s+|api[_-]?key|credential|password|secret|token)",
    re.IGNORECASE,
)


class VocalCompletionAuthorityMode(StrEnum):
    COMMIT = "commit"
    REPLAY = "replay"


class DohaVocalArtifactCompletionErrorCode(StrEnum):
    INVALID_REQUEST = "DOHAVOCAL_COMPLETION_INVALID_REQUEST"
    INVALID_AUTHORITY = "DOHAVOCAL_COMPLETION_INVALID_AUTHORITY"
    RIGHTS_DENIED = "DOHAVOCAL_COMPLETION_RIGHTS_DENIED"
    STALE_CLAIM = "DOHAVOCAL_COMPLETION_STALE_CLAIM"
    CANCELLED = "DOHAVOCAL_COMPLETION_CANCELLED"
    CONFLICT = "DOHAVOCAL_COMPLETION_CONFLICT"
    INGESTION_FAILED = "DOHAVOCAL_COMPLETION_INGESTION_FAILED"
    PERSISTENCE_FAILED = "DOHAVOCAL_COMPLETION_PERSISTENCE_FAILED"


class DohaVocalArtifactCompletionError(RuntimeError):
    def __init__(self, code: DohaVocalArtifactCompletionErrorCode) -> None:
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class VocalCompletionModelFacts:
    model_id: str
    model_version: str
    license_status: str
    commercial_usage_status: str
    checkpoint_version: str | None = None


@dataclass(frozen=True, slots=True)
class DohaVocalArtifactCompletionRequest:
    candidate: TrustedProviderResultCandidate
    payload_locator_id: str
    claimed_by: str
    execution_claim_token: UUID
    trusted_principal: object
    model: VocalCompletionModelFacts


@dataclass(frozen=True, slots=True)
class DohaVocalArtifactCompletionResult:
    job_id: UUID
    artifact_id: UUID
    asset_id: UUID
    asset_version_id: UUID
    output_role: str
    replayed: bool


class VocalCompletionRightsPort(Protocol):
    """Session-aware current rights authority supplied by the application boundary."""

    def require_current(
        self,
        session: Session,
        *,
        trusted_principal: object,
        owner_id: UUID,
        workspace_id: UUID,
        project_id: UUID,
        job: Job,
        candidate: TrustedProviderResultCandidate,
        mode: VocalCompletionAuthorityMode,
    ) -> None: ...


@dataclass(frozen=True, slots=True)
class VocalCompletionAuthoritySnapshot:
    job: Job
    workspace: Workspace
    project: MusicProject
    binding: ProviderJobBinding
    locator: PayloadLocatorRecord
    source_version: AssetVersion
    source_asset: Asset


class VocalCompletionAuthorityPort(Protocol):
    def require_current(
        self,
        session: Session,
        request: DohaVocalArtifactCompletionRequest,
        *,
        mode: VocalCompletionAuthorityMode,
    ) -> VocalCompletionAuthoritySnapshot: ...


class SqlAlchemyVocalCompletionAuthorityPort:
    """DB scope/binding checks plus an injected current-rights decision."""

    def __init__(
        self,
        rights: VocalCompletionRightsPort,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._rights = rights
        self._clock = clock or (lambda: datetime.now(UTC))

    def require_current(
        self,
        session: Session,
        request: DohaVocalArtifactCompletionRequest,
        *,
        mode: VocalCompletionAuthorityMode,
    ) -> VocalCompletionAuthoritySnapshot:
        candidate = request.candidate
        invalid_authority = (
            DohaVocalArtifactCompletionErrorCode.CONFLICT
            if mode is VocalCompletionAuthorityMode.REPLAY
            else DohaVocalArtifactCompletionErrorCode.INVALID_AUTHORITY
        )
        job = JobRepository(session).get_job(candidate.workspace_job_id)
        if job is None or job.job_type not in VOCAL_JOB_TYPES:
            _fail(invalid_authority)
        workspace = WorkspaceRepository(session).get_workspace(job.workspace_id)
        project = WorkspaceRepository(session).get_project(job.project_id)
        if (
            workspace is None
            or project is None
            or project.workspace_id != workspace.workspace_id
            or job.workspace_id != workspace.workspace_id
            or job.requested_by != workspace.owner_id
        ):
            _fail(invalid_authority)

        binding = ProviderJobRepository(session).get_by_id(candidate.provider_job_binding_id)
        if (
            binding is None
            or binding.workspace_job_id != job.job_id
            or binding.provider_id != candidate.provider_id
            or binding.provider_job_id != candidate.provider_job_id
            or job.provider_id != candidate.provider_id
            or job.model_manifest_id != candidate.model_manifest_id
            or job.api_contract_version != "0.2.0"
            or candidate.output_role != VOCAL_JOB_OUTPUT_ROLES[job.job_type]
            or len(candidate.payloads) != 1
            or candidate.artifact_kind
            != ("analysis" if job.job_type == "vocal_analysis" else "audio")
        ):
            _fail(invalid_authority)

        expected_settings = deepcopy(dict(job.settings_snapshot))
        if expected_settings.pop(VOCAL_JOB_INPUT_SETTINGS_KEY, None) is None:
            _fail(invalid_authority)
        if candidate.settings_snapshot != expected_settings:
            _fail(invalid_authority)

        locator_uuid = _parse_locator(request.payload_locator_id)
        locator = PayloadLocatorRepository(session).get_by_locator_uuid(locator_uuid)
        payload = candidate.payloads[0]
        if (
            locator is None
            or locator.issue.workspace_job_id != job.job_id
            or locator.issue.provider_job_binding_id != binding.provider_job_binding_id
            or locator.issue.payload_ordinal != 0
            or locator.issue.provider_artifact_id != payload.provider_artifact_id
            or locator.issue.role != payload.role
            or locator.issue.source_kind != payload.source_kind
            or locator.issue.source_id != payload.source_id
            or locator.issue.expected_checksum_algorithm != payload.checksum_algorithm
            or locator.issue.expected_payload_checksum != payload.payload_checksum
            or locator.issue.expected_size_bytes != payload.expected_size_bytes
            or locator.issue.expected_media_type != payload.expected_media_type
            or locator.issue.artifact_kind != candidate.artifact_kind
        ):
            _fail(invalid_authority)

        source_version = AssetRepository(session).get_asset_version(
            candidate.source_asset_version_id
        )
        parent_version = AssetRepository(session).get_asset_version(
            candidate.parent_asset_version_id
        )
        source_asset = (
            AssetRepository(session).get_asset(source_version.asset_id, include_deleted=True)
            if source_version is not None
            else None
        )
        if (
            source_version is None
            or parent_version is None
            or source_asset is None
            or source_asset.owner_id != workspace.owner_id
            or source_asset.workspace_id not in {None, workspace.workspace_id}
            or parent_version.asset_id != source_asset.asset_id
            or not _job_references_version(session, job.job_id, source_version.asset_version_id)
        ):
            _fail(invalid_authority)
        if job.job_type != "vocal_generation" and source_asset.asset_type is not AssetType.VOCAL:
            _fail(invalid_authority)
        chain = CompositionRepository(session).get_processing_chain(candidate.processing_chain_id)
        if chain is None or chain.created_by != workspace.owner_id:
            _fail(invalid_authority)

        now = self._clock()
        if mode is VocalCompletionAuthorityMode.COMMIT:
            if (
                workspace.lifecycle_status != "active"
                or project.lifecycle_status != "active"
                or source_asset.deleted_at is not None
                or source_asset.lifecycle_status != "active"
                or WorkspaceRepository(session).find_project_asset(
                    project.project_id, source_asset.asset_id
                )
                is None
            ):
                _fail(DohaVocalArtifactCompletionErrorCode.INVALID_AUTHORITY)
            if job.cancel_requested_at is not None:
                _fail(DohaVocalArtifactCompletionErrorCode.CANCELLED)
            if (
                job.status is not JobStatus.RUNNING
                or job.claimed_by != request.claimed_by
                or job.claim_token != request.execution_claim_token
                or (job.lease_expires_at is not None and _utc(job.lease_expires_at) <= now)
            ):
                _fail(DohaVocalArtifactCompletionErrorCode.STALE_CLAIM)
            if (
                locator.staging_status is not PayloadLocatorStatus.VERIFIED_STAGED
                or locator.revoked
                or (
                    locator.issue.locator_expires_at is not None
                    and now >= locator.issue.locator_expires_at
                )
                or locator.actual_checksum_algorithm != locator.issue.expected_checksum_algorithm
                or locator.actual_payload_checksum != locator.issue.expected_payload_checksum
                or locator.actual_size_bytes != locator.issue.expected_size_bytes
                or locator.actual_media_type != locator.issue.expected_media_type
            ):
                _fail(DohaVocalArtifactCompletionErrorCode.INVALID_AUTHORITY)
        elif mode is VocalCompletionAuthorityMode.REPLAY:
            if (
                job.status is not JobStatus.SUCCEEDED
                or locator.staging_status
                not in {
                    PayloadLocatorStatus.INGESTED,
                    PayloadLocatorStatus.CLEANUP_PENDING,
                    PayloadLocatorStatus.CLEANED,
                }
                or locator.ingested_artifact_id is None
            ):
                _fail(DohaVocalArtifactCompletionErrorCode.CONFLICT)
        else:  # pragma: no cover - enum boundary
            _fail(DohaVocalArtifactCompletionErrorCode.INVALID_REQUEST)

        try:
            self._rights.require_current(
                session,
                trusted_principal=request.trusted_principal,
                owner_id=workspace.owner_id,
                workspace_id=workspace.workspace_id,
                project_id=project.project_id,
                job=job,
                candidate=candidate,
                mode=mode,
            )
        except DohaVocalArtifactCompletionError:
            raise
        except Exception:
            _fail(DohaVocalArtifactCompletionErrorCode.RIGHTS_DENIED)
        return VocalCompletionAuthoritySnapshot(
            job, workspace, project, binding, locator, source_version, source_asset
        )


@dataclass(frozen=True, slots=True)
class _CompletionPlan:
    asset_version_id: UUID


class DohaVocalArtifactCompletionService:
    """Owns verified stream I/O compensation and the final atomic DB transaction."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        staging: VerifiedPayloadStagingPort,
        ingestion: ArtifactIngestionService,
        authority: VocalCompletionAuthorityPort,
    ) -> None:
        self._session_factory = session_factory
        self._staging = staging
        self._ingestion = ingestion
        self._authority = authority

    def complete(
        self, request: DohaVocalArtifactCompletionRequest
    ) -> DohaVocalArtifactCompletionResult:
        normalized = _validate_request(request)
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).get_job(normalized.candidate.workspace_job_id)
            mode = (
                VocalCompletionAuthorityMode.REPLAY
                if job is not None and job.status is JobStatus.SUCCEEDED
                else VocalCompletionAuthorityMode.COMMIT
            )
            snapshot = self._authority.require_current(session, normalized, mode=mode)
            if mode is VocalCompletionAuthorityMode.REPLAY:
                return self._replay(session, normalized, snapshot)
            plan = _CompletionPlan(asset_version_id=generate_uuid())
            staged_payload = staged_payload_from_record(snapshot.locator)

        artifact_kind = "evaluation" if snapshot.job.job_type == "vocal_analysis" else "audio"
        stream_request = VerifiedStreamArtifactIngestionRequest(
            asset_version_id=(
                snapshot.source_version.asset_version_id
                if snapshot.job.job_type == "vocal_analysis"
                else plan.asset_version_id
            ),
            artifact_kind=artifact_kind,
            producer_type="provider",
            storage_domain="vocal",
            producer_id=snapshot.binding.provider_id,
            run_id=str(snapshot.job.job_id),
        )
        facts = VerifiedArtifactStreamFacts(
            checksum_algorithm=staged_payload.checksum_algorithm,
            payload_checksum=staged_payload.payload_checksum,
            size_bytes=staged_payload.size_bytes,
            media_type=staged_payload.media_type,
        )
        try:
            with self._staging.open_verified(staged_payload) as stream:
                prepared = self._ingestion.prepare_verified_stream(
                    stream_request,
                    stream,
                    expected_facts=facts,
                )
        except Exception:
            raise DohaVocalArtifactCompletionError(
                DohaVocalArtifactCompletionErrorCode.INGESTION_FAILED
            ) from None

        try:
            result = self._commit(normalized, plan, prepared)
        except (DohaVocalArtifactCompletionError, ArtifactIngestionError, PayloadLocatorError):
            self._compensate(prepared)
            replay = self._replay_fresh(normalized)
            if replay is not None:
                return replay
            raise
        except Exception:
            self._compensate(prepared)
            replay = self._replay_fresh(normalized)
            if replay is not None:
                return replay
            raise DohaVocalArtifactCompletionError(
                DohaVocalArtifactCompletionErrorCode.PERSISTENCE_FAILED
            ) from None
        if result.artifact_id != prepared.artifact_id:
            self._compensate(prepared)
            return result
        self._ingestion.finalize_prepared(prepared)
        return result

    def _commit(
        self,
        request: DohaVocalArtifactCompletionRequest,
        plan: _CompletionPlan,
        prepared: PreparedArtifactIngestion,
    ) -> DohaVocalArtifactCompletionResult:
        with self._session_factory() as session, session.begin():
            job = JobRepository(session).get_job(request.candidate.workspace_job_id)
            if job is not None and job.status is JobStatus.SUCCEEDED:
                snapshot = self._authority.require_current(
                    session, request, mode=VocalCompletionAuthorityMode.REPLAY
                )
                return self._replay(session, request, snapshot)
            snapshot = self._authority.require_current(
                session, request, mode=VocalCompletionAuthorityMode.COMMIT
            )
            version = self._create_target(session, request, snapshot, plan)
            if prepared.request.asset_version_id != version.asset_version_id:
                _fail(DohaVocalArtifactCompletionErrorCode.CONFLICT)
            artifact = self._ingestion.register_prepared(session, prepared)
            self._ingestion.verify_registered(session, artifact, prepared)
            output_role = _CANONICAL_OUTPUT_ROLES[snapshot.job.job_type]
            JobRepository(session).add_job_output(
                JobOutput(
                    job_id=snapshot.job.job_id,
                    output_order=0,
                    output_role=output_role,
                    artifact_id=artifact.artifact_id,
                )
            )
            model = request.model
            JobRepository(session).add_model_usage(
                ModelUsage(
                    job_id=snapshot.job.job_id,
                    asset_version_id=version.asset_version_id,
                    provider_id=snapshot.binding.provider_id,
                    model_manifest_id=request.candidate.model_manifest_id,
                    model_id=model.model_id,
                    model_version=model.model_version,
                    checkpoint_version=model.checkpoint_version,
                    api_contract_version=snapshot.job.api_contract_version,
                    license_status=model.license_status,
                    commercial_usage_status=model.commercial_usage_status,
                )
            )
            ingested_at = datetime.now(UTC)
            PayloadLocatorRepository(session).compare_and_set(
                snapshot.locator.locator_uuid,
                expected_revision=snapshot.locator.lifecycle_revision,
                expected_status=PayloadLocatorStatus.VERIFIED_STAGED,
                require_not_revoked=True,
                values={
                    "staging_status": PayloadLocatorStatus.INGESTED.value,
                    "ingested_artifact_id": artifact.artifact_id,
                    "ingested_at": ingested_at,
                },
            )
            completed = JobRepository(session).finish_owned_claim(
                snapshot.job.job_id,
                claimed_by=request.claimed_by,
                claim_token=request.execution_claim_token,
                status=JobStatus.SUCCEEDED,
                now=ingested_at,
            )
            if completed is None:
                _fail(DohaVocalArtifactCompletionErrorCode.STALE_CLAIM)
            completed.progress_percent = Decimal(100)
            session.flush()
            return DohaVocalArtifactCompletionResult(
                job_id=completed.job_id,
                artifact_id=artifact.artifact_id,
                asset_id=version.asset_id,
                asset_version_id=version.asset_version_id,
                output_role=output_role,
                replayed=False,
            )

    @staticmethod
    def _create_target(
        session: Session,
        request: DohaVocalArtifactCompletionRequest,
        snapshot: VocalCompletionAuthoritySnapshot,
        plan: _CompletionPlan,
    ) -> AssetVersion:
        job = snapshot.job
        if job.job_type == "vocal_analysis":
            return snapshot.source_version
        assets = AssetRepository(session)
        if job.job_type == "vocal_generation":
            asset = assets.add_asset(
                Asset(
                    workspace_id=snapshot.workspace.workspace_id,
                    owner_id=snapshot.workspace.owner_id,
                    asset_type=AssetType.VOCAL,
                    selected_asset_version_id=None,
                    lifecycle_status="active",
                )
            )
            workspaces = WorkspaceRepository(session)
            workspaces.add_project_asset(
                ProjectAsset(
                    project_id=snapshot.project.project_id,
                    asset_id=asset.asset_id,
                    role="vocal",
                    display_order=workspaces.next_project_asset_display_order(
                        snapshot.project.project_id
                    ),
                )
            )
            version_number = 1
            parent_id = None
        else:
            asset = snapshot.source_asset
            latest = assets.get_latest_asset_version(asset.asset_id)
            version_number = 1 if latest is None else latest.version_number + 1
            parent_id = request.candidate.parent_asset_version_id
        version = AssetVersion(
            asset_version_id=plan.asset_version_id,
            asset_id=asset.asset_id,
            version_number=version_number,
            version_origin="dohavocal_provider",
            parent_asset_version_id=parent_id,
            processing_chain_id=request.candidate.processing_chain_id,
            provider_id=snapshot.binding.provider_id,
            model_manifest_id=job.model_manifest_id,
            settings_snapshot=deepcopy(request.candidate.settings_snapshot),
            created_by=snapshot.workspace.owner_id,
        )
        return assets.add_asset_version(version)

    def _replay_fresh(
        self, request: DohaVocalArtifactCompletionRequest
    ) -> DohaVocalArtifactCompletionResult | None:
        try:
            with self._session_factory() as session, session.begin():
                job = JobRepository(session).get_job(request.candidate.workspace_job_id)
                if job is None or job.status is not JobStatus.SUCCEEDED:
                    return None
                snapshot = self._authority.require_current(
                    session, request, mode=VocalCompletionAuthorityMode.REPLAY
                )
                return self._replay(session, request, snapshot)
        except Exception:
            return None

    @staticmethod
    def _replay(
        session: Session,
        request: DohaVocalArtifactCompletionRequest,
        snapshot: VocalCompletionAuthoritySnapshot,
    ) -> DohaVocalArtifactCompletionResult:
        outputs = JobRepository(session).list_job_outputs(snapshot.job.job_id, limit=2)
        usages = JobRepository(session).list_model_usages(snapshot.job.job_id, limit=2)
        expected_role = _CANONICAL_OUTPUT_ROLES[snapshot.job.job_type]
        output = outputs[0] if len(outputs) == 1 else None
        artifact = (
            AssetRepository(session).get_artifact(output.artifact_id)
            if output is not None and output.artifact_id is not None
            else None
        )
        version = (
            AssetRepository(session).get_asset_version(artifact.asset_version_id)
            if artifact is not None
            else None
        )
        asset = (
            AssetRepository(session).get_asset(version.asset_id, include_deleted=True)
            if version is not None
            else None
        )
        location = (
            ArtifactStorageRepository(session).get_storage_location(artifact.artifact_id)
            if artifact is not None
            else None
        )
        usage = usages[0] if len(usages) == 1 else None
        model = request.model
        if (
            output is None
            or output.output_order != 0
            or output.output_role != expected_role
            or artifact is None
            or snapshot.locator.ingested_artifact_id != artifact.artifact_id
            or artifact.artifact_kind
            != ("evaluation" if snapshot.job.job_type == "vocal_analysis" else "audio")
            or artifact.checksum_algorithm != "sha256"
            or artifact.artifact_checksum != snapshot.locator.actual_payload_checksum
            or artifact.size_bytes != snapshot.locator.actual_size_bytes
            or artifact.media_type != snapshot.locator.actual_media_type
            or artifact.producer_type != "provider"
            or artifact.producer_id != snapshot.binding.provider_id
            or artifact.run_id != str(snapshot.job.job_id)
            or artifact.retention_status != "active"
            or version is None
            or asset is None
            or asset.owner_id != snapshot.workspace.owner_id
            or asset.workspace_id not in {None, snapshot.workspace.workspace_id}
            or location is None
            or location.storage_backend != SUPPORTED_STORAGE_BACKEND
            or location.storage_domain != "vocal"
            or location.locator_version != SUPPORTED_LOCATOR_VERSION
            or usage is None
            or usage.asset_version_id != version.asset_version_id
            or usage.provider_id != snapshot.binding.provider_id
            or usage.model_manifest_id != request.candidate.model_manifest_id
            or usage.api_contract_version != snapshot.job.api_contract_version
            or usage.model_id != model.model_id
            or usage.model_version != model.model_version
            or usage.checkpoint_version != model.checkpoint_version
            or usage.license_status != model.license_status
            or usage.commercial_usage_status != model.commercial_usage_status
        ):
            _fail(DohaVocalArtifactCompletionErrorCode.CONFLICT)
        if snapshot.job.job_type == "vocal_generation":
            membership = WorkspaceRepository(session).find_project_asset(
                snapshot.project.project_id, asset.asset_id, include_deleted=True
            )
            if (
                asset.asset_type is not AssetType.VOCAL
                or version.version_number != 1
                or version.parent_asset_version_id is not None
                or membership is None
                or membership.role != "vocal"
                or version.processing_chain_id != request.candidate.processing_chain_id
                or version.settings_snapshot != request.candidate.settings_snapshot
                or version.provider_id != snapshot.binding.provider_id
                or version.model_manifest_id != request.candidate.model_manifest_id
            ):
                _fail(DohaVocalArtifactCompletionErrorCode.CONFLICT)
        elif snapshot.job.job_type in {"voice_conversion", "vocal_correction"}:
            if (
                asset.asset_id != snapshot.source_asset.asset_id
                or version.asset_version_id == snapshot.source_version.asset_version_id
                or version.parent_asset_version_id != request.candidate.parent_asset_version_id
                or version.processing_chain_id != request.candidate.processing_chain_id
                or version.settings_snapshot != request.candidate.settings_snapshot
                or version.provider_id != snapshot.binding.provider_id
                or version.model_manifest_id != request.candidate.model_manifest_id
            ):
                _fail(DohaVocalArtifactCompletionErrorCode.CONFLICT)
        elif version.asset_version_id != snapshot.source_version.asset_version_id:
            _fail(DohaVocalArtifactCompletionErrorCode.CONFLICT)
        return DohaVocalArtifactCompletionResult(
            job_id=snapshot.job.job_id,
            artifact_id=artifact.artifact_id,
            asset_id=asset.asset_id,
            asset_version_id=version.asset_version_id,
            output_role=expected_role,
            replayed=True,
        )

    def _compensate(self, prepared: PreparedArtifactIngestion) -> None:
        self._ingestion.compensate_prepared(
            prepared,
            reason_code=DohaVocalArtifactCompletionErrorCode.PERSISTENCE_FAILED.value,
        )


def _validate_request(
    request: DohaVocalArtifactCompletionRequest,
) -> DohaVocalArtifactCompletionRequest:
    if (
        not isinstance(request, DohaVocalArtifactCompletionRequest)
        or not isinstance(request.candidate, TrustedProviderResultCandidate)
        or not request.candidate.payload_present
        or len(request.candidate.payloads) != 1
        or type(request.execution_claim_token) is not UUID
    ):
        _fail(DohaVocalArtifactCompletionErrorCode.INVALID_REQUEST)
    model = request.model
    if not isinstance(model, VocalCompletionModelFacts):
        _fail(DohaVocalArtifactCompletionErrorCode.INVALID_REQUEST)
    normalized_model = VocalCompletionModelFacts(
        model_id=_safe_text(model.model_id),
        model_version=_safe_text(model.model_version),
        checkpoint_version=_safe_optional_text(model.checkpoint_version),
        license_status=_safe_text(model.license_status),
        commercial_usage_status=_safe_text(model.commercial_usage_status),
    )
    return DohaVocalArtifactCompletionRequest(
        candidate=request.candidate,
        payload_locator_id=request.payload_locator_id,
        claimed_by=_safe_text(request.claimed_by),
        execution_claim_token=request.execution_claim_token,
        trusted_principal=request.trusted_principal,
        model=normalized_model,
    )


def _job_references_version(session: Session, job_id: UUID, version_id: UUID) -> bool:
    for item in JobRepository(session).list_job_inputs(job_id):
        if item.asset_version_id == version_id:
            return True
        if item.artifact_id is not None:
            artifact = AssetRepository(session).get_artifact(item.artifact_id)
            if artifact is not None and artifact.asset_version_id == version_id:
                return True
    return False


def _parse_locator(value: object) -> UUID:
    try:
        return parse_locator_id(value)
    except PayloadLocatorError:
        _fail(DohaVocalArtifactCompletionErrorCode.INVALID_REQUEST)


def _safe_text(value: object) -> str:
    if (
        type(value) is not str
        or not value.strip()
        or len(value.strip()) > 256
        or _UNSAFE_TEXT.search(value.strip()) is not None
    ):
        _fail(DohaVocalArtifactCompletionErrorCode.INVALID_REQUEST)
    return value.strip()


def _safe_optional_text(value: object) -> str | None:
    return None if value is None else _safe_text(value)


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _fail(code: DohaVocalArtifactCompletionErrorCode) -> NoReturn:
    raise DohaVocalArtifactCompletionError(code)
