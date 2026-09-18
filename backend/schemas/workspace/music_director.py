from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class MusicDirectorIntentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=2000)
    candidate_count: int = Field(default=2, ge=1, le=4, strict=True)


class MusicDirectorRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    composition_snapshot_id: UUID
    music_intent: MusicDirectorIntentRequest


class MusicDirectorJobCreated(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    project_id: UUID
    composition_snapshot_id: UUID
    status: str
    candidate_count: int
    created_at: datetime

    _normalize_created_at = field_validator("created_at", mode="before")(_utc)


class MusicDirectorCandidateDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: UUID
    ordinal: int
    status: str
    proposal_digest: str
    proposal_artifact_id: UUID
    preview_artifact_id: UUID | None
    candidate_asset_version_id: UUID
    selected: bool
    applied: bool


class MusicDirectorRunDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    job_id: UUID
    project_id: UUID
    composition_snapshot_id: UUID
    selected_candidate_id: UUID | None
    applied_candidate_id: UUID | None
    applied_working_revision: int | None
    version: int
    status: str
    candidates: list[MusicDirectorCandidateDetail]
    created_at: datetime
    updated_at: datetime

    _normalize_timestamps = field_validator("created_at", "updated_at", mode="before")(_utc)


class MusicDirectorSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_run_version: int = Field(ge=0, strict=True)


class MusicDirectorSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    selected_candidate_id: UUID
    version: int


class MusicDirectorApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_run_version: int = Field(ge=0, strict=True)
    expected_working_composition_revision: int = Field(ge=0, strict=True)


class MusicDirectorApplyResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: UUID
    candidate_id: UUID
    working_composition_id: UUID
    working_composition_revision: int
    run_version: int
    history_entry_id: UUID
    replayed: bool
