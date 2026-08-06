"""Workspace Job aggregate persistence operations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.workspace.enums import JobStatus
from backend.models.workspace.job import Job, JobInput, JobOutput, ModelUsage


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
