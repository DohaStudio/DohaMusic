"""Workspace Job에 보존하는 DohaVocal capability 입력 계약."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

DOHAVOCAL_PROVIDER_ID = "dohavocal"
VOCAL_JOB_INPUT_SETTINGS_KEY = "_workspace_vocal_job_input"
VOCAL_JOB_TYPES = frozenset(
    {"vocal_generation", "voice_conversion", "vocal_correction", "vocal_analysis"}
)
VOCAL_JOB_INPUT_ROLES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "vocal_generation": (
        frozenset({"lyrics_reference", "melody_reference"}),
        frozenset(
            {
                "lyrics_reference",
                "melody_reference",
                "timing_reference",
                "voice_reference",
            }
        ),
    ),
    "voice_conversion": (
        frozenset({"source_vocal", "voice_reference"}),
        frozenset({"source_vocal", "voice_reference"}),
    ),
    "vocal_correction": (
        frozenset({"source_vocal"}),
        frozenset({"source_vocal"}),
    ),
    "vocal_analysis": (
        frozenset({"source_vocal"}),
        frozenset({"source_vocal"}),
    ),
}
VOCAL_JOB_OUTPUT_ROLES = {
    "vocal_generation": "generated_vocal_candidate",
    "voice_conversion": "converted_vocal_candidate",
    "vocal_correction": "corrected_vocal_candidate",
    "vocal_analysis": "vocal_analysis_result",
}


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


class _StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class VocalGenerationJobInput(_StrictInput):
    job_type: Literal["vocal_generation"]
    lyrics_reference: UUID
    melody_reference: UUID
    timing_reference: UUID | None = None
    voice_reference: UUID | None = None
    processing_chain_id: UUID | None = None


class VoiceConversionJobInput(_StrictInput):
    job_type: Literal["voice_conversion"]
    source_asset_version_id: UUID
    parent_asset_version_id: UUID | None = None
    voice_reference_artifact_id: UUID
    source_entity_type: Literal["recording_take", "ai_generated_vocal"]
    reference_entity_type: Literal["voice_enrollment_sample"]
    training_dataset_id: Literal[None] = None
    processing_chain_id: UUID | None = None


class VocalCorrectionJobInput(_StrictInput):
    job_type: Literal["vocal_correction"]
    source_asset_version_id: UUID
    parent_asset_version_id: UUID | None = None
    correction_types: tuple[VocalCorrectionType, ...] = Field(min_length=1)
    processing_chain_id: UUID | None = None


class VocalAnalysisJobInput(_StrictInput):
    job_type: Literal["vocal_analysis"]
    source_asset_version_id: UUID
    parent_asset_version_id: UUID | None = None
    analysis_types: tuple[VocalAnalysisType, ...] = Field(min_length=1)
    processing_chain_id: UUID | None = None


VocalJobInput = Annotated[
    VocalGenerationJobInput
    | VoiceConversionJobInput
    | VocalCorrectionJobInput
    | VocalAnalysisJobInput,
    Field(discriminator="job_type"),
]
VOCAL_JOB_INPUT_ADAPTER = TypeAdapter(VocalJobInput)
