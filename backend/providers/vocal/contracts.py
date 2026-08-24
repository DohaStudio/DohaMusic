"""DohaVocal Runtime 0.1.0을 위한 strict consumer DTO."""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DOHAVOCAL_PROVIDER_ID = "dohavocal"
DOHAVOCAL_CONTRACT_VERSION = "0.1.0"
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
    VocalGenerationInput | VoiceConversionInput | VocalCorrectionInput | VocalAnalysisInput,
    Field(discriminator="job_type"),
]


class VocalCreateJobRequest(StrictFrozenModel):
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID] = DOHAVOCAL_PROVIDER_ID
    capability: VocalCapability
    api_contract_version: Literal[DOHAVOCAL_CONTRACT_VERSION] = DOHAVOCAL_CONTRACT_VERSION
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


class VocalCapabilities(StrictFrozenModel):
    provider_id: Literal[DOHAVOCAL_PROVIDER_ID]
    api_contract_version: Literal[DOHAVOCAL_CONTRACT_VERSION]
    capabilities: tuple[VocalCapability, ...]
    supported_operations: tuple[str, ...]

    @model_validator(mode="after")
    def require_complete_surface(self) -> VocalCapabilities:
        if set(self.capabilities) != set(VocalCapability):
            raise ValueError("DohaVocal capability surface가 지원 기준과 다릅니다.")
        if tuple(self.supported_operations) != DOHAVOCAL_OPERATIONS:
            raise ValueError("DohaVocal operation surface가 지원 기준과 다릅니다.")
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
    api_contract_version: Literal[DOHAVOCAL_CONTRACT_VERSION]
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
    api_contract_version: Literal[DOHAVOCAL_CONTRACT_VERSION]
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
