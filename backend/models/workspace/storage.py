"""Artifact의 물리 locator를 보존하는 내부 Storage Catalog Entity."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import CreatedAtMixin, utc_now

if TYPE_CHECKING:
    from backend.models.workspace.asset import Artifact


class ArtifactStorageLocation(CreatedAtMixin, Base):
    """Artifact ID와 승인된 Storage root 내부 key를 1:1로 연결한다."""

    __tablename__ = "artifact_storage_locations"
    __table_args__ = (
        CheckConstraint(
            "length(trim(storage_backend)) > 0",
            name="ck_artifact_storage_locations_backend_nonempty",
        ),
        CheckConstraint(
            "storage_domain IN ('lm', 'audio', 'vocal', 'music')",
            name="ck_artifact_storage_locations_domain",
        ),
        CheckConstraint(
            "length(storage_key) > 0",
            name="ck_artifact_storage_locations_key_nonempty",
        ),
        CheckConstraint(
            "locator_version >= 1",
            name="ck_artifact_storage_locations_locator_version",
        ),
        UniqueConstraint(
            "artifact_id",
            name="uq_artifact_storage_locations_artifact",
        ),
        UniqueConstraint(
            "storage_backend",
            "storage_domain",
            "storage_key",
            name="uq_artifact_storage_locations_locator",
        ),
    )

    storage_location_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    artifact_id: Mapped[UUID] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"),
        nullable=False,
    )
    storage_backend: Mapped[str] = mapped_column(
        String, nullable=False, default="local"
    )
    storage_domain: Mapped[str] = mapped_column(String, nullable=False)
    storage_key: Mapped[str] = mapped_column(String, nullable=False)
    locator_version: Mapped[int] = mapped_column(nullable=False, default=1)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    artifact: Mapped[Artifact] = relationship(
        "Artifact", back_populates="storage_location"
    )


ARTIFACT_STORAGE_ENTITY_CLASSES = (ArtifactStorageLocation,)
