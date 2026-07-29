"""Pipeline orchestration use cases."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, ResourceNotFoundError
from backend.core.logging import get_logger
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.repositories.pipeline_repository import PipelineRepository
from backend.schemas.pipeline import PipelineCreate

logger = get_logger(__name__)


class PipelineDispatcher(Protocol):
    def submit(self, job_id: str) -> None: ...


class PipelineService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        dispatcher: PipelineDispatcher,
        pipeline_version: str,
    ) -> None:
        self.session_factory = session_factory
        self.dispatcher = dispatcher
        self.pipeline_version = pipeline_version

    def create(self, request: PipelineCreate) -> PipelineJob:
        logger.info("pipeline_request_started")
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            profile = repository.get_profile(request.voice_profile_id)
            if profile is None:
                raise ResourceNotFoundError("음성 프로필")
            if not profile.consent_confirmed:
                raise AppError(
                    "VOICE_CONSENT_REQUIRED", "음성 사용 동의가 필요합니다.", 400
                )
            job = repository.create(request, self.pipeline_version)
            logger.info("pipeline_job_created job_id=%s", job.id)
            session.expunge(job)
        self.dispatcher.submit(job.id)
        return job

    def get(self, job_id: str) -> PipelineJob:
        with self.session_factory() as session:
            job = PipelineRepository(session).get(job_id)
            if job is None:
                raise ResourceNotFoundError("Pipeline 작업")
            session.expunge(job)
            return job

    def list_files(self, job_id: str) -> list[PipelineFile]:
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            if repository.get(job_id) is None:
                raise ResourceNotFoundError("Pipeline 작업")
            files = repository.list_files(job_id)
            for item in files:
                session.expunge(item)
            return files
