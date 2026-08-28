"""Revision-pinned WorkingComposition preview render manifests."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import CreatedAtMixin


class WorkingPreviewAsset(Base):
    """Project당 하나인 non-canonical preview Asset binding."""

    __tablename__ = "working_preview_assets"

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("music_projects.project_id", ondelete="RESTRICT"), primary_key=True
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False, unique=True
    )


class WorkingPreviewRender(CreatedAtMixin, Base):
    """Workspace Job에 고정된 immutable preview manifest identity."""

    __tablename__ = "working_preview_renders"
    __table_args__ = (
        CheckConstraint("rendered_revision >= 0", name="ck_working_preview_non_negative_revision"),
        UniqueConstraint("workspace_job_id", name="uq_working_preview_render_job"),
        Index(
            "ix_working_preview_render_working_revision",
            "working_composition_id",
            "rendered_revision",
            "created_at",
        ),
    )

    preview_render_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("music_projects.project_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    working_composition_id: Mapped[UUID] = mapped_column(
        ForeignKey("working_compositions.working_composition_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    rendered_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    workspace_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    preview_asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    preview_asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    payload_expires_at: Mapped[datetime] = mapped_column(nullable=False, index=True)


class WorkingPreviewRenderTrack(Base):
    __tablename__ = "working_preview_render_tracks"
    __table_args__ = (
        CheckConstraint("track_order >= 0", name="ck_working_preview_track_non_negative_order"),
        UniqueConstraint("preview_render_id", "track_order", name="uq_working_preview_track_order"),
        UniqueConstraint("preview_render_id", "track_id", name="uq_working_preview_track_identity"),
    )

    preview_render_id: Mapped[UUID] = mapped_column(
        ForeignKey("working_preview_renders.preview_render_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    track_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    track_order: Mapped[int] = mapped_column(Integer, nullable=False)


class WorkingPreviewRenderClip(Base):
    __tablename__ = "working_preview_render_clips"
    __table_args__ = (
        CheckConstraint("canonical_order >= 0", name="ck_working_preview_clip_non_negative_order"),
        CheckConstraint("source_in_us >= 0", name="ck_working_preview_clip_non_negative_source_in"),
        CheckConstraint("source_duration_us > 0", name="ck_working_preview_clip_positive_duration"),
        CheckConstraint(
            "source_out_us > source_in_us", name="ck_working_preview_clip_non_empty_range"
        ),
        CheckConstraint(
            "source_out_us <= source_duration_us",
            name="ck_working_preview_clip_range_within_source",
        ),
        CheckConstraint(
            "timeline_start_us >= 0", name="ck_working_preview_clip_non_negative_timeline"
        ),
        UniqueConstraint(
            "preview_render_id", "canonical_order", name="uq_working_preview_clip_order"
        ),
        ForeignKeyConstraint(
            ["preview_render_id", "track_id"],
            [
                "working_preview_render_tracks.preview_render_id",
                "working_preview_render_tracks.track_id",
            ],
            ondelete="RESTRICT",
            name="fk_working_preview_clip_manifest_track",
        ),
        Index("ix_working_preview_clip_artifact", "source_artifact_id"),
    )

    preview_render_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    clip_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    track_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    canonical_order: Mapped[int] = mapped_column(Integer, nullable=False)
    source_asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"), nullable=False
    )
    source_artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"), nullable=False
    )
    source_in_us: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_out_us: Mapped[int] = mapped_column(BigInteger, nullable=False)
    source_duration_us: Mapped[int] = mapped_column(BigInteger, nullable=False)
    timeline_start_us: Mapped[int] = mapped_column(BigInteger, nullable=False)
