"""DohaVocal wire result를 Workspace ingestion 후보로 승격하는 trust gate."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy.orm import Session

from backend.contracts.vocal_jobs import (
    VOCAL_JOB_INPUT_ADAPTER,
    VOCAL_JOB_INPUT_SETTINGS_KEY,
    VOCAL_JOB_OUTPUT_ROLES,
    VocalGenerationJobInput,
)
from backend.core.exceptions import ApplicationValidationError
from backend.models.workspace import JobStatus
from backend.providers.vocal import VocalProviderResultCandidate
from backend.repositories.workspace import (
    AssetRepository,
    CompositionRepository,
    JobRepository,
    ProviderJobRepository,
)
from backend.storage.trusted_payload import TrustedPayloadReference

_OPAQUE_ID = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?")
_URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
_UNSAFE_VALUE = re.compile(
    r"(?:[A-Za-z]:[\\/]|/(?:home|users?|var|tmp|opt|data|models?)/|"
    r"authorization|bearer\s+|api[_-]?key|credential|password|secret|token)",
    re.IGNORECASE,
)


class ProviderResultContractErrorReason(StrEnum):
    BINDING_MISSING = "binding_missing"
    WORKSPACE_JOB_MISMATCH = "workspace_job_mismatch"
    INVALID_JOB_STATE = "invalid_job_state"
    PROVIDER_IDENTITY_MISMATCH = "provider_identity_mismatch"
    PROVIDER_JOB_IDENTITY_MISMATCH = "provider_job_identity_mismatch"
    OUTPUT_ROLE_MISMATCH = "output_role_mismatch"
    ARTIFACT_KIND_MISMATCH = "artifact_kind_mismatch"
    MANIFEST_MISMATCH = "manifest_mismatch"
    SETTINGS_MISMATCH = "settings_mismatch"
    LINEAGE_MISMATCH = "lineage_mismatch"
    PROCESSING_CHAIN_MISMATCH = "processing_chain_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    INVALID_CANDIDATE = "invalid_candidate"


class ProviderResultContractError(ApplicationValidationError):
    """Provider 세부 정보나 경로를 노출하지 않는 fail-closed 오류."""

    def __init__(self, reason: ProviderResultContractErrorReason) -> None:
        super().__init__("Provider result ingestion 계약이 유효하지 않습니다.")
        self.reason = reason


class IngestionDecisionReason(StrEnum):
    PAYLOAD_ABSENT = "payload_absent"


@dataclass(frozen=True, slots=True)
class TrustedProviderResultCandidate:
    """Provider identity와 Workspace 계약을 검증한 내부 metadata snapshot."""

    workspace_job_id: UUID
    provider_job_binding_id: UUID
    provider_id: str
    provider_job_id: str
    output_role: str
    provider_artifact_id: str
    provider_output_asset_version_id: str
    source_asset_version_id: UUID
    parent_asset_version_id: UUID
    processing_chain_id: UUID
    model_manifest_id: str
    settings_snapshot: dict[str, object]
    artifact_kind: str
    media_type: str
    payload_present: bool
    metadata_checksum: str
    checksum_scope: str
    created_at: datetime
    provider_source_artifact_id: str | None
    provider_parent_artifact_id: str | None
    processing_types: tuple[str, ...]
    analysis_result: dict[str, object] | None
    payload_reference: TrustedPayloadReference | None = None

    @property
    def idempotency_key(self) -> tuple[UUID, str, str]:
        return (
            self.provider_job_binding_id,
            self.output_role,
            self.provider_artifact_id,
        )

    def require_payload_reference(self) -> TrustedPayloadReference:
        """metadata-only 결과의 payload-backed Completion 변환을 차단한다."""

        if not self.payload_present or self.payload_reference is None:
            raise ProviderResultNotIngestibleError(IngestionDecisionReason.PAYLOAD_ABSENT)
        return self.payload_reference


@dataclass(frozen=True, slots=True)
class ProviderResultIngestionDecision:
    candidate: TrustedProviderResultCandidate
    reason: IngestionDecisionReason
    eligible_for_binary_ingestion: bool
    eligible_for_structured_ingestion: bool


class ProviderResultNotIngestibleError(RuntimeError):
    def __init__(self, reason: IngestionDecisionReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


class ProviderResultIngestionService:
    """호출자 transaction에서 mutation 없이 ingestion eligibility를 판정한다."""

    def validate_candidate_for_owner(
        self,
        session: Session,
        *,
        effective_owner_id: UUID,
        workspace_job_id: UUID,
        provider_job_binding_id: UUID,
        output_role: str,
        wire_candidate: VocalProviderResultCandidate,
    ) -> ProviderResultIngestionDecision:
        job_repository = JobRepository(session)
        job = job_repository.get_job_for_owner(workspace_job_id, effective_owner_id)
        if job is None:
            _reject(ProviderResultContractErrorReason.WORKSPACE_JOB_MISMATCH)
        if job.status is not JobStatus.RUNNING:
            _reject(ProviderResultContractErrorReason.INVALID_JOB_STATE)

        binding = ProviderJobRepository(session).get_by_id(provider_job_binding_id)
        if binding is None:
            _reject(ProviderResultContractErrorReason.BINDING_MISSING)
        if binding.workspace_job_id != workspace_job_id:
            _reject(ProviderResultContractErrorReason.WORKSPACE_JOB_MISMATCH)

        self._validate_identity(job, binding, wire_candidate)
        expected_role = VOCAL_JOB_OUTPUT_ROLES.get(job.job_type)
        if output_role != expected_role:
            _reject(ProviderResultContractErrorReason.OUTPUT_ROLE_MISMATCH)
        expected_kind = "analysis" if job.job_type == "vocal_analysis" else "audio"
        if wire_candidate.artifact_kind != expected_kind:
            _reject(ProviderResultContractErrorReason.ARTIFACT_KIND_MISMATCH)

        expected_settings = deepcopy(dict(job.settings_snapshot))
        raw_job_input = expected_settings.pop(VOCAL_JOB_INPUT_SETTINGS_KEY, None)
        if raw_job_input is None:
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        try:
            job_input = VOCAL_JOB_INPUT_ADAPTER.validate_python(raw_job_input)
        except ValueError:
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        if wire_candidate.lineage.settings_snapshot != expected_settings:
            _reject(ProviderResultContractErrorReason.SETTINGS_MISMATCH)

        source_id, parent_id, chain_id = self._validate_lineage(
            session,
            job_repository=job_repository,
            workspace_job_id=workspace_job_id,
            effective_owner_id=effective_owner_id,
            job_input=job_input,
            candidate=wire_candidate,
        )
        self._validate_descriptor(wire_candidate, job.job_type)

        trusted = TrustedProviderResultCandidate(
            workspace_job_id=workspace_job_id,
            provider_job_binding_id=provider_job_binding_id,
            provider_id=binding.provider_id,
            provider_job_id=binding.provider_job_id,
            output_role=output_role,
            provider_artifact_id=wire_candidate.artifact_id,
            provider_output_asset_version_id=wire_candidate.output_asset_version_id,
            source_asset_version_id=source_id,
            parent_asset_version_id=parent_id,
            processing_chain_id=chain_id,
            model_manifest_id=wire_candidate.lineage.model_manifest_id,
            settings_snapshot=deepcopy(wire_candidate.lineage.settings_snapshot),
            artifact_kind=wire_candidate.artifact_kind,
            media_type=wire_candidate.media_type,
            payload_present=False,
            metadata_checksum=wire_candidate.artifact_checksum,
            checksum_scope=wire_candidate.checksum_scope,
            created_at=wire_candidate.lineage.created_at,
            provider_source_artifact_id=wire_candidate.lineage.source_artifact_id,
            provider_parent_artifact_id=wire_candidate.lineage.parent_artifact_id,
            processing_types=wire_candidate.lineage.processing_types,
            analysis_result=deepcopy(wire_candidate.analysis_result),
        )
        return ProviderResultIngestionDecision(
            candidate=trusted,
            reason=IngestionDecisionReason.PAYLOAD_ABSENT,
            eligible_for_binary_ingestion=False,
            eligible_for_structured_ingestion=False,
        )

    @staticmethod
    def _validate_identity(job, binding, candidate) -> None:
        if (
            job.provider_id != binding.provider_id
            or candidate.producer_id != binding.provider_id
            or candidate.lineage.provider_id != binding.provider_id
        ):
            _reject(ProviderResultContractErrorReason.PROVIDER_IDENTITY_MISMATCH)
        if (
            candidate.run_id != binding.provider_job_id
            or candidate.lineage.job_id != binding.provider_job_id
        ):
            _reject(ProviderResultContractErrorReason.PROVIDER_JOB_IDENTITY_MISMATCH)
        if (
            job.model_manifest_id is None
            or candidate.lineage.model_manifest_id != job.model_manifest_id
        ):
            _reject(ProviderResultContractErrorReason.MANIFEST_MISMATCH)

    @staticmethod
    def _validate_lineage(
        session: Session,
        *,
        job_repository: JobRepository,
        workspace_job_id: UUID,
        effective_owner_id: UUID,
        job_input,
        candidate: VocalProviderResultCandidate,
    ) -> tuple[UUID, UUID, UUID]:
        assets = AssetRepository(session)
        inputs = job_repository.list_job_inputs(workspace_job_id)
        resolved_input_versions: list[UUID] = []
        input_artifact_ids: set[str] = set()
        for item in inputs:
            if item.asset_version_id is not None:
                resolved_input_versions.append(item.asset_version_id)
            else:
                artifact = assets.get_artifact(item.artifact_id)
                if artifact is None:
                    _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
                resolved_input_versions.append(artifact.asset_version_id)
                input_artifact_ids.add(str(artifact.artifact_id))

        if isinstance(job_input, VocalGenerationJobInput):
            if not resolved_input_versions:
                _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
            expected_source = resolved_input_versions[0]
        else:
            expected_source = job_input.source_asset_version_id
            if expected_source not in resolved_input_versions:
                _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        expected_parent = job_input.parent_asset_version_id or expected_source
        source_id = _uuid(candidate.lineage.source_asset_version_id)
        parent_id = _uuid(candidate.lineage.parent_asset_version_id)
        if source_id != expected_source or parent_id != expected_parent:
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        _validate_parent_lineage(assets, source_id, parent_id)

        if candidate.lineage.source_artifact_id is not None and (
            candidate.lineage.source_artifact_id not in input_artifact_ids
        ):
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        if candidate.lineage.parent_artifact_id is not None and (
            candidate.lineage.parent_artifact_id not in input_artifact_ids
        ):
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)

        chain_id = _uuid(candidate.lineage.processing_chain_id)
        if job_input.processing_chain_id is not None and (
            chain_id != job_input.processing_chain_id
        ):
            _reject(ProviderResultContractErrorReason.PROCESSING_CHAIN_MISMATCH)
        chain = CompositionRepository(session).get_processing_chain(chain_id)
        if chain is None or chain.created_by != effective_owner_id:
            _reject(ProviderResultContractErrorReason.PROCESSING_CHAIN_MISMATCH)
        return source_id, parent_id, chain_id

    @staticmethod
    def _validate_descriptor(candidate: VocalProviderResultCandidate, job_type: str) -> None:
        _safe_identifier(candidate.artifact_id)
        _safe_identifier(candidate.output_asset_version_id)
        _safe_text(candidate.media_type)
        if (
            candidate.payload_present is not False
            or candidate.checksum_algorithm != "sha256"
            or candidate.checksum_scope != "metadata_descriptor"
            or candidate.lineage.checksum_scope != "metadata_descriptor"
            or candidate.artifact_checksum != candidate.lineage.checksum
        ):
            _reject(ProviderResultContractErrorReason.CHECKSUM_MISMATCH)
        if job_type != "vocal_analysis" and candidate.analysis_result is not None:
            _reject(ProviderResultContractErrorReason.INVALID_CANDIDATE)


def _validate_parent_lineage(repository: AssetRepository, source_id: UUID, parent_id: UUID) -> None:
    source = repository.get_asset_version(source_id)
    parent = repository.get_asset_version(parent_id)
    if source is None or parent is None or source.asset_id != parent.asset_id:
        _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
    visited: set[UUID] = set()
    current = parent
    while current.asset_version_id != source_id:
        if current.asset_version_id in visited or current.parent_asset_version_id is None:
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        visited.add(current.asset_version_id)
        ancestor = repository.get_asset_version(current.parent_asset_version_id)
        if ancestor is None or ancestor.asset_id != source.asset_id:
            _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)
        current = ancestor


def _uuid(value: object) -> UUID:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        _reject(ProviderResultContractErrorReason.LINEAGE_MISMATCH)


def _safe_text(value: object) -> str:
    if not isinstance(value, str):
        _reject(ProviderResultContractErrorReason.INVALID_CANDIDATE)
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > 256
        or _UNSAFE_VALUE.search(normalized) is not None
        or _URI_SCHEME.match(normalized) is not None
    ):
        _reject(ProviderResultContractErrorReason.INVALID_CANDIDATE)
    return normalized


def _safe_identifier(value: object) -> str:
    normalized = _safe_text(value)
    if _OPAQUE_ID.fullmatch(normalized) is None:
        _reject(ProviderResultContractErrorReason.INVALID_CANDIDATE)
    return normalized


def _reject(reason: ProviderResultContractErrorReason):
    raise ProviderResultContractError(reason)
