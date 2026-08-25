"""Draft Voice Enrollment persistence model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.voice_enrollment_status import (
    VoiceCleanupStatus,
    VoiceEnrollmentStatus,
)
from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.voice_profile import VoiceProfile
    from backend.models.voice_sample import VoiceSample


def utc_now() -> datetime:
    return datetime.now(UTC)


class VoiceEnrollment(Base):
    __tablename__ = "voice_enrollments"
    __table_args__ = (
        Index("ix_voice_enrollments_status_expires_at", "status", "expires_at"),
        Index("ix_voice_enrollments_cleanup_status", "cleanup_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    profile_name: Mapped[str] = mapped_column(String(100), nullable=False)
    profile_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VoiceEnrollmentStatus.DRAFT.value
    )
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consent_policy_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    voice_profile_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("voice_profiles.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    absolute_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cleanup_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=VoiceCleanupStatus.NOT_REQUESTED.value
    )
    cleanup_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleanup_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cleanup_failure_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    samples: Mapped[list[VoiceSample]] = relationship(
        back_populates="enrollment", passive_deletes=True
    )
    voice_profile: Mapped[VoiceProfile | None] = relationship(
        back_populates="source_enrollment", foreign_keys=[voice_profile_id]
    )
