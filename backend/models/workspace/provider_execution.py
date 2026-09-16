from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import TimestampMixin

if TYPE_CHECKING:
    from backend.models.workspace.job import Job


class MusicDirectorProviderExecutionStatus(StrEnum):
    INTENDED = "intended"
    SUBMITTED = "submitted"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECONCILIATION_REQUIRED = "reconciliation_required"


class MusicDirectorProviderExecution(TimestampMixin, Base):
    __tablename__ = "music_director_provider_executions"
    __table_args__ = (
        UniqueConstraint("job_id", name="uq_music_director_provider_executions_job"),
        UniqueConstraint(
            "client_execution_key", name="uq_music_director_provider_executions_client_key"
        ),
        UniqueConstraint(
            "provider_id",
            "external_job_id",
            name="uq_music_director_provider_executions_external_identity",
        ),
        CheckConstraint("version >= 0", name="ck_music_director_provider_executions_version"),
        Index(
            "ix_music_director_provider_executions_recovery",
            "status",
            "updated_at",
            "provider_execution_id",
        ),
    )

    provider_execution_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    model_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    client_execution_key: Mapped[str] = mapped_column(String(64), nullable=False)
    external_job_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    job: Mapped[Job] = relationship(back_populates="music_director_provider_executions")
