"""Durable Provider payload reconciliation lifecycle persistence model."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.payload_locator import PayloadLocatorStatus
from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import TimestampMixin

if TYPE_CHECKING:
    from backend.models.workspace.asset import Artifact
    from backend.models.workspace.job import Job
    from backend.models.workspace.provider_job import ProviderJobBinding


class PayloadLocator(TimestampMixin, Base):
    """Source identity and verified staging handoff for one ordered payload."""

    __tablename__ = "payload_locators"
    __table_args__ = (
        UniqueConstraint(
            "provider_job_binding_id",
            "payload_ordinal",
            name="uq_payload_locators_binding_ordinal",
        ),
        UniqueConstraint(
            "provider_job_binding_id",
            "provider_artifact_id",
            "role",
            "source_id",
            name="uq_payload_locators_source_identity",
        ),
        ForeignKeyConstraint(
            ["workspace_job_id", "provider_job_binding_id"],
            [
                "provider_job_bindings.workspace_job_id",
                "provider_job_bindings.provider_job_binding_id",
            ],
            name="fk_payload_locators_binding_scope",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "payload_ordinal >= 0", name="ck_payload_locators_ordinal_nonnegative"
        ),
        CheckConstraint(
            "expected_checksum_algorithm = 'sha256' "
            "AND length(expected_payload_checksum) = 64 "
            "AND expected_size_bytes > 0",
            name="ck_payload_locators_expected_integrity",
        ),
        CheckConstraint(
            "lifecycle_revision >= 0",
            name="ck_payload_locators_revision_nonnegative",
        ),
        CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="ck_payload_locators_revocation_pair",
        ),
        CheckConstraint(
            "(staging_status = 'source_bound' AND staging_backend IS NULL "
            "AND staging_key IS NULL AND actual_checksum_algorithm IS NULL "
            "AND actual_payload_checksum IS NULL AND actual_size_bytes IS NULL "
            "AND actual_media_type IS NULL AND verified_at IS NULL "
            "AND ingested_artifact_id IS NULL AND ingested_at IS NULL "
            "AND cleanup_requested_at IS NULL AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'verified_staged' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ingested_artifact_id IS NULL AND ingested_at IS NULL "
            "AND cleanup_requested_at IS NULL AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'ingested' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ingested_artifact_id IS NOT NULL AND ingested_at IS NOT NULL "
            "AND cleanup_requested_at IS NULL AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'cleanup_pending' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ((ingested_artifact_id IS NULL AND ingested_at IS NULL) OR "
            "(ingested_artifact_id IS NOT NULL AND ingested_at IS NOT NULL)) "
            "AND cleanup_requested_at IS NOT NULL "
            "AND cleanup_completed_at IS NULL) OR "
            "(staging_status = 'cleaned' AND staging_backend IS NOT NULL "
            "AND staging_key IS NOT NULL AND actual_checksum_algorithm = 'sha256' "
            "AND length(actual_payload_checksum) = 64 AND actual_size_bytes > 0 "
            "AND actual_media_type IS NOT NULL AND verified_at IS NOT NULL "
            "AND ((ingested_artifact_id IS NULL AND ingested_at IS NULL) OR "
            "(ingested_artifact_id IS NOT NULL AND ingested_at IS NOT NULL)) "
            "AND cleanup_requested_at IS NOT NULL "
            "AND cleanup_completed_at IS NOT NULL)",
            name="ck_payload_locators_lifecycle_facts",
        ),
        Index(
            "ix_payload_locators_binding_history",
            "provider_job_binding_id",
            "payload_ordinal",
            "created_at",
        ),
        Index(
            "ix_payload_locators_cleanup_scan",
            "staging_status",
            "cleanup_requested_at",
        ),
        Index("ix_payload_locators_source_expiry", "source_available_until"),
        Index("ix_payload_locators_policy_expiry", "locator_expires_at"),
        Index("ix_payload_locators_ingested_artifact", "ingested_artifact_id"),
    )

    payload_locator_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    workspace_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    provider_job_binding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), nullable=False
    )
    payload_ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    provider_artifact_id: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(200), nullable=False)
    artifact_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    expected_checksum_algorithm: Mapped[str] = mapped_column(String(16), nullable=False)
    expected_payload_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    expected_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_media_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_available_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locator_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    staging_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=PayloadLocatorStatus.SOURCE_BOUND.value
    )
    staging_backend: Mapped[str | None] = mapped_column(String(32), nullable=True)
    staging_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    actual_checksum_algorithm: Mapped[str | None] = mapped_column(
        String(16), nullable=True
    )
    actual_payload_checksum: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    actual_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    actual_media_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ingested_artifact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("artifacts.artifact_id", ondelete="RESTRICT"), nullable=True
    )
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revocation_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cleanup_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleanup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lifecycle_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    workspace_job: Mapped[Job] = relationship(
        back_populates="payload_locators",
        foreign_keys=[workspace_job_id],
    )
    provider_job_binding: Mapped[ProviderJobBinding] = relationship(
        back_populates="payload_locators",
        overlaps="payload_locators,workspace_job",
    )
    ingested_artifact: Mapped[Artifact | None] = relationship(
        back_populates="payload_locators"
    )
