"""Public history and project contracts without storage internals."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HistoryItemRead(BaseModel):
    job_id: str
    project_id: str | None
    title: str
    status: str
    created_at: datetime
    duration: int
    voice_profile_name: str
    has_audio: bool
    can_cancel: bool
    can_retry: bool
    retry_of_job_id: str | None


class HistoryDetailRead(HistoryItemRead):
    prompt: str
    genre: str | None
    completed_at: datetime | None


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Project title must not be blank")
        return value


class ProjectUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Project title must not be blank")
        return value


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str | None
    created_at: datetime
    updated_at: datetime
    job_count: int = 0


class ProjectDetailRead(ProjectRead):
    jobs: list[HistoryItemRead]
