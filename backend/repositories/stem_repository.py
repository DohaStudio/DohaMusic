"""Stem separation job and file persistence operations."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.job_status import ALLOWED_TRANSITIONS, JobStatus
from backend.models.generated_file import GeneratedFile
from backend.models.stem_file import StemFile
from backend.models.stem_job import StemJob


class StemRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_source_file(self, source_file_id: str) -> GeneratedFile | None:
        return self.session.get(GeneratedFile, source_file_id)

    def create(self, source_file_id: str) -> StemJob:
        job = StemJob(
            source_file_id=source_file_id,
            status=JobStatus.PENDING.value,
            current_step="queued",
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: str) -> StemJob | None:
        return self.session.get(StemJob, job_id)

    def list_files(self, job_id: str) -> list[StemFile]:
        statement = (
            select(StemFile)
            .where(StemFile.job_id == job_id)
            .order_by(StemFile.created_at)
        )
        return list(self.session.scalars(statement))

    def transition(
        self,
        job: StemJob,
        target: JobStatus,
        current_step: str,
    ) -> StemJob:
        current = JobStatus(job.status)
        if target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(
                f"Invalid job transition: {current.value} -> {target.value}"
            )
        job.status = target.value
        job.current_step = current_step
        job.updated_at = datetime.now(timezone.utc)
        if target == JobStatus.COMPLETED:
            job.completed_at = job.updated_at
        self.session.commit()
        self.session.refresh(job)
        return job

    def set_model(self, job: StemJob, provider: str, name: str, version: str) -> None:
        job.provider = provider
        job.model_name = name
        job.model_version = version
        self.session.commit()

    def mark_failed(self, job: StemJob, code: str, message: str) -> StemJob:
        if JobStatus(job.status) in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return job
        job.status = JobStatus.FAILED.value
        job.current_step = "failed"
        job.error_code = code
        job.error_message = message
        job.updated_at = datetime.now(timezone.utc)
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
    ) -> StemFile:
        stem_file = StemFile(
            job_id=job_id,
            file_type=file_type,
            file_path=file_path,
            mime_type=mime_type,
        )
        self.session.add(stem_file)
        self.session.commit()
        self.session.refresh(stem_file)
        return stem_file
