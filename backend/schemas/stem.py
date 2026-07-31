"""Stem separation API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class StemCreate(BaseModel):
    source_file_id: str = Field(min_length=36, max_length=36)


class StemJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_file_id: str
    status: str
    current_step: str
    provider: str | None
    model_name: str | None
    model_version: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class StemFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_type: str
    mime_type: str
    created_at: datetime
    content_available: bool = False
    download_available: bool = False
