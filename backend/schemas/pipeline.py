"""Pipeline orchestration API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PipelineCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    lyrics: str | None = Field(default=None, max_length=20_000)
    genre: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(default=30, ge=1, le=600)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)
    voice_profile_id: str = Field(min_length=36, max_length=36)


class PipelineJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
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
    failed_step: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class PipelineFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_type: str
    mime_type: str
    created_at: datetime
    content_available: bool = False
    download_available: bool = False
