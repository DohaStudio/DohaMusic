"""Voice conversion API schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VoiceConversionCreate(BaseModel):
    source_file_id: str = Field(min_length=36, max_length=36)
    voice_profile_id: str = Field(min_length=36, max_length=36)


class VoiceConversionJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_file_id: str
    voice_profile_id: str
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


class VoiceConversionFileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    job_id: str
    file_type: str
    file_path: str
    mime_type: str
    created_at: datetime
