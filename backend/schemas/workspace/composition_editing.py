"""WorkingComposition product API request and response contracts."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkingCompositionInitializeRequest(_StrictModel):
    pass


class WorkingMutationRequest(_StrictModel):
    working_composition_id: UUID
    expected_revision: int = Field(ge=0)


class WorkingCompositionCheckoutRequest(WorkingMutationRequest):
    composition_snapshot_id: UUID


class TrackCreateRequest(WorkingMutationRequest):
    name: str = Field(min_length=1, max_length=200)


class TrackRenameRequest(WorkingMutationRequest):
    name: str = Field(min_length=1, max_length=200)


class TrackReorderRequest(WorkingMutationRequest):
    ordered_track_ids: list[UUID] = Field(min_length=1)


class TrackRestoreRequest(WorkingMutationRequest):
    target_track_order: int = Field(ge=0)


class ClipCreateRequest(WorkingMutationRequest):
    track_id: UUID
    source_asset_version_id: UUID
    timeline_start: Decimal = Field(ge=0)
    source_in: Decimal = Field(ge=0)
    source_out: Decimal = Field(gt=0)


class ClipMoveRequest(WorkingMutationRequest):
    timeline_start: Decimal = Field(ge=0)


class ClipTrimStartRequest(WorkingMutationRequest):
    timeline_start: Decimal = Field(ge=0)
    source_in: Decimal = Field(ge=0)


class ClipTrimEndRequest(WorkingMutationRequest):
    source_out: Decimal = Field(gt=0)


class ClipSplitRequest(WorkingMutationRequest):
    split_at: Decimal = Field(gt=0)


class ClipToggleRequest(WorkingMutationRequest):
    left_clip_id: UUID
    right_clip_id: UUID


class TrackDetail(_StrictModel):
    track_id: UUID
    track_type: str
    name: str
    track_order: int = Field(ge=0)


class ClipDetail(_StrictModel):
    clip_id: UUID
    track_id: UUID
    source_asset_version_id: UUID
    timeline_start: Decimal
    source_in: Decimal
    source_out: Decimal
    source_duration: Decimal
    split_from_clip_id: UUID | None


class ClipMediaSourceDetail(_StrictModel):
    asset_version_id: UUID
    artifact_id: UUID
    media_type: Literal["audio/wav", "audio/flac", "audio/mpeg"]
    size_bytes: int = Field(gt=0)
    artifact_checksum: str
    duration_seconds: Decimal = Field(gt=0)
    content_url: str = Field(pattern=r"^/api/v1/artifacts/[0-9a-fA-F-]{36}/content$")


class WorkingCompositionDetail(_StrictModel):
    working_composition_id: UUID
    project_id: UUID
    base_composition_snapshot_id: UUID | None
    revision: int = Field(ge=0)
    mix_settings: dict[str, object]
    tracks: list[TrackDetail]
    clips: list[ClipDetail]
    timeline_duration: Decimal


class InitializeResult(_StrictModel):
    working_composition_id: UUID
    completed_revision: int = Field(ge=0)
    replayed: bool


class CheckoutResult(_StrictModel):
    working_composition_id: UUID
    base_composition_snapshot_id: UUID
    completed_revision: int = Field(ge=0)
    replayed: bool


class TrackMutationResult(_StrictModel):
    track_id: UUID
    completed_revision: int = Field(ge=0)
    replayed: bool


class ReorderTracksResult(_StrictModel):
    working_composition_id: UUID
    completed_revision: int = Field(ge=0)


class ClipMutationResult(_StrictModel):
    clip_id: UUID
    completed_revision: int = Field(ge=0)
    replayed: bool


class SplitClipResult(_StrictModel):
    original_clip_id: UUID
    left_clip_id: UUID
    right_clip_id: UUID
    completed_revision: int = Field(ge=0)
    replayed: bool
