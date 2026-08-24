"""Asset aggregate persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session, joinedload

from backend.models.workspace.asset import (
    Artifact,
    Asset,
    AssetRelation,
    AssetVersion,
)
from backend.models.workspace.enums import AssetType
from backend.models.workspace.mixins import utc_now


class AssetRepository:
    """Asset aggregate를 commit 없이 현재 transaction에 반영한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_asset(self, asset: Asset) -> Asset:
        self.session.add(asset)
        self.session.flush()
        return asset

    def get_asset(
        self, asset_id: UUID, *, include_deleted: bool = False
    ) -> Asset | None:
        statement = select(Asset).where(Asset.asset_id == asset_id)
        if not include_deleted:
            statement = statement.where(Asset.deleted_at.is_(None))
        return self.session.scalar(statement)

    def list_assets(
        self,
        *,
        owner_id: UUID | None = None,
        asset_type: AssetType | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Asset]:
        statement = select(Asset)
        if owner_id is not None:
            statement = statement.where(Asset.owner_id == owner_id)
        if asset_type is not None:
            statement = statement.where(Asset.asset_type == asset_type)
        if not include_deleted:
            statement = statement.where(Asset.deleted_at.is_(None))
        statement = (
            statement.order_by(Asset.created_at.desc(), Asset.asset_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_workspace_assets(
        self,
        workspace_id: UUID,
        *,
        asset_type: AssetType | None = None,
        include_deleted: bool = False,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Asset]:
        statement = select(Asset).where(Asset.workspace_id == workspace_id)
        if asset_type is not None:
            statement = statement.where(Asset.asset_type == asset_type)
        if not include_deleted:
            statement = statement.where(Asset.deleted_at.is_(None))
        statement = (
            statement.order_by(Asset.created_at.desc(), Asset.asset_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_assets_after(
        self,
        *,
        owner_id: UUID,
        workspace_id: UUID | None = None,
        asset_type: AssetType | None = None,
        last_created_at: datetime | None = None,
        last_id: UUID | None = None,
        limit: int = 100,
    ) -> list[Asset]:
        """Owner scope를 고정한 활성 Asset DESC keyset 조회."""

        _validate_keyset_position(last_created_at, last_id)
        statement = select(Asset).where(
            Asset.owner_id == owner_id,
            Asset.deleted_at.is_(None),
        )
        if workspace_id is not None:
            statement = statement.where(Asset.workspace_id == workspace_id)
        if asset_type is not None:
            statement = statement.where(Asset.asset_type == asset_type)
        if last_created_at is not None and last_id is not None:
            statement = statement.where(
                or_(
                    Asset.created_at < last_created_at,
                    and_(
                        Asset.created_at == last_created_at,
                        Asset.asset_id < last_id,
                    ),
                )
            )
        statement = statement.order_by(
            Asset.created_at.desc(), Asset.asset_id.desc()
        ).limit(limit)
        return list(self.session.scalars(statement))

    def soft_delete_asset(self, asset: Asset) -> Asset:
        asset.deleted_at = utc_now()
        self.session.flush()
        return asset

    def add_asset_version(self, asset_version: AssetVersion) -> AssetVersion:
        self.session.add(asset_version)
        self.session.flush()
        return asset_version

    def get_asset_version(self, asset_version_id: UUID) -> AssetVersion | None:
        return self.session.get(AssetVersion, asset_version_id)

    def list_asset_versions(
        self,
        asset_id: UUID,
        *,
        limit: int | None = 100,
        offset: int = 0,
        newest_first: bool = False,
    ) -> list[AssetVersion]:
        ordering = (
            (AssetVersion.version_number.desc(), AssetVersion.asset_version_id.desc())
            if newest_first
            else (AssetVersion.version_number, AssetVersion.asset_version_id)
        )
        statement = (
            select(AssetVersion)
            .where(AssetVersion.asset_id == asset_id)
            .order_by(*ordering)
            .offset(offset)
        )
        if limit is not None:
            statement = statement.limit(limit)
        return list(self.session.scalars(statement))

    def get_latest_asset_version(self, asset_id: UUID) -> AssetVersion | None:
        statement = (
            select(AssetVersion)
            .where(AssetVersion.asset_id == asset_id)
            .order_by(AssetVersion.version_number.desc(), AssetVersion.asset_version_id)
            .limit(1)
        )
        return self.session.scalar(statement)

    def version_number_exists(self, asset_id: UUID, version_number: int) -> bool:
        statement = select(AssetVersion.asset_version_id).where(
            AssetVersion.asset_id == asset_id,
            AssetVersion.version_number == version_number,
        )
        return self.session.scalar(statement.limit(1)) is not None

    def add_artifact(self, artifact: Artifact) -> Artifact:
        self.session.add(artifact)
        self.session.flush()
        return artifact

    def get_artifact(self, artifact_id: UUID) -> Artifact | None:
        return self.session.get(Artifact, artifact_id)

    def get_artifact_for_owner(
        self,
        artifact_id: UUID,
        owner_id: UUID,
    ) -> Artifact | None:
        """Soft Delete되지 않은 Asset 계보의 Owner 범위에서 Artifact를 조회한다."""

        statement = (
            select(Artifact)
            .join(Artifact.asset_version)
            .join(AssetVersion.asset)
            .where(
                Artifact.artifact_id == artifact_id,
                Asset.owner_id == owner_id,
                Asset.deleted_at.is_(None),
            )
            .options(joinedload(Artifact.asset_version).joinedload(AssetVersion.asset))
        )
        return self.session.scalar(statement)

    def list_version_artifacts(
        self, asset_version_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Artifact]:
        statement = (
            select(Artifact)
            .where(Artifact.asset_version_id == asset_version_id)
            .order_by(Artifact.created_at, Artifact.artifact_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_clip_source_artifact_candidates(
        self, asset_version_id: UUID
    ) -> list[Artifact]:
        """Clip source 후보를 fallback 없이 deterministic하게 반환한다."""

        statement = (
            select(Artifact)
            .where(
                Artifact.asset_version_id == asset_version_id,
                Artifact.artifact_kind.in_(("audio", "stem")),
                Artifact.media_type.in_(("audio/wav", "audio/flac", "audio/mpeg")),
                Artifact.retention_status == "active",
            )
            .order_by(Artifact.created_at, Artifact.artifact_id)
        )
        return list(self.session.scalars(statement))

    def checksum_exists(self, checksum_algorithm: str, artifact_checksum: str) -> bool:
        statement = select(Artifact.artifact_id).where(
            Artifact.checksum_algorithm == checksum_algorithm,
            Artifact.artifact_checksum == artifact_checksum,
        )
        return self.session.scalar(statement.limit(1)) is not None

    def add_asset_relation(self, relation: AssetRelation) -> AssetRelation:
        self.session.add(relation)
        self.session.flush()
        return relation

    def get_asset_relation(self, relation_id: UUID) -> AssetRelation | None:
        return self.session.get(AssetRelation, relation_id)

    def list_asset_relations(
        self,
        *,
        asset_id: UUID | None = None,
        asset_version_id: UUID | None = None,
        relation_type: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AssetRelation]:
        statement = select(AssetRelation)
        if asset_id is not None:
            statement = statement.where(
                or_(
                    AssetRelation.source_asset_id == asset_id,
                    AssetRelation.target_asset_id == asset_id,
                )
            )
        if asset_version_id is not None:
            statement = statement.where(
                or_(
                    AssetRelation.source_asset_version_id == asset_version_id,
                    AssetRelation.target_asset_version_id == asset_version_id,
                )
            )
        if relation_type is not None:
            statement = statement.where(AssetRelation.relation_type == relation_type)
        statement = (
            statement.order_by(AssetRelation.created_at, AssetRelation.relation_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def relation_exists(
        self,
        *,
        relation_type: str,
        source_asset_id: UUID | None = None,
        target_asset_id: UUID | None = None,
        source_asset_version_id: UUID | None = None,
        target_asset_version_id: UUID | None = None,
    ) -> bool:
        statement = select(AssetRelation.relation_id).where(
            AssetRelation.relation_type == relation_type,
            AssetRelation.source_asset_id == source_asset_id,
            AssetRelation.target_asset_id == target_asset_id,
            AssetRelation.source_asset_version_id == source_asset_version_id,
            AssetRelation.target_asset_version_id == target_asset_version_id,
        )
        return self.session.scalar(statement.limit(1)) is not None


def _validate_keyset_position(
    last_created_at: datetime | None, last_id: UUID | None
) -> None:
    if (last_created_at is None) != (last_id is None):
        raise ValueError("keyset position requires both created_at and id")
