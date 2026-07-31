"""Voice conversion persistence operations."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.job_status import ALLOWED_TRANSITIONS, JobStatus
from backend.models.stem_file import StemFile
from backend.models.voice_conversion_file import VoiceConversionFile
from backend.models.voice_conversion_job import VoiceConversionJob
from backend.models.voice_profile import VoiceProfile


class VoiceConversionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_source_file(self, file_id: str) -> StemFile | None:
        return self.session.get(StemFile, file_id)

    def get_profile(self, profile_id: str) -> VoiceProfile | None:
        return self.session.get(VoiceProfile, profile_id)

    def create(self, source_file_id: str, voice_profile_id: str) -> VoiceConversionJob:
        job = VoiceConversionJob(
            source_file_id=source_file_id,
            voice_profile_id=voice_profile_id,
            status=JobStatus.PENDING.value,
            current_step="queued",
        )
        self.session.add(job)
        self.session.commit()
        self.session.refresh(job)
        return job

    def get(self, job_id: str) -> VoiceConversionJob | None:
        return self.session.get(VoiceConversionJob, job_id)

    def list_files(self, job_id: str) -> list[VoiceConversionFile]:
        statement = (
            select(VoiceConversionFile)
            .where(VoiceConversionFile.job_id == job_id)
            .order_by(VoiceConversionFile.created_at)
        )
        return list(self.session.scalars(statement))

    def transition(
        self, job: VoiceConversionJob, target: JobStatus, current_step: str
    ) -> VoiceConversionJob:
        current = JobStatus(job.status)
        if target not in ALLOWED_TRANSITIONS[current]:
            raise ValueError(
                f"Invalid job transition: {current.value} -> {target.value}"
            )
        job.status = target.value
        job.current_step = current_step
        job.updated_at = datetime.now(UTC)
        if target == JobStatus.COMPLETED:
            job.completed_at = job.updated_at
        self.session.commit()
        self.session.refresh(job)
        return job

    def set_model(
        self, job: VoiceConversionJob, provider: str, name: str, version: str
    ) -> None:
        job.provider = provider
        job.model_name = name
        job.model_version = version
        self.session.commit()

    def mark_failed(self, job: VoiceConversionJob, code: str, message: str) -> None:
        if JobStatus(job.status) in {JobStatus.COMPLETED, JobStatus.FAILED}:
            return
        job.status = JobStatus.FAILED.value
        job.current_step = "failed"
        job.error_code = code
        job.error_message = message
        job.updated_at = datetime.now(UTC)
        job.completed_at = job.updated_at
        self.session.commit()

    def add_file(
        self, job_id: str, file_type: str, file_path: str, mime_type: str
    ) -> None:
        self.session.add(
            VoiceConversionFile(
                job_id=job_id,
                file_type=file_type,
                file_path=file_path,
                mime_type=mime_type,
            )
        )
        self.session.commit()
