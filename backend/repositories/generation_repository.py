"""Generation job and file persistence operations."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.job_status import ALLOWED_TRANSITIONS, JobStatus
from backend.models.generated_file import GeneratedFile
from backend.models.generation_job import GenerationJob
from backend.schemas.generation import GenerationCreate


class GenerationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, request: GenerationCreate) -> GenerationJob:
        job = GenerationJob(
            status=JobStatus.PENDING.value,
            current_step="queued",
            **request.model_dump(),
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: str) -> GenerationJob | None:
        return self.session.get(GenerationJob, job_id)

    def list_files(self, job_id: str) -> list[GeneratedFile]:
        statement = (
            select(GeneratedFile)
            .where(GeneratedFile.job_id == job_id)
            .order_by(GeneratedFile.created_at)
        )
        return list(self.session.scalars(statement))

    def transition(
        self,
        job: GenerationJob,
        target: JobStatus,
        current_step: str,
    ) -> GenerationJob:
        current = JobStatus(job.status)
        if target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"Invalid job transition: {current.value} -> {target.value}")
        job.status = target.value
        job.current_step = current_step
        job.updated_at = datetime.now(UTC)
        if target == JobStatus.COMPLETED:
            job.completed_at = job.updated_at
        self.session.commit()
        self.session.refresh(job)
        return job

    def mark_failed(self, job: GenerationJob, code: str, message: str) -> GenerationJob:
        if JobStatus(job.status) in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return job
        job.status = JobStatus.FAILED.value
        job.current_step = "failed"
        job.error_code = code
        job.error_message = message
        job.updated_at = datetime.now(UTC)
        job.completed_at = job.updated_at
        self.session.commit()
        self.session.refresh(job)
        return job

    def add_file(
        self,
        job_id: str,
        file_type: str,
        file_path: str,
        mime_type: str,
    ) -> GeneratedFile:
        generated_file = GeneratedFile(
            job_id=job_id,
            file_type=file_type,
            file_path=file_path,
            mime_type=mime_type,
        )
        self.session.add(generated_file)
        self.session.commit()
        self.session.refresh(generated_file)
        return generated_file
