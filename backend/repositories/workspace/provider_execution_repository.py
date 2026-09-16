from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.models.workspace.provider_execution import MusicDirectorProviderExecution


class MusicDirectorProviderExecutionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_for_job(self, job_id: UUID) -> MusicDirectorProviderExecution | None:
        return self.session.scalar(
            select(MusicDirectorProviderExecution).where(
                MusicDirectorProviderExecution.job_id == job_id
            )
        )

    def add(self, execution: MusicDirectorProviderExecution) -> MusicDirectorProviderExecution:
        self.session.add(execution)
        self.session.flush()
        return execution

    def bind_external_id(
        self, execution_id: UUID, *, expected_version: int, external_job_id: str
    ) -> MusicDirectorProviderExecution | None:
        statement = (
            update(MusicDirectorProviderExecution)
            .where(
                MusicDirectorProviderExecution.provider_execution_id == execution_id,
                MusicDirectorProviderExecution.version == expected_version,
                MusicDirectorProviderExecution.external_job_id.is_(None),
                MusicDirectorProviderExecution.status == "intended",
            )
            .values(
                external_job_id=external_job_id,
                status="submitted",
                version=MusicDirectorProviderExecution.version + 1,
            )
            .returning(MusicDirectorProviderExecution)
        )
        return self.session.scalars(statement).one_or_none()

    def transition(
        self, execution_id: UUID, *, expected_version: int, from_status: str, to_status: str
    ) -> MusicDirectorProviderExecution | None:
        statement = (
            update(MusicDirectorProviderExecution)
            .where(
                MusicDirectorProviderExecution.provider_execution_id == execution_id,
                MusicDirectorProviderExecution.version == expected_version,
                MusicDirectorProviderExecution.status == from_status,
            )
            .values(status=to_status, version=MusicDirectorProviderExecution.version + 1)
            .returning(MusicDirectorProviderExecution)
        )
        return self.session.scalars(statement).one_or_none()
