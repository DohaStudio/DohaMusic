"""Artifact Storage Catalog의 읽기 전용 Repository."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.storage import ArtifactStorageLocation


class ArtifactStorageRepository:
    """Catalog 조회만 수행하고 transaction과 filesystem을 소유하지 않는다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_storage_location(self, artifact_id: UUID) -> ArtifactStorageLocation | None:
        statement = select(ArtifactStorageLocation).where(
            ArtifactStorageLocation.artifact_id == artifact_id
        )
        return self.session.scalar(statement)
