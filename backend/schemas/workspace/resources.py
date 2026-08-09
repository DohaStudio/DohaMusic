"""Workspace와 MusicProject REST API transport schema."""

from __future__ import annotations

from datetime import datetime
from typing import Any
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
