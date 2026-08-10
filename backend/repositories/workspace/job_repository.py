"""Workspace Job aggregate persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.models.workspace.enums import JobStatus
from backend.models.workspace.job import Job, JobInput, JobOutput, ModelUsage
from backend.models.workspace.workspace import Workspace


class JobRepository:
    """Workspace Job aggregate를 commit 없이 현재 transaction에 반영한다."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def add_job(self, job: Job) -> Job:
        self.session.add(job)
        self.session.flush()
        return job

    def get_job(self, job_id: UUID) -> Job | None:
        return self.session.get(Job, job_id)

    def get_job_for_owner(self, job_id: UUID, owner_id: UUID) -> Job | None:
        """Owner 범위를 벗어난 Job의 존재를 노출하지 않고 조회한다."""

        statement = (
            select(Job)
            .join(Workspace, Workspace.workspace_id == Job.workspace_id)
            .where(
                Job.job_id == job_id,
                Workspace.owner_id == owner_id,
                Workspace.deleted_at.is_(None),
            )
        )
        return self.session.scalar(statement)

    def list_jobs(self, *, limit: int = 100, offset: int = 0) -> list[Job]:
        statement = (
            select(Job)
            .order_by(Job.created_at.desc(), Job.job_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_project_jobs(
        self, project_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Job]:
        statement = (
            select(Job)
            .where(Job.project_id == project_id)
            .order_by(Job.created_at.desc(), Job.job_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_jobs_by_status(
        self, status: JobStatus, *, limit: int = 100, offset: int = 0
    ) -> list[Job]:
        statement = (
            select(Job)
            .where(Job.status == status)
            .order_by(Job.created_at, Job.job_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def list_jobs_after(
        self,
        *,
        owner_id: UUID,
        workspace_id: UUID,
        project_id: UUID | None = None,
        status: JobStatus | None = None,
        job_type: str | None = None,
        last_created_at: datetime | None = None,
        last_id: UUID | None = None,
        limit: int = 100,
    ) -> list[Job]:
        """Owner·Workspace scope의 Job을 DESC keyset으로 조회한다."""

        statement = _build_list_jobs_after_statement(
            owner_id=owner_id,
            workspace_id=workspace_id,
            project_id=project_id,
            status=status,
            job_type=job_type,
            last_created_at=last_created_at,
            last_id=last_id,
            limit=limit,
        )
        return list(self.session.scalars(statement))

    def update_job_status(
        self,
        job: Job,
        status: JobStatus,
        *,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> Job:
        job.status = status
        if started_at is not None:
            job.started_at = started_at
        if completed_at is not None:
            job.completed_at = completed_at
        self.session.flush()
        return job

    def add_job_input(self, item: JobInput) -> JobInput:
        self.session.add(item)
        self.session.flush()
        return item

    def list_job_inputs(
        self, job_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[JobInput]:
        statement = (
            select(JobInput)
            .where(JobInput.job_id == job_id)
            .order_by(JobInput.input_order, JobInput.job_input_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def job_input_order_exists(self, job_id: UUID, input_order: int) -> bool:
        statement = select(JobInput.job_input_id).where(
            JobInput.job_id == job_id,
            JobInput.input_order == input_order,
        )
        return self.session.scalar(statement.limit(1)) is not None

    def add_job_output(self, item: JobOutput) -> JobOutput:
        self.session.add(item)
        self.session.flush()
        return item

    def list_job_outputs(
        self, job_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[JobOutput]:
        statement = (
            select(JobOutput)
            .where(JobOutput.job_id == job_id)
            .order_by(JobOutput.output_order, JobOutput.job_output_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def job_output_order_exists(self, job_id: UUID, output_order: int) -> bool:
        statement = select(JobOutput.job_output_id).where(
            JobOutput.job_id == job_id,
            JobOutput.output_order == output_order,
        )
        return self.session.scalar(statement.limit(1)) is not None

    def add_model_usage(self, usage: ModelUsage) -> ModelUsage:
        self.session.add(usage)
        self.session.flush()
        return usage

    def list_model_usages(
        self, job_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[ModelUsage]:
        statement = (
            select(ModelUsage)
            .where(ModelUsage.job_id == job_id)
            .order_by(ModelUsage.created_at, ModelUsage.model_usage_id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))


def _build_list_jobs_after_statement(
    *,
    owner_id: UUID,
    workspace_id: UUID,
    project_id: UUID | None = None,
    status: JobStatus | None = None,
    job_type: str | None = None,
    last_created_at: datetime | None = None,
    last_id: UUID | None = None,
    limit: int = 100,
):
    """Repository 실행과 Query Plan 검증이 공유하는 단일 statement를 만든다."""

    _validate_keyset_position(last_created_at, last_id)
    statement = (
        select(Job)
        .join(Workspace, Workspace.workspace_id == Job.workspace_id)
        .where(
            Workspace.owner_id == owner_id,
            Workspace.workspace_id == workspace_id,
            Workspace.deleted_at.is_(None),
            Job.workspace_id == workspace_id,
        )
    )
    if project_id is not None:
        statement = statement.where(Job.project_id == project_id)
    if status is not None:
        statement = statement.where(Job.status == status)
    if job_type is not None:
        statement = statement.where(Job.job_type == job_type)
    if last_created_at is not None and last_id is not None:
        statement = statement.where(
            or_(
                Job.created_at < last_created_at,
                and_(
                    Job.created_at == last_created_at,
                    Job.job_id < last_id,
                ),
            )
        )
    return statement.order_by(Job.created_at.desc(), Job.job_id.desc()).limit(limit)


def _validate_keyset_position(
    last_created_at: datetime | None, last_id: UUID | None
) -> None:
    if (last_created_at is None) != (last_id is None):
        raise ValueError("keyset position requires both created_at and id")
