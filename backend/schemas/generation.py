"""Generation API request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GenerationCreate(BaseModel):
    prompt: str = Field(min_length=1, max_length=4_000)
    lyrics: str | None = Field(default=None, max_length=20_000)
    genre: str | None = Field(default=None, max_length=100)
    duration_seconds: int = Field(default=30, ge=1, le=600)
    seed: int | None = Field(default=None, ge=0, le=2_147_483_647)


class GenerationJobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    prompt: str
    lyrics: str | None
    genre: str | None
    duration_seconds: int
    seed: int | None
    current_step: str
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
