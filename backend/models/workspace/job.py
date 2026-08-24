"""독립 Workspace Job과 입출력·ModelUsage 목표 Entity."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.enums import JobStatus
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from backend.models.workspace.asset import Artifact, AssetVersion
    from backend.models.workspace.collaboration import Approval
    from backend.models.workspace.composition import CompositionSnapshot
    from backend.models.workspace.provider_job import ProviderJobBinding
    from backend.models.workspace.workspace import MusicProject


class Job(CreatedAtMixin, Base):
    __tablename__ = "jobs"
    __table_args__ = (
        CheckConstraint(
            "progress_percent IS NULL OR (progress_percent >= 0 AND progress_percent <= 100)",
            name="ck_jobs_progress_percent",
        ),
        CheckConstraint("attempt >= 0", name="ck_jobs_attempt_nonnegative"),
        Index("ix_jobs_project_created", "project_id", "created_at"),
        Index("ix_jobs_status_created", "status", "created_at"),
        Index(
            "ix_jobs_workspace_keyset",
            "workspace_id",
            "created_at",
            "job_id",
        ),
        Index(
            "ix_jobs_workspace_project_keyset",
            "workspace_id",
            "project_id",
            "created_at",
            "job_id",
        ),
        Index(
            "ix_jobs_workspace_status_keyset",
            "workspace_id",
            "status",
            "created_at",
            "job_id",
        ),
        Index(
            "ix_jobs_workspace_type_keyset",
            "workspace_id",
            "job_type",
            "created_at",
            "job_id",
        ),
        Index(
            "ix_jobs_claim_queue",
            "status",
            "cancel_requested_at",
            "created_at",
            "job_id",
        ),
        Index(
            "ix_jobs_lease_recovery",
            "status",
            "lease_expires_at",
            "job_id",
        ),
    )

    job_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("music_projects.project_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=True,
    )
    composition_snapshot_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("composition_snapshots.composition_snapshot_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(
            JobStatus,
            name="workspace_job_status",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    api_contract_version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_manifest_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    progress_percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    stage: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    retry_of_job_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    error_code: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_retryable: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    error_details_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    requested_by: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claim_token: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    claimed_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )

    project: Mapped[MusicProject] = relationship(back_populates="jobs")
    composition_snapshot: Mapped[CompositionSnapshot | None] = relationship(back_populates="jobs")
    retry_of_job: Mapped[Job | None] = relationship(
        back_populates="retry_jobs",
        remote_side=[job_id],
        foreign_keys=[retry_of_job_id],
    )
    retry_jobs: Mapped[list[Job]] = relationship(
        back_populates="retry_of_job", foreign_keys=[retry_of_job_id]
    )
    inputs: Mapped[list[JobInput]] = relationship(back_populates="job")
    outputs: Mapped[list[JobOutput]] = relationship(back_populates="job")
    model_usages: Mapped[list[ModelUsage]] = relationship(back_populates="job")
    provider_job_bindings: Mapped[list[ProviderJobBinding]] = relationship(
        back_populates="workspace_job"
    )


class JobInput(CreatedAtMixin, Base):
    __tablename__ = "job_inputs"
    __table_args__ = (
        CheckConstraint(
            "(asset_version_id IS NOT NULL AND artifact_id IS NULL) OR "
            "(asset_version_id IS NULL AND artifact_id IS NOT NULL)",
            name="ck_job_inputs_exact_source",
        ),
        UniqueConstraint("job_id", "input_order", name="uq_job_inputs_order"),
    )

    job_input_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    input_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_order: Mapped[int] = mapped_column(Integer, nullable=False)

    job: Mapped[Job] = relationship(back_populates="inputs")
    asset_version: Mapped[AssetVersion | None] = relationship(back_populates="job_inputs")
    artifact: Mapped[Artifact | None] = relationship(back_populates="job_inputs")


class JobOutput(CreatedAtMixin, Base):
    __tablename__ = "job_outputs"
    __table_args__ = (
        CheckConstraint(
            "(asset_version_id IS NOT NULL AND artifact_id IS NULL) OR "
            "(asset_version_id IS NULL AND artifact_id IS NOT NULL)",
            name="ck_job_outputs_exact_target",
        ),
        UniqueConstraint("job_id", "output_order", name="uq_job_outputs_order"),
    )

    job_output_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    output_role: Mapped[str | None] = mapped_column(String(64), nullable=True)
    output_order: Mapped[int] = mapped_column(Integer, nullable=False)

    job: Mapped[Job] = relationship(back_populates="outputs")
    asset_version: Mapped[AssetVersion | None] = relationship(back_populates="job_outputs")
    artifact: Mapped[Artifact | None] = relationship(back_populates="job_outputs")


class ModelUsage(CreatedAtMixin, Base):
    __tablename__ = "model_usages"
    __table_args__ = (
        UniqueConstraint(
            "job_id",
            "model_manifest_id",
            "asset_version_id",
            name="uq_model_usages_job_manifest_version",
        ),
    )

    model_usage_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    provider_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_manifest_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    model_version: Mapped[str] = mapped_column(String, nullable=False)
    checkpoint_version: Mapped[str | None] = mapped_column(String, nullable=True)
    api_contract_version: Mapped[str] = mapped_column(String, nullable=False, index=True)
    license_status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    commercial_usage_status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    job: Mapped[Job] = relationship(back_populates="model_usages")
    asset_version: Mapped[AssetVersion | None] = relationship(back_populates="model_usages")
    approvals: Mapped[list[Approval]] = relationship(back_populates="model_usage")
