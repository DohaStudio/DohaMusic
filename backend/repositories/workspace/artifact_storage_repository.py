"""Artifact Storage Catalog의 읽기 전용 Repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.storage import ArtifactStorageLocation


class ArtifactStorageRepository:
    """Catalog persistence만 수행하고 transaction과 filesystem을 소유하지 않는다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_storage_location(self, artifact_id: UUID) -> ArtifactStorageLocation | None:
        statement = select(ArtifactStorageLocation).where(
            ArtifactStorageLocation.artifact_id == artifact_id
        )
        return self.session.scalar(statement)

    def get_storage_location_by_locator(
        self,
        *,
        storage_backend: str,
        storage_domain: str,
        storage_key: str,
    ) -> ArtifactStorageLocation | None:
        statement = select(ArtifactStorageLocation).where(
            ArtifactStorageLocation.storage_backend == storage_backend,
            ArtifactStorageLocation.storage_domain == storage_domain,
            ArtifactStorageLocation.storage_key == storage_key,
        )
        return self.session.scalar(statement)

    def list_storage_locations_batch(
        self,
        *,
        after_id: UUID | None = None,
        limit: int = 100,
    ) -> list[ArtifactStorageLocation]:
        """전체 Catalog를 적재하지 않는 UUID keyset batch 조회."""

        statement = select(ArtifactStorageLocation)
        if after_id is not None:
            statement = statement.where(ArtifactStorageLocation.storage_location_id > after_id)
        statement = statement.order_by(ArtifactStorageLocation.storage_location_id).limit(limit)
        return list(self.session.scalars(statement))

    def add_storage_location(self, location: ArtifactStorageLocation) -> ArtifactStorageLocation:
        self.session.add(location)
        self.session.flush()
        return location
