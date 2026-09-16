from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import CreatedAtMixin, TimestampMixin


class MusicDirectorCandidateStatus(StrEnum):
    GENERATED = "generated"
    REJECTED = "rejected"
    APPLIED = "applied"


class MusicDirectorMaterializationStatus(StrEnum):
    INTENDED = "intended"
    PUBLISHED = "published"
    COMPLETED = "completed"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class MusicDirectorRun(TimestampMixin, Base):
    __tablename__ = "music_director_runs"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "composition_snapshot_id"],
            ["composition_snapshots.project_id", "composition_snapshots.composition_snapshot_id"],
            name="fk_music_director_runs_project_snapshot",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id", "selected_candidate_id"],
            ["music_director_candidates.run_id", "music_director_candidates.candidate_id"],
            name="fk_music_director_runs_selected_candidate",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["run_id", "applied_candidate_id"],
            ["music_director_candidates.run_id", "music_director_candidates.candidate_id"],
            name="fk_music_director_runs_applied_candidate",
            ondelete="RESTRICT",
        ),
        Index("ix_music_director_runs_project_created", "project_id", "created_at"),
    )
    run_id: Mapped[UUID] = mapped_column(primary_key=True, default=generate_uuid)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(nullable=False)
    composition_snapshot_id: Mapped[UUID] = mapped_column(nullable=False)
    selected_candidate_id: Mapped[UUID | None]
    applied_candidate_id: Mapped[UUID | None]
    applied_working_revision: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)


class MusicDirectorCandidate(CreatedAtMixin, Base):
    __tablename__ = "music_director_candidates"
    __table_args__ = (
        UniqueConstraint("run_id", "ordinal", name="uq_music_director_candidates_run_ordinal"),
        UniqueConstraint(
            "run_id", "candidate_id", name="uq_music_director_candidates_run_candidate"
        ),
        CheckConstraint(
            "ordinal >= 0 AND ordinal < 4", name="ck_music_director_candidates_ordinal"
        ),
        CheckConstraint(
            "status IN ('generated', 'rejected', 'applied')",
            name="ck_music_director_candidates_status",
        ),
        CheckConstraint("length(proposal_digest) = 64", name="ck_music_director_candidates_digest"),
    )
    candidate_id: Mapped[UUID] = mapped_column(primary_key=True, default=generate_uuid)
    run_id: Mapped[UUID] = mapped_column(
        ForeignKey("music_director_runs.run_id", ondelete="CASCADE"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="generated", nullable=False)
    proposal_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"), nullable=False
    )
    proposal_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"), nullable=False
    )
    preview_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT")
    )
    provider: Mapped[str | None] = mapped_column(String(100))
    model: Mapped[str | None] = mapped_column(String(200))


class MusicDirectorCandidateMaterialization(TimestampMixin, Base):
    __tablename__ = "music_director_candidate_materializations"
    __table_args__ = (
        UniqueConstraint("job_id", "ordinal", name="uq_md_materializations_job_ordinal"),
        UniqueConstraint("materialization_key", name="uq_md_materializations_key"),
        UniqueConstraint("planned_candidate_id", name="uq_md_materializations_candidate"),
        UniqueConstraint("planned_asset_id", name="uq_md_materializations_asset"),
        UniqueConstraint("planned_asset_version_id", name="uq_md_materializations_version"),
        UniqueConstraint("planned_artifact_id", name="uq_md_materializations_artifact"),
        UniqueConstraint("storage_domain", "storage_key", name="uq_md_materializations_storage"),
        CheckConstraint("ordinal >= 0 AND ordinal < 4", name="ck_md_materializations_ordinal"),
        CheckConstraint("length(proposal_digest) = 64", name="ck_md_materializations_digest"),
        CheckConstraint("version >= 0", name="ck_md_materializations_version"),
        CheckConstraint(
            "status IN ('intended', 'published', 'completed', 'reconciliation_required')",
            name="ck_md_materializations_status",
        ),
        Index(
            "ix_md_materializations_recovery",
            "status",
            "updated_at",
            "materialization_id",
        ),
    )
    materialization_id: Mapped[UUID] = mapped_column(primary_key=True, default=generate_uuid)
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    materialization_key: Mapped[str] = mapped_column(String(64), nullable=False)
    proposal_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    planned_run_id: Mapped[UUID] = mapped_column(nullable=False)
    planned_candidate_id: Mapped[UUID] = mapped_column(nullable=False)
    planned_asset_id: Mapped[UUID] = mapped_column(nullable=False)
    planned_asset_version_id: Mapped[UUID] = mapped_column(nullable=False)
    planned_artifact_id: Mapped[UUID] = mapped_column(nullable=False)
    storage_domain: Mapped[str] = mapped_column(String(32), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="intended")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
