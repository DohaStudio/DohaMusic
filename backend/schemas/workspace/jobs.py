"""Workspace Job REST API transport schema."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.contracts.vocal_jobs import VocalJobInput
from backend.models.workspace import JobStatus


class JobInputCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_role: str = Field(min_length=1, max_length=64)
    input_order: int = Field(ge=0, strict=True)
    asset_version_id: UUID | None = None
    artifact_id: UUID | None = None

    @model_validator(mode="after")
    def require_exactly_one_reference(self) -> JobInputCreateRequest:
        if (self.asset_version_id is None) == (self.artifact_id is None):
            raise ValueError("AssetVersion 또는 Artifact 중 하나만 필요합니다.")
        return self


class JobCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: UUID
    job_type: str = Field(min_length=1, max_length=64)
    composition_snapshot_id: UUID | None = None
    inputs: list[JobInputCreateRequest] = Field(default_factory=list, max_length=16)
    provider_id: str | None = Field(default=None, max_length=128)
    model_manifest_id: str | None = Field(default=None, max_length=256)
    settings_snapshot: dict[str, Any] = Field(default_factory=dict)
    job_input: VocalJobInput | None = None


class JobSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    job_id: UUID
    project_id: UUID
    composition_snapshot_id: UUID | None
    job_type: str
    status: JobStatus
    provider_id: str | None
    model_manifest_id: str | None
    progress_percent: Decimal | None
    stage: str | None
    retry_of_job_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    @field_validator("progress_percent")
    @classmethod
    def normalize_progress_scale(cls, value: Decimal | None) -> Decimal | None:
        return value.quantize(Decimal("0.01")) if value is not None else None

    @field_validator("created_at", "started_at", "completed_at")
    @classmethod
    def normalize_sqlite_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class JobInputDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    input_role: str | None
    input_order: int
    asset_version_id: UUID | None
    artifact_id: UUID | None


class JobOutputDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    output_role: str | None
    output_order: int
    asset_version_id: UUID | None
    artifact_id: UUID | None


class JobModelUsageDetail(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    provider_id: str
    model_manifest_id: str
    model_id: str
    model_version: str
    checkpoint_version: str | None
    api_contract_version: str
    license_status: str
    commercial_usage_status: str
    asset_version_id: UUID | None


class JobDetail(JobSummary):
    inputs: list[JobInputDetail]
    outputs: list[JobOutputDetail]
    model_usages: list[JobModelUsageDetail]
    error_code: str | None
    error_message: str | None
    error_retryable: bool | None
    error_details_id: str | None
