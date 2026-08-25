"""Workspace Job과 외부 Provider Job 사이의 불변 실행 이력."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.db.base import Base
from backend.models.workspace.identifiers import generate_uuid
from backend.models.workspace.mixins import CreatedAtMixin

if TYPE_CHECKING:
    from backend.models.workspace.job import Job
    from backend.models.workspace.payload_locator import PayloadLocator


class ProviderJobBinding(CreatedAtMixin, Base):
    """Provider 실행 identity를 Workspace Job에 영속적으로 결합한다."""

    __tablename__ = "provider_job_bindings"
    __table_args__ = (
        UniqueConstraint(
            "provider_id",
            "provider_job_id",
            name="uq_provider_job_bindings_identity",
        ),
        ForeignKeyConstraint(
            ["provider_id", "retry_of_provider_job_id"],
            [
                "provider_job_bindings.provider_id",
                "provider_job_bindings.provider_job_id",
            ],
            name="fk_provider_job_bindings_retry_identity",
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "retry_of_provider_job_id IS NULL "
            "OR retry_of_provider_job_id <> provider_job_id",
            name="ck_provider_job_bindings_no_self_retry",
        ),
        Index(
            "ix_provider_job_bindings_workspace_history",
            "workspace_job_id",
            "created_at",
            "provider_job_binding_id",
        ),
        Index(
            "ix_provider_job_bindings_provider_job_id",
            "provider_job_id",
        ),
        Index(
            "uq_provider_job_bindings_workspace_identity",
            "workspace_job_id",
            "provider_job_binding_id",
            unique=True,
        ),
    )

    provider_job_binding_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=generate_uuid
    )
    workspace_job_id: Mapped[UUID] = mapped_column(
        ForeignKey("jobs.job_id", ondelete="RESTRICT"), nullable=False
    )
    provider_id: Mapped[str] = mapped_column(String(128), nullable=False)
    provider_job_id: Mapped[str] = mapped_column(String(256), nullable=False)
    retry_of_provider_job_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )

    workspace_job: Mapped[Job] = relationship(back_populates="provider_job_bindings")
    payload_locators: Mapped[list[PayloadLocator]] = relationship(
        back_populates="provider_job_binding",
        overlaps="payload_locators,workspace_job",
    )
