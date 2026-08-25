"""DohaVocal Runtime 0.1.0을 위한 strict consumer DTO."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DOHAVOCAL_PROVIDER_ID = "dohavocal"
DOHAVOCAL_CONTRACT_VERSION = "0.1.0"
DOHAVOCAL_PAYLOAD_CONTRACT_VERSION = "0.2.0"
VocalContractVersion = Literal["0.1.0", "0.2.0"]
DOHAVOCAL_OPERATIONS = (
    "GetCapabilities",
    "CreateJob",
    "GetJobStatus",
    "CancelJob",
    "RetryJob",
    "GetResult",
    "GetModelManifest",
    "Health",
    "Readiness",
)
DOHAVOCAL_PAYLOAD_OPERATIONS = (*DOHAVOCAL_OPERATIONS, "GetPayloadContent")
_OPAQUE_PAYLOAD_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")
_URI_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")


class StrictFrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VocalCapability(StrEnum):
    VOCAL_GENERATION = "vocal_generation"
    VOICE_CONVERSION = "voice_conversion"
    VOCAL_CORRECTION = "vocal_correction"
    VOCAL_ANALYSIS = "vocal_analysis"


class VocalJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class VocalCorrectionType(StrEnum):
    PITCH = "pitch_correction"
    TIMING = "timing_correction"
    NOISE_REDUCTION = "noise_reduction"
    BREATH_CLEANUP = "breath_cleanup"
    SILENCE_CLEANUP = "silence_cleanup"
    NATURAL_TUNE = "natural_tune"
    STRONG_AUTOTUNE = "strong_autotune"
    NORMALIZATION = "normalization"
    DE_ESSER = "de_esser"
    EQ = "eq"
    COMPRESSION = "compression"


class VocalAnalysisType(StrEnum):
    PITCH = "pitch"
    TIMING = "timing"
    PRONUNCIATION = "pronunciation"
    AUDIO_QUALITY = "audio_quality"
    SIMILARITY = "similarity"


class VocalGenerationInput(StrictFrozenModel):
    job_type: Literal[VocalCapability.VOCAL_GENERATION]
    lyrics_reference: str
    melody_reference: str
    timing_reference: str | None = None
    voice_reference: str | None = None
    processing_chain_id: str | None = None


class VoiceConversionInput(StrictFrozenModel):
    job_type: Literal[VocalCapability.VOICE_CONVERSION]
    source_asset_version_id: str
    parent_asset_version_id: str | None = None
    voice_reference_artifact_id: str
    source_entity_type: Literal["recording_take", "ai_generated_vocal"]
    reference_entity_type: Literal["voice_enrollment_sample"]
    training_dataset_id: None = None
    processing_chain_id: str | None = None


class VocalCorrectionInput(StrictFrozenModel):
    job_type: Literal[VocalCapability.VOCAL_CORRECTION]
    source_asset_version_id: str
    parent_asset_version_id: str | None = None
    correction_types: tuple[VocalCorrectionType, ...] = Field(min_length=1)
    processing_chain_id: str | None = None


class VocalAnalysisInput(StrictFrozenModel):
    job_type: Literal[VocalCapability.VOCAL_ANALYSIS]
    source_asset_version_id: str
    parent_asset_version_id: str | None = None
    analysis_types: tuple[VocalAnalysisType, ...] = Field(min_length=1)
    processing_chain_id: str | None = None


VocalJobInput = Annotated[
    VocalGenerationInput
    | VoiceConversionInput
    | VocalCorrectionInput
    | VocalAnalysisInput,
    Field(discriminator="job_type"),
]


class VocalCreateJobRequest(StrictFrozenModel):
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID] = DOHAVOCAL_PROVIDER_ID
    capability: VocalCapability
    api_contract_version: VocalContractVersion = DOHAVOCAL_CONTRACT_VERSION
    idempotency_key: str = Field(min_length=1, max_length=200)
    project_id: str
    input_asset_version_ids: tuple[str, ...] = ()
    input_artifact_ids: tuple[str, ...] = ()
    model_manifest_id: str
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)
    requested_by: str
    composition_snapshot_id: str | None = None
    job_input: VocalJobInput

    @field_validator("settings_snapshot", mode="before")
    @classmethod
    def detach_settings(cls, value: Any) -> Any:
        return deepcopy(value)

    @model_validator(mode="after")
    def validate_boundary(self) -> VocalCreateJobRequest:
        if self.capability != self.job_input.job_type:
            raise ValueError("capability과 job_input.job_type이 일치해야 합니다.")
        _reject_sensitive_or_path_values(self.model_dump(mode="python"))
        return self


class VocalHealthProbe(StrictFrozenModel):
    status: Literal["ok"]
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]


class VocalReadinessProbe(StrictFrozenModel):
    status: Literal["ready"]
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]


class VocalPayloadAcquisitionCapability(StrictFrozenModel):
    supported: Literal[True]
    source_kinds: tuple[Literal["provider_subresource"], ...]
    operation: Literal["GetPayloadContent"]

    @model_validator(mode="after")
    def require_exact_source_surface(self) -> VocalPayloadAcquisitionCapability:
        if self.source_kinds != ("provider_subresource",):
            raise ValueError("unsupported DohaVocal payload source kind surface")
        return self


class VocalCapabilities(StrictFrozenModel):
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]
    api_contract_version: VocalContractVersion
    capabilities: tuple[VocalCapability, ...]
    supported_operations: tuple[str, ...]
    payload_acquisition: VocalPayloadAcquisitionCapability | None = None

    @model_validator(mode="after")
    def require_complete_surface(self) -> VocalCapabilities:
        if self.capabilities != tuple(VocalCapability):
            raise ValueError("DohaVocal capability surface가 지원 기준과 다릅니다.")
        expected_operations = (
            DOHAVOCAL_OPERATIONS
            if self.api_contract_version == DOHAVOCAL_CONTRACT_VERSION
            else DOHAVOCAL_PAYLOAD_OPERATIONS
        )
        if tuple(self.supported_operations) != expected_operations:
            raise ValueError("DohaVocal operation surface가 지원 기준과 다릅니다.")
        if self.api_contract_version == DOHAVOCAL_CONTRACT_VERSION:
            if self.payload_acquisition is not None:
                raise ValueError("0.1.0 must not advertise payload acquisition")
        elif self.payload_acquisition is None:
            raise ValueError("0.2.0 must advertise payload acquisition")
        return self


class VocalErrorDetail(StrictFrozenModel):
    error_code: str
    message: str
    retryable: bool
    stage: str
    details_id: str


class VocalErrorEnvelope(StrictFrozenModel):
    error: VocalErrorDetail


class BaseVocalJob(StrictFrozenModel):
    job_id: str
    job_type: VocalCapability
    status: VocalJobStatus
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]
    api_contract_version: VocalContractVersion
    progress_percent: int = Field(ge=0, le=100)
    input_asset_version_ids: tuple[str, ...]
    input_artifact_ids: tuple[str, ...]
    output_asset_version_ids: tuple[str, ...] = ()
    output_artifact_ids: tuple[str, ...] = ()
    composition_snapshot_id: str | None = None
    settings_snapshot: dict[str, Any]
    model_manifest_id: str
    retry_of_job_id: str | None = None
    error: VocalErrorDetail | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator("settings_snapshot", mode="before")
    @classmethod
    def detach_settings(cls, value: Any) -> Any:
        return deepcopy(value)

    @model_validator(mode="after")
    def validate_terminal_contract(self) -> BaseVocalJob:
        if self.status is VocalJobStatus.FAILED and self.error is None:
            raise ValueError("failed Job에는 구조화된 error가 필요합니다.")
        if self.status is VocalJobStatus.SUCCEEDED and (
            not self.output_asset_version_ids or not self.output_artifact_ids
        ):
            raise ValueError("succeeded Job에는 output ID가 필요합니다.")
        if (
            self.status
            in {
                VocalJobStatus.SUCCEEDED,
                VocalJobStatus.FAILED,
                VocalJobStatus.CANCELLED,
            }
            and self.completed_at is None
        ):
            raise ValueError("terminal Job에는 completed_at이 필요합니다.")
        return self


class VocalGenerationJob(BaseVocalJob):
    job_type: Literal[VocalCapability.VOCAL_GENERATION]


class VoiceConversionJob(BaseVocalJob):
    job_type: Literal[VocalCapability.VOICE_CONVERSION]


class VocalCorrectionJob(BaseVocalJob):
    job_type: Literal[VocalCapability.VOCAL_CORRECTION]


class VocalAnalysisJob(BaseVocalJob):
    job_type: Literal[VocalCapability.VOCAL_ANALYSIS]


AnyVocalJob = Annotated[
    VocalGenerationJob | VoiceConversionJob | VocalCorrectionJob | VocalAnalysisJob,
    Field(discriminator="job_type"),
]


class VocalArtifactLineage(StrictFrozenModel):
    source_asset_version_id: str
    parent_asset_version_id: str
    processing_chain_id: str
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]
    model_manifest_id: str
    settings_snapshot: dict[str, Any]
    processing_types: tuple[str, ...]
    created_at: datetime
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    checksum_scope: Literal["metadata_descriptor"]
    source_artifact_id: str | None = None
    parent_artifact_id: str | None = None
    job_id: str

    @field_validator("settings_snapshot", mode="before")
    @classmethod
    def detach_settings(cls, value: Any) -> Any:
        return deepcopy(value)


class VocalProviderResultCandidate(StrictFrozenModel):
    """DohaMusic AssetVersion으로 아직 commit되지 않은 Provider metadata 후보."""

    artifact_id: str
    artifact_kind: Literal["audio", "analysis"]
    media_type: str
    size_bytes: int = Field(ge=0)
    checksum_algorithm: Literal["sha256"]
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    checksum_scope: Literal["metadata_descriptor"]
    payload_present: Literal[False]
    producer_type: Literal["provider"]
    producer_id: Literal[DOHAVOCAL_PROVIDER_ID]
    run_id: str
    retention_status: Literal["candidate"]
    output_asset_version_id: str
    lineage: VocalArtifactLineage
    analysis_result: dict[str, Any] | None = None

    @field_validator("analysis_result", mode="before")
    @classmethod
    def detach_analysis(cls, value: Any) -> Any:
        return deepcopy(value)


class VocalPayloadSource(StrictFrozenModel):
    kind: Literal["provider_subresource"]
    source_id: str = Field(min_length=1, max_length=200)

    @field_validator("source_id")
    @classmethod
    def require_opaque_source_id(cls, value: str) -> str:
        if (
            not value.isascii()
            or _OPAQUE_PAYLOAD_ID.fullmatch(value) is None
            or ".." in value
            or _URI_SCHEME.search(value) is not None
        ):
            raise ValueError("payload source_id must be a bounded opaque identifier")
        return value


VocalPayloadRole = Literal[
    "generated_vocal_candidate",
    "converted_vocal_candidate",
    "corrected_vocal_candidate",
    "vocal_analysis_result",
]


class VocalProviderPayloadEntry(StrictFrozenModel):
    provider_artifact_id: str = Field(min_length=1, max_length=200)
    role: VocalPayloadRole
    source: VocalPayloadSource
    checksum_algorithm: Literal["sha256"]
    payload_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected_size_bytes: int = Field(gt=0)
    expected_media_type: Literal["audio/wav", "audio/flac", "application/json"]
    available_until: datetime | None

    @field_validator("provider_artifact_id")
    @classmethod
    def require_opaque_artifact_id(cls, value: str) -> str:
        if (
            not value.isascii()
            or _OPAQUE_PAYLOAD_ID.fullmatch(value) is None
            or ".." in value
            or _URI_SCHEME.search(value) is not None
        ):
            raise ValueError("provider_artifact_id must be a bounded opaque identifier")
        return value

    @field_validator("available_until")
    @classmethod
    def require_aware_expiry(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() != timedelta(0):
            raise ValueError("available_until must be UTC and timezone-aware")
        return value

    @model_validator(mode="after")
    def require_role_media_pair(self) -> VocalProviderPayloadEntry:
        if self.role == "vocal_analysis_result":
            if self.expected_media_type != "application/json":
                raise ValueError("analysis payload must use application/json")
        elif self.expected_media_type not in {"audio/wav", "audio/flac"}:
            raise ValueError("audio payload must use audio/wav or audio/flac")
        return self


class VocalPayloadBackedResultCandidate(VocalProviderResultCandidate):
    """0.2.0 Result whose payload entries are acquisition candidates only."""

    payload_present: bool
    payloads: tuple[VocalProviderPayloadEntry, ...]

    @model_validator(mode="after")
    def require_payload_presence_invariants(self) -> VocalPayloadBackedResultCandidate:
        if self.payload_present != bool(self.payloads):
            raise ValueError("payload_present and payload entries disagree")
        roles = tuple(item.role for item in self.payloads)
        if len(roles) != len(set(roles)):
            raise ValueError("payload roles must be unique")
        return self


AnyVocalProviderResultCandidate = (
    VocalProviderResultCandidate | VocalPayloadBackedResultCandidate
)


ReviewStatus = Literal["UNKNOWN", "REVIEW_REQUIRED", "APPROVED", "REJECTED"]


class VocalModelManifest(StrictFrozenModel):
    model_manifest_id: str
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]
    model_id: str
    model_version: str
    checkpoint_version: str
    model_type: str
    capabilities: tuple[VocalCapability, ...]
    input_formats: tuple[str, ...]
    output_formats: tuple[str, ...]
    api_contract_version: VocalContractVersion
    dataset_manifest_id: str | None = None
    training_run_id: str | None = None
    evaluation_result_id: str | None = None
    license_status: ReviewStatus
    commercial_usage_status: ReviewStatus
    recommended_vram: int | float | None = None
    runtime_environment: dict[str, str]
    artifact_checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    artifact_checksum_scope: Literal["fake_manifest_descriptor"]
    created_at: datetime
    voice_identity_scope: Literal[
        "generic", "user_specific", "speaker_adapter", "conversion_reference"
    ]
    consent_requirement: Literal["caller_verified"]
    supported_languages: tuple[str, ...] = ()
    supported_vocal_styles: tuple[str, ...] = ()

    @field_validator("runtime_environment", mode="before")
    @classmethod
    def detach_runtime_environment(cls, value: Any) -> Any:
        return deepcopy(value)


def _reject_sensitive_or_path_values(value: Any, key: str = "") -> None:
    forbidden_keys = {
        "api_key",
        "credential",
        "dataset_path",
        "model_path",
        "password",
        "path",
        "secret",
        "token",
    }
    if key.lower() in forbidden_keys:
        raise ValueError("Provider 요청에 민감한 설정을 포함할 수 없습니다.")
    if isinstance(value, dict):
        for nested_key, nested_value in value.items():
            _reject_sensitive_or_path_values(nested_value, str(nested_key))
    elif isinstance(value, (list, tuple)):
        for item in value:
            _reject_sensitive_or_path_values(item, key)
    elif isinstance(value, str) and _looks_like_path(value):
        raise ValueError("Provider 요청에 파일 경로를 포함할 수 없습니다.")


def _looks_like_path(value: str) -> bool:
    return bool(
        re.match(r"^[A-Za-z]:[\\/]", value)
        or value.startswith(("/", "\\", "~/", "~\\"))
        or re.search(r"(^|[\\/])\.\.([\\/]|$)", value)
        or re.search(r"(^|:)file://", value, flags=re.IGNORECASE)
    )
