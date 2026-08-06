"""Enrollment, Approval과 Workspace Metadata 목표 Entity."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import (
    CreatedAtMixin,
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from backend.models.workspace.asset import Asset, AssetVersion
    from backend.models.workspace.job import ModelUsage
    from backend.models.workspace.workspace import Workspace


class RecordingEnrollment(CreatedAtMixin, SoftDeleteMixin, Base):
    __tablename__ = "recording_enrollments"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id",
            "recording_asset_version_id",
            "consent_policy_version",
            name="uq_recording_enrollments_consent",
        ),
    )

    recording_enrollment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    recording_asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    consent_policy_version: Mapped[str] = mapped_column(
        String, nullable=False, index=True
    )
    consent_evidence_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workspace: Mapped[Workspace] = relationship(back_populates="recording_enrollments")
    recording_asset_version: Mapped[AssetVersion] = relationship(
        back_populates="recording_enrollments"
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="recording_enrollment"
    )


class Approval(CreatedAtMixin, Base):
    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN asset_version_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN recording_enrollment_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN model_usage_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_approvals_exact_target",
        ),
    )

    approval_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    recording_enrollment_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "recording_enrollments.recording_enrollment_id", ondelete="RESTRICT"
        ),
        nullable=True,
        index=True,
    )
    model_usage_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("model_usages.model_usage_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    usage_purpose: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, nullable=False, index=True)
    approved_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    evidence_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    asset_version: Mapped[AssetVersion | None] = relationship(
        back_populates="approvals"
    )
    recording_enrollment: Mapped[RecordingEnrollment | None] = relationship(
        back_populates="approvals"
    )
    model_usage: Mapped[ModelUsage | None] = relationship(back_populates="approvals")


class Tag(CreatedAtMixin, SoftDeleteMixin, Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("asset_id", "name", name="uq_tags_asset_name"),)

    tag_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )

    asset: Mapped[Asset] = relationship(back_populates="tags")


class Comment(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "comments"
    __table_args__ = (
        Index("ix_comments_version_created", "asset_version_id", "created_at"),
    )

    comment_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    asset_version: Mapped[AssetVersion] = relationship(back_populates="comments")


class Favorite(CreatedAtMixin, SoftDeleteMixin, Base):
    __tablename__ = "favorites"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "asset_id", name="uq_favorites_workspace_asset"
        ),
    )

    favorite_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=False, index=True
    )

    workspace: Mapped[Workspace] = relationship(back_populates="favorites")
    asset: Mapped[Asset] = relationship(back_populates="favorites")


class History(CreatedAtMixin, Base):
    __tablename__ = "history"
    __table_args__ = (
        Index("ix_history_workspace_created", "workspace_id", "created_at"),
        Index("ix_history_entity_created", "entity_type", "entity_id", "created_at"),
    )

    history_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    actor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    entity_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(String, nullable=False, index=True)
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    workspace: Mapped[Workspace] = relationship(back_populates="history_entries")
