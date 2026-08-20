"""Provider Job binding persistence operations."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.provider_job import ProviderJobBinding


class ProviderJobRepository:
    """Commit하지 않고 현재 transaction에 binding 변경을 반영한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_binding(self, binding: ProviderJobBinding) -> ProviderJobBinding:
        self.session.add(binding)
        self.session.flush()
        return binding

    def get_by_id(self, binding_id: UUID) -> ProviderJobBinding | None:
        return self.session.get(ProviderJobBinding, binding_id)

    def get_by_provider_identity(
        self, provider_id: str, provider_job_id: str
    ) -> ProviderJobBinding | None:
        return self.session.scalar(
            select(ProviderJobBinding).where(
                ProviderJobBinding.provider_id == provider_id,
                ProviderJobBinding.provider_job_id == provider_job_id,
            )
        )

    def find_by_provider_job_id(
        self, provider_job_id: str, *, limit: int = 2
    ) -> list[ProviderJobBinding]:
        statement = (
            select(ProviderJobBinding)
            .where(ProviderJobBinding.provider_job_id == provider_job_id)
            .order_by(ProviderJobBinding.provider_id)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_by_workspace_job(
        self, workspace_job_id: UUID, *, limit: int = 100
    ) -> list[ProviderJobBinding]:
        statement = (
            select(ProviderJobBinding)
            .where(ProviderJobBinding.workspace_job_id == workspace_job_id)
            .order_by(
                ProviderJobBinding.created_at,
                ProviderJobBinding.provider_job_binding_id,
            )
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def get_latest_for_workspace_job(
        self, workspace_job_id: UUID
    ) -> ProviderJobBinding | None:
        statement = (
            select(ProviderJobBinding)
            .where(ProviderJobBinding.workspace_job_id == workspace_job_id)
            .order_by(
                ProviderJobBinding.created_at.desc(),
                ProviderJobBinding.provider_job_binding_id.desc(),
            )
            .limit(1)
        )
        return self.session.scalar(statement)
