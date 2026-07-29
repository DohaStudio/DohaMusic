"""Persistent state for one orchestrated AI pipeline execution."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base

if TYPE_CHECKING:
    from backend.models.pipeline_file import PipelineFile


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    voice_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("voice_profiles.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_step: Mapped[str] = mapped_column(String(100), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    lyrics: Mapped[str | None] = mapped_column(Text, nullable=True)
    genre: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pipeline_version: Mapped[str] = mapped_column(String(50), nullable=False)
    result_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    failed_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    files: Mapped[list["PipelineFile"]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
