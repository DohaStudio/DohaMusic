"""Voice profile API schemas."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VoiceProfileCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    reference_file_path: str = Field(min_length=1, max_length=500)
    consent_confirmed: Literal[True]


class VoiceProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    display_filename: str | None
    mime_type: str | None
    size_bytes: int | None
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    consent_confirmed: bool
    consent_text_version: str | None
    status: str
    quality_warnings: list[str]
    created_at: datetime
    updated_at: datetime
