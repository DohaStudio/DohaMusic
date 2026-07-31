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
    consent_confirmed: bool
    created_at: datetime
    updated_at: datetime
