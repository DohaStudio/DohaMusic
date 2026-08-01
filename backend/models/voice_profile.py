"""Consent-gated voice profile persistence model."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.voice_enrollment import VoiceEnrollment
    from backend.models.voice_sample import VoiceSample


class VoiceProfile(Base):
    __tablename__ = "voice_profiles"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_rate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    channels: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="READY")
    quality_warnings: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list
    )
    consent_text_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    consent_confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_reference_sample_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("voice_samples.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    samples: Mapped[list[VoiceSample]] = relationship(
        back_populates="voice_profile",
        foreign_keys="VoiceSample.voice_profile_id",
        passive_deletes=True,
    )
    active_reference_sample: Mapped[VoiceSample | None] = relationship(
        foreign_keys=[active_reference_sample_id], post_update=True
    )
    source_enrollment: Mapped[VoiceEnrollment | None] = relationship(
        back_populates="voice_profile",
        foreign_keys="VoiceEnrollment.voice_profile_id",
        uselist=False,
    )
