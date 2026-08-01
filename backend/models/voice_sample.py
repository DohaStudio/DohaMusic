"""Individual Voice Sample metadata and lifecycle persistence model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.voice_enrollment_status import VoiceSampleStatus
from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.voice_enrollment import VoiceEnrollment
    from backend.models.voice_profile import VoiceProfile


def utc_now() -> datetime:
    return datetime.now(UTC)


class VoiceSample(Base):
    __tablename__ = "voice_samples"
    __table_args__ = (
        CheckConstraint(
            "enrollment_id IS NOT NULL OR voice_profile_id IS NOT NULL",
            name="ck_voice_samples_has_owner",
        ),
        Index("ix_voice_samples_enrollment_id_status", "enrollment_id", "status"),
        Index("ix_voice_samples_voice_profile_id_status", "voice_profile_id", "status"),
        Index("ix_voice_samples_status_expires_at", "status", "expires_at"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    enrollment_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("voice_enrollments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    voice_profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("voice_profiles.id", ondelete="RESTRICT"),
        nullable=True,
    )
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VoiceSampleStatus.UPLOADED.value
    )
    original_content_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    original_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    original_storage_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    normalized_content_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    normalized_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    normalized_storage_path: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bit_depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    quality_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    quality_warnings: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    quality_metrics: Mapped[dict[str, float | str]] = mapped_column(
        JSON, nullable=False, default=dict
    )
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    promoted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    delete_failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    enrollment: Mapped[VoiceEnrollment | None] = relationship(
        back_populates="samples", foreign_keys=[enrollment_id]
    )
    voice_profile: Mapped[VoiceProfile | None] = relationship(
        back_populates="samples", foreign_keys=[voice_profile_id]
    )
