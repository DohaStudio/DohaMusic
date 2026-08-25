"""Persistence boundary for pipeline jobs, progress, metadata, and files."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.core.job_status import ALLOWED_TRANSITIONS, JobStatus
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.models.voice_profile import VoiceProfile
from backend.repositories.history_repository import HistoryRepository
from backend.schemas.pipeline import PipelineCreate


class PipelineRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_profile(self, profile_id: str) -> VoiceProfile | None:
        return self.session.get(VoiceProfile, profile_id)

    def create(
        self,
        request: PipelineCreate,
        pipeline_version: str,
        *,
        retry_of_job_id: str | None = None,
        input_snapshot: dict[str, Any] | None = None,
    ) -> PipelineJob:
        project_id = request.project_id
        if project_id is None:
            project_id = HistoryRepository(self.session).get_or_create_default_project().id
        job = PipelineJob(
            **request.model_dump(exclude={"project_id", "generation_options"}),
            project_id=project_id,
            status=JobStatus.PENDING.value,
            current_step="queued",
            progress_percent=0,
            pipeline_version=pipeline_version,
            result_metadata={},
            retry_of_job_id=retry_of_job_id,
            input_snapshot=input_snapshot or request.model_dump(mode="json"),
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def retry_for(self, source_job_id: str) -> PipelineJob | None:
        return self.session.scalar(
            select(PipelineJob)
            .where(PipelineJob.retry_of_job_id == source_job_id)
            .order_by(PipelineJob.created_at.desc())
        )

    def request_cancel(self, job: PipelineJob) -> PipelineJob:
        now = datetime.now(UTC)
        if job.status == JobStatus.PENDING.value:
            job.status = JobStatus.CANCELLED.value
            job.current_step = "cancelled"
            job.cancel_requested_at = now
            job.cancelled_at = now
            job.completed_at = now
        elif job.status not in {
            JobStatus.CANCEL_REQUESTED.value,
            JobStatus.CANCELLED.value,
        }:
            job.status = JobStatus.CANCEL_REQUESTED.value
            job.current_step = "cancel_requested"
            job.cancel_requested_at = now
        self.session.commit()
        self.session.refresh(job)
        return job

    def mark_cancelled(self, job: PipelineJob) -> None:
        now = datetime.now(UTC)
        job.status = JobStatus.CANCELLED.value
        job.current_step = "cancelled"
        job.cancel_requested_at = job.cancel_requested_at or now
        job.cancelled_at = now
        job.completed_at = now
        job.progress_percent = min(job.progress_percent, 99)
        job.updated_at = now
        self.session.commit()

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
            raise ValueError(f"Invalid job transition: {current.value} -> {target.value}")
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

    def finalize_success(
        self,
        job: PipelineJob,
        metadata: dict[str, Any],
        files: list[tuple[str, str, str]],
    ) -> bool:
        now = datetime.now(UTC)
        result = self.session.execute(
            update(PipelineJob)
            .where(
                PipelineJob.id == job.id,
                PipelineJob.status.not_in(
                    [
                        JobStatus.CANCEL_REQUESTED.value,
                        JobStatus.CANCELLED.value,
                        JobStatus.COMPLETED.value,
                        JobStatus.FAILED.value,
                    ]
                ),
            )
            .values(
                status=JobStatus.COMPLETED.value,
                current_step="completed",
                progress_percent=100,
                result_metadata=metadata,
                updated_at=now,
                completed_at=now,
            )
        )
        if result.rowcount != 1:
            self.session.rollback()
            return False
        self.session.add_all(
            [
                PipelineFile(
                    job_id=job.id,
                    file_type=file_type,
                    file_path=file_path,
                    mime_type=mime_type,
                )
                for file_type, file_path, mime_type in files
            ]
        )
        self.session.commit()
        self.session.refresh(job)
        return True

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

    def add_file(self, job_id: str, file_type: str, file_path: str, mime_type: str) -> PipelineFile:
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
