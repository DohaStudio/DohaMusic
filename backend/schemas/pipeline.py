"""Pipeline orchestration API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic_core import PydanticCustomError

from backend.kpop.options import KPopGenerationOptions
from backend.kpop.presets import KPOP_PRESET_REGISTRY
from backend.audio_analysis import PublicAudioAnalysis, sanitize_result_metadata


class PipelineCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    lyrics: str | None = Field(default=None, max_length=20_000)
    genre: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(default=30, ge=1, le=600)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    voice_profile_id: str = Field(min_length=36, max_length=36)
    project_id: str | None = Field(default=None, min_length=36, max_length=36)
    generation_options: KPopGenerationOptions | None = None

    @model_validator(mode="after")
    def validate_preset_genre(self) -> PipelineCreate:
        if self.generation_options is None or self.genre is None:
            return self
        canonical_genre = KPOP_PRESET_REGISTRY.get(
            self.generation_options.preset_id
        ).genre
        if self.genre != canonical_genre:
            raise PydanticCustomError(
                "preset_genre_mismatch",
                "genre must match generation_options.preset_id",
            )
        return self


class PipelineJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    project_id: str | None
    voice_profile_id: str
    status: str
    current_step: str
    progress_percent: int
    prompt: str
    lyrics: str | None
    genre: str | None
    duration_seconds: int
    seed: int | None
    pipeline_version: str
    result_metadata: dict[str, Any]
    audio_analysis: PublicAudioAnalysis | None = None
    failed_step: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    cancel_requested_at: datetime | None
    cancelled_at: datetime | None
    retry_of_job_id: str | None
    can_cancel: bool
    can_retry: bool
    generation_options: KPopGenerationOptions | None = None
    kpop_prompt_compiler_version: str | None = None

    @field_validator("result_metadata", mode="before")
    @classmethod
    def allowlist_audio_analysis(cls, value: object) -> dict[str, Any]:
        return sanitize_result_metadata(value)


class PipelineCancelRead(BaseModel):
    job_id: str
    status: str
    cancel_requested_at: datetime | None
    cancelled_at: datetime | None
    message: str


class PipelineRetryRead(BaseModel):
    source_job_id: str
    job: PipelineJobRead


class PipelineFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_type: str
    mime_type: str
    created_at: datetime
    content_available: bool = False
    download_available: bool = False
    content_url: str | None = None
    download_url: str | None = None
