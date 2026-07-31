"""Persistent state for one orchestrated AI pipeline execution."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.audio_analysis import public_audio_analysis
from backend.db.base import Base
from backend.kpop.options import public_generation_metadata

if TYPE_CHECKING:
    from backend.models.pipeline_file import PipelineFile
    from backend.models.project import Project


def utc_now() -> datetime:
    return datetime.now(UTC)


class PipelineJob(Base):
    __tablename__ = "pipeline_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    voice_profile_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("voice_profiles.id", ondelete="RESTRICT"), index=True
    )
    project_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="SET NULL"), index=True
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
    cancel_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retry_of_job_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pipeline_jobs.id", ondelete="SET NULL"), index=True
    )
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    files: Mapped[list[PipelineFile]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )
    project: Mapped[Project | None] = relationship(back_populates="jobs")

    @property
    def can_cancel(self) -> bool:
        return self.status in {
            "PENDING",
            "VALIDATING",
            "GENERATING",
            "STEM_SEPARATING",
            "VOICE_CONVERTING",
            "MIXING",
            "EXPORTING",
        }

    @property
    def can_retry(self) -> bool:
        return self.status in {"FAILED", "CANCELLED"}

    @property
    def generation_options(self) -> dict[str, object] | None:
        return public_generation_metadata(self.input_snapshot)[0]

    @property
    def kpop_prompt_compiler_version(self) -> str | None:
        return public_generation_metadata(self.input_snapshot)[1]

    @property
    def audio_analysis(self) -> object | None:
        return public_audio_analysis(self.result_metadata)
