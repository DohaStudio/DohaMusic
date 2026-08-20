"""Workspace와 MusicProject REST API transport schema."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.models.workspace import AssetType


class WorkspaceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    workspace_id: UUID
    name: str
    lifecycle_status: str
    created_at: datetime
    updated_at: datetime


class WorkspaceDetail(WorkspaceSummary):
    pass


class WorkspaceUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=255)


class ProjectSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    project_id: UUID
    workspace_id: UUID
    title: str
    lifecycle_status: str
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectSummary):
    description: str | None


class ProjectCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)


class ProjectUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=10_000)

    @field_validator("description")
    @classmethod
    def reject_explicit_null_description(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("description은 null로 수정할 수 없습니다.")
        return value

    @model_validator(mode="after")
    def require_at_least_one_field(self) -> ProjectUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("수정할 필드가 하나 이상 필요합니다.")
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("title은 null로 수정할 수 없습니다.")
        return self


class ProjectAssetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    asset_id: UUID
    role: str | None
    display_order: int


class ProjectAssetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: UUID
    role: str | None = None
    display_order: int = Field(default=0, ge=0, strict=True)


class AssetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    asset_id: UUID
    workspace_id: UUID | None
    asset_type: AssetType
    selected_asset_version_id: UUID | None
    lifecycle_status: str
    created_at: datetime
    updated_at: datetime


class AssetDetail(AssetSummary):
    pass


class AssetCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: UUID | None = None
    asset_type: AssetType
    lifecycle_status: str = Field(default="active", min_length=1, max_length=255)


class AssetUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lifecycle_status: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def require_lifecycle_status(self) -> AssetUpdateRequest:
        if "lifecycle_status" not in self.model_fields_set:
            raise ValueError("수정할 필드가 하나 이상 필요합니다.")
        if self.lifecycle_status is None:
            raise ValueError("lifecycle_status는 null로 수정할 수 없습니다.")
        return self


class AssetVersionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    asset_version_id: UUID
    asset_id: UUID
    version_number: int
    version_origin: str
    parent_asset_version_id: UUID | None
    processing_chain_id: UUID | None
    provider_id: str | None
    model_manifest_id: str | None
    settings_snapshot: dict[str, Any]
    created_at: datetime


class AssetVersionDetail(AssetVersionSummary):
    pass


class ArtifactDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_id: UUID
    asset_version_id: UUID
    artifact_kind: str
    media_type: str
    size_bytes: int
    checksum_algorithm: str
    artifact_checksum: str
    producer_type: str
    producer_id: str | None
    run_id: str | None
    retention_status: str
    created_at: datetime
    content_url: str | None = None
    download_url: str | None = None


class AssetVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_origin: str = Field(min_length=1, max_length=255)
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)
    parent_asset_version_id: UUID | None = None
    processing_chain_id: UUID | None = None
    provider_id: str | None = Field(default=None, min_length=1, max_length=255)
    model_manifest_id: str | None = Field(default=None, min_length=1, max_length=255)


class SnapshotItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_version_id: UUID
    item_role: Literal["lyrics", "music", "vocal", "stem", "mix"]
    sort_order: int = Field(ge=0, strict=True)


class CompositionSnapshotCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    items: list[SnapshotItemCreateRequest] = Field(min_length=1, max_length=64)
    processing_chain_id: UUID | None = None
    mix_settings_snapshot: dict[str, Any] = Field(default_factory=dict)
    provider_versions: dict[str, str] = Field(default_factory=dict)
    model_manifest_ids: dict[str, str] = Field(default_factory=dict)


class CompositionSnapshotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    composition_snapshot_id: UUID
    project_id: UUID
    snapshot_version: int
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class SnapshotItemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    snapshot_item_id: UUID
    asset_version_id: UUID
    item_role: Literal["lyrics", "music", "vocal", "stem", "mix"]
    sort_order: int
    created_at: datetime

    @field_validator("created_at", mode="before")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class CompositionSnapshotDetail(CompositionSnapshotSummary):
    processing_chain_id: UUID | None
    mix_settings_snapshot: dict[str, Any]
    provider_versions: dict[str, str]
    model_manifest_ids: dict[str, str]
    items: list[SnapshotItemDetail]


class CompositionSelectionUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_snapshot_id: UUID | None


class CompositionSelectionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    project_id: UUID
    selected_snapshot_id: UUID | None


class CompositionReadSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selected_snapshot_id: UUID | None
    resolved_snapshot_id: UUID | None
    resolution: Literal["selected", "requested", "none"]
    is_current: bool


class CompositionReadSnapshot(CompositionSnapshotSummary):
    processing_chain_id: UUID | None
    provider_versions: dict[str, str]
    model_manifest_ids: dict[str, str]


class CompositionReadItemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snapshot_item_id: UUID
    item_role: Literal["lyrics", "music", "vocal", "stem", "mix"]
    sort_order: int
    asset_version: AssetVersionDetail
    artifacts: list[ArtifactDetail]


class CompositionTrackProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    projection_id: UUID
    identity_scope: Literal["snapshot"] = "snapshot"
    snapshot_item_id: UUID
    item_role: Literal["music", "vocal", "stem", "mix"]
    sort_order: int
    asset_id: UUID
    asset_version_id: UUID


class CompositionSectionProjection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    availability: Literal["not_available"] = "not_available"
    items: list[dict[str, Any]] = Field(default_factory=list, max_length=0)


class CompositionReadLineage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    processing_chain_id: UUID | None
    provider_versions: dict[str, str]
    model_manifest_ids: dict[str, str]


class CompositionWorkspaceRead(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: Literal["ready", "empty", "selection_required"]
    project: ProjectSummary
    selection: CompositionReadSelection
    snapshot: CompositionReadSnapshot | None
    items: list[CompositionReadItemDetail]
    track_projections: list[CompositionTrackProjection]
    section_projection: CompositionSectionProjection
    mix_settings_snapshot: dict[str, Any]
    lineage: CompositionReadLineage
