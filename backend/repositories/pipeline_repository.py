"""Persistence boundary for pipeline jobs, progress, metadata, and files."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.job_status import ALLOWED_TRANSITIONS, JobStatus
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.models.voice_profile import VoiceProfile
from backend.schemas.pipeline import PipelineCreate


class PipelineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_profile(self, profile_id: str) -> VoiceProfile | None:
        return self.session.get(VoiceProfile, profile_id)

    def create(self, request: PipelineCreate, pipeline_version: str) -> PipelineJob:
        job = PipelineJob(
            **request.model_dump(),
            status=JobStatus.PENDING.value,
            current_step="queued",
            progress_percent=0,
            pipeline_version=pipeline_version,
            result_metadata={},
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: str) -> PipelineJob | None:
        return self.session.get(PipelineJob, job_id)

    def list_files(self, job_id: str) -> list[PipelineFile]:
        statement = (
            select(PipelineFile)
            .where(PipelineFile.job_id == job_id)
            .order_by(PipelineFile.created_at)
        )
        return list(self.session.scalars(statement))

    def get_file(self, file_id: str) -> PipelineFile | None:
        return self.session.get(PipelineFile, file_id)

    def transition(
        self,
        job: PipelineJob,
        target: JobStatus,
        current_step: str,
        progress_percent: int,
    ) -> None:
        current = JobStatus(job.status)
        if target != current and target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(
                f"Invalid job transition: {current.value} -> {target.value}"
            )
        job.status = target.value
        job.current_step = current_step
        job.progress_percent = progress_percent
        job.updated_at = datetime.now(UTC)
        if target == JobStatus.COMPLETED:
            job.completed_at = job.updated_at
        self.session.commit()

    def set_metadata(self, job: PipelineJob, metadata: dict[str, Any]) -> None:
        job.result_metadata = metadata
        self.session.commit()

    def mark_failed(
        self,
        job: PipelineJob,
        code: str,
        message: str,
        failed_step: str | None,
        metadata: dict[str, Any],
    ) -> None:
        job.status = JobStatus.FAILED.value
        job.current_step = "failed"
        job.error_code = code
        job.error_message = message
        job.failed_step = failed_step
        job.result_metadata = metadata
        job.updated_at = datetime.now(UTC)
        job.completed_at = job.updated_at
        self.session.commit()

    def add_file(
        self, job_id: str, file_type: str, file_path: str, mime_type: str
    ) -> PipelineFile:
        item = PipelineFile(
            job_id=job_id,
            file_type=file_type,
            file_path=file_path,
            mime_type=mime_type,
        )
        self.session.add(item)
        self.session.commit()
        self.session.refresh(item)
        return item
