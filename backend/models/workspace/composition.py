"""Composition Snapshot과 Processing 목표 Entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from backend.models.workspace.asset import AssetVersion
    from backend.models.workspace.job import Job
    from backend.models.workspace.workspace import MusicProject


class CompositionSnapshot(CreatedAtMixin, Base):
    __tablename__ = "composition_snapshots"
    __table_args__ = (
        CheckConstraint(
            "snapshot_version >= 1", name="ck_composition_snapshots_positive_version"
        ),
        UniqueConstraint(
            "project_id", "snapshot_version", name="uq_composition_snapshots_version"
        ),
        Index("ix_composition_snapshots_project_created", "project_id", "created_at"),
    )

    composition_snapshot_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("music_projects.project_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    processing_chain_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("processing_chains.processing_chain_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    mix_settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provider_versions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    model_manifest_ids: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )

    project: Mapped[MusicProject] = relationship(back_populates="composition_snapshots")
    processing_chain: Mapped[ProcessingChain | None] = relationship(
        back_populates="composition_snapshots"
    )
    items: Mapped[list[SnapshotItem]] = relationship(
        back_populates="composition_snapshot"
    )
    jobs: Mapped[list[Job]] = relationship(back_populates="composition_snapshot")


class SnapshotItem(CreatedAtMixin, Base):
    __tablename__ = "snapshot_items"
    __table_args__ = (
        UniqueConstraint(
            "composition_snapshot_id",
            "item_role",
            "sort_order",
            name="uq_snapshot_items_role_order",
        ),
        UniqueConstraint(
            "composition_snapshot_id",
            "asset_version_id",
            "item_role",
            name="uq_snapshot_items_version_role",
        ),
    )

    snapshot_item_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    composition_snapshot_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "composition_snapshots.composition_snapshot_id", ondelete="RESTRICT"
        ),
        nullable=False,
        index=True,
    )
    asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    item_role: Mapped[str] = mapped_column(String, nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    composition_snapshot: Mapped[CompositionSnapshot] = relationship(
        back_populates="items"
    )
    asset_version: Mapped[AssetVersion] = relationship(back_populates="snapshot_items")


class ProcessingChain(CreatedAtMixin, Base):
    __tablename__ = "processing_chains"
    __table_args__ = (
        UniqueConstraint("name", "chain_version", name="uq_processing_chains_version"),
    )

    processing_chain_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    chain_version: Mapped[str] = mapped_column(String, nullable=False)
    chain_checksum: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )

    steps: Mapped[list[ProcessingStep]] = relationship(
        back_populates="processing_chain"
    )
    asset_versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="processing_chain"
    )
    composition_snapshots: Mapped[list[CompositionSnapshot]] = relationship(
        back_populates="processing_chain"
    )


class ProcessingStep(CreatedAtMixin, Base):
    __tablename__ = "processing_steps"
    __table_args__ = (
        CheckConstraint("step_order >= 1", name="ck_processing_steps_positive_order"),
        UniqueConstraint(
            "processing_chain_id",
            "step_order",
            name="uq_processing_steps_chain_order",
        ),
    )

    processing_step_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    processing_chain_id: Mapped[UUID] = mapped_column(
        ForeignKey("processing_chains.processing_chain_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    processing_chain: Mapped[ProcessingChain] = relationship(back_populates="steps")
