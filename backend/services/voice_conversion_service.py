"""Voice conversion use cases."""

from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.models.voice_conversion_file import VoiceConversionFile
from backend.models.voice_conversion_job import VoiceConversionJob
from backend.repositories.voice_conversion_repository import VoiceConversionRepository
from backend.schemas.voice_conversion import VoiceConversionCreate


class VoiceConversionDispatcher(Protocol):
    def submit(self, job_id: str) -> None: ...


class VoiceConversionService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        dispatcher: VoiceConversionDispatcher,
    ) -> None:
        self.session_factory = session_factory
        self.dispatcher = dispatcher

    def create(self, request: VoiceConversionCreate) -> VoiceConversionJob:
        with self.session_factory() as session:
            repository = VoiceConversionRepository(session)
            source = repository.get_source_file(request.source_file_id)
            if source is None or source.file_type != "vocals":
                raise ResourceNotFoundError("변환할 보컬 파일")
            profile = repository.get_profile(request.voice_profile_id)
            if profile is None or not profile.consent_confirmed:
                raise ResourceNotFoundError("동의가 확인된 음성 프로필")
            job = repository.create(request.source_file_id, request.voice_profile_id)
        self.dispatcher.submit(job.id)
        return job

    def get(self, job_id: str) -> VoiceConversionJob:
        with self.session_factory() as session:
            job = VoiceConversionRepository(session).get(job_id)
            if job is None:
                raise ResourceNotFoundError("Voice Conversion 작업")
            session.expunge(job)
            return job

    def list_files(self, job_id: str) -> list[VoiceConversionFile]:
        with self.session_factory() as session:
            repository = VoiceConversionRepository(session)
            if repository.get(job_id) is None:
                raise ResourceNotFoundError("Voice Conversion 작업")
            files = repository.list_files(job_id)
            for item in files:
                session.expunge(item)
            return files
