"""Asset, AssetVersion, Artifact와 AssetRelation 목표 Entity."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.enums import AssetType
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import (
    CreatedAtMixin,
    SoftDeleteMixin,
    TimestampMixin,
)

if TYPE_CHECKING:
    from backend.models.workspace.collaboration import (
        Approval,
        Comment,
        Favorite,
        RecordingEnrollment,
        Tag,
    )
    from backend.models.workspace.composition import (
        ProcessingChain,
        SnapshotItem,
    )
    from backend.models.workspace.job import JobInput, JobOutput, ModelUsage
    from backend.models.workspace.payload_locator import PayloadLocator
    from backend.models.workspace.storage import ArtifactStorageLocation
    from backend.models.workspace.workspace import ProjectAsset, Workspace


class Asset(TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        Index(
            "ix_assets_owner_active_keyset",
            "owner_id",
            "deleted_at",
            "created_at",
            "asset_id",
        ),
        Index(
            "ix_assets_owner_workspace_active_keyset",
            "owner_id",
            "workspace_id",
            "deleted_at",
            "created_at",
            "asset_id",
        ),
    )

    asset_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    workspace_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workspaces.workspace_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    owner_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )
    asset_type: Mapped[AssetType] = mapped_column(
        SAEnum(
            AssetType,
            name="workspace_asset_type",
            native_enum=False,
            values_callable=lambda enum: [item.value for item in enum],
            validate_strings=True,
        ),
        nullable=False,
        index=True,
    )
    selected_asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    lifecycle_status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    workspace: Mapped[Workspace | None] = relationship(back_populates="assets")
    project_assets: Mapped[list[ProjectAsset]] = relationship(back_populates="asset")
    versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="asset", foreign_keys="AssetVersion.asset_id"
    )
    selected_version: Mapped[AssetVersion | None] = relationship(
        back_populates="selected_by_asset",
        foreign_keys=[selected_asset_version_id],
        post_update=True,
    )
    source_relations: Mapped[list[AssetRelation]] = relationship(
        back_populates="source_asset", foreign_keys="AssetRelation.source_asset_id"
    )
    target_relations: Mapped[list[AssetRelation]] = relationship(
        back_populates="target_asset", foreign_keys="AssetRelation.target_asset_id"
    )
    tags: Mapped[list[Tag]] = relationship(back_populates="asset")
    favorites: Mapped[list[Favorite]] = relationship(back_populates="asset")


class AssetVersion(CreatedAtMixin, Base):
    __tablename__ = "asset_versions"
    __table_args__ = (
        CheckConstraint(
            "version_number >= 1", name="ck_asset_versions_positive_number"
        ),
        UniqueConstraint("asset_id", "version_number", name="uq_asset_versions_number"),
    )

    asset_version_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    asset_id: Mapped[UUID] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    version_origin: Mapped[str] = mapped_column(String, nullable=False, index=True)
    parent_asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    processing_chain_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("processing_chains.processing_chain_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    provider_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    model_manifest_id: Mapped[str | None] = mapped_column(
        String, nullable=True, index=True
    )
    settings_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False, index=True
    )

    asset: Mapped[Asset] = relationship(
        back_populates="versions", foreign_keys=[asset_id]
    )
    selected_by_asset: Mapped[Asset | None] = relationship(
        back_populates="selected_version",
        foreign_keys="Asset.selected_asset_version_id",
        uselist=False,
    )
    parent_version: Mapped[AssetVersion | None] = relationship(
        back_populates="child_versions",
        remote_side=[asset_version_id],
        foreign_keys=[parent_asset_version_id],
    )
    child_versions: Mapped[list[AssetVersion]] = relationship(
        back_populates="parent_version", foreign_keys=[parent_asset_version_id]
    )
    processing_chain: Mapped[ProcessingChain | None] = relationship(
        back_populates="asset_versions"
    )
    artifacts: Mapped[list[Artifact]] = relationship(back_populates="asset_version")
    source_relations: Mapped[list[AssetRelation]] = relationship(
        back_populates="source_asset_version",
        foreign_keys="AssetRelation.source_asset_version_id",
    )
    target_relations: Mapped[list[AssetRelation]] = relationship(
        back_populates="target_asset_version",
        foreign_keys="AssetRelation.target_asset_version_id",
    )
    snapshot_items: Mapped[list[SnapshotItem]] = relationship(
        back_populates="asset_version"
    )
    job_inputs: Mapped[list[JobInput]] = relationship(back_populates="asset_version")
    job_outputs: Mapped[list[JobOutput]] = relationship(back_populates="asset_version")
    model_usages: Mapped[list[ModelUsage]] = relationship(
        back_populates="asset_version"
    )
    recording_enrollments: Mapped[list[RecordingEnrollment]] = relationship(
        back_populates="recording_asset_version"
    )
    approvals: Mapped[list[Approval]] = relationship(back_populates="asset_version")
    comments: Mapped[list[Comment]] = relationship(back_populates="asset_version")


class Artifact(CreatedAtMixin, Base):
    __tablename__ = "artifacts"
    __table_args__ = (
        CheckConstraint(
            "duration_us IS NULL OR duration_us > 0",
            name="ck_artifacts_positive_duration_us",
        ),
        Index(
            "ix_artifacts_checksum_size",
            "checksum_algorithm",
            "artifact_checksum",
            "size_bytes",
        ),
        Index(
            "ix_artifacts_version_created",
            "asset_version_id",
            "created_at",
            "artifact_id",
        ),
    )

    artifact_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    asset_version_id: Mapped[UUID] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    artifact_kind: Mapped[str] = mapped_column(String, nullable=False, index=True)
    media_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    duration_us: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    checksum_algorithm: Mapped[str] = mapped_column(String, nullable=False)
    artifact_checksum: Mapped[str] = mapped_column(String, nullable=False, index=True)
    producer_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    producer_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    run_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    retention_status: Mapped[str] = mapped_column(String, nullable=False, index=True)

    asset_version: Mapped[AssetVersion] = relationship(back_populates="artifacts")
    storage_location: Mapped[ArtifactStorageLocation | None] = relationship(
        "ArtifactStorageLocation", back_populates="artifact", uselist=False
    )
    job_inputs: Mapped[list[JobInput]] = relationship(back_populates="artifact")
    job_outputs: Mapped[list[JobOutput]] = relationship(back_populates="artifact")
    payload_locators: Mapped[list[PayloadLocator]] = relationship(
        back_populates="ingested_artifact"
    )


class AssetRelation(CreatedAtMixin, Base):
    __tablename__ = "asset_relations"
    __table_args__ = (
        CheckConstraint(
            "((source_asset_id IS NOT NULL AND target_asset_id IS NOT NULL "
            "AND source_asset_version_id IS NULL AND target_asset_version_id IS NULL "
            "AND source_asset_id <> target_asset_id) OR "
            "(source_asset_id IS NULL AND target_asset_id IS NULL "
            "AND source_asset_version_id IS NOT NULL "
            "AND target_asset_version_id IS NOT NULL "
            "AND source_asset_version_id <> target_asset_version_id))",
            name="ck_asset_relations_exact_pair",
        ),
        UniqueConstraint(
            "source_asset_id",
            "target_asset_id",
            "relation_type",
            name="uq_asset_relations_asset_pair",
        ),
        UniqueConstraint(
            "source_asset_version_id",
            "target_asset_version_id",
            "relation_type",
            name="uq_asset_relations_version_pair",
        ),
    )

    relation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    source_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    target_asset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("assets.asset_id", ondelete="RESTRICT"), nullable=True, index=True
    )
    source_asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    target_asset_version_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("asset_versions.asset_version_id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    relation_type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    source_asset: Mapped[Asset | None] = relationship(
        back_populates="source_relations", foreign_keys=[source_asset_id]
    )
    target_asset: Mapped[Asset | None] = relationship(
        back_populates="target_relations", foreign_keys=[target_asset_id]
    )
    source_asset_version: Mapped[AssetVersion | None] = relationship(
        back_populates="source_relations", foreign_keys=[source_asset_version_id]
    )
    target_asset_version: Mapped[AssetVersion | None] = relationship(
        back_populates="target_relations", foreign_keys=[target_asset_version_id]
    )
