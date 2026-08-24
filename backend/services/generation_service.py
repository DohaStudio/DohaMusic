"""Generation use cases."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.core.logging import get_logger
from backend.models.generated_file import GeneratedFile
from backend.models.generation_job import GenerationJob
from backend.repositories.generation_repository import GenerationRepository
from backend.schemas.generation import GenerationCreate

logger = get_logger(__name__)


class JobDispatcher(Protocol):
    def submit(self, job_id: str) -> None: ...


class GenerationService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        dispatcher: JobDispatcher,
    ) -> None:
        self.session_factory = session_factory
        self.dispatcher = dispatcher

    def create(self, request: GenerationCreate) -> GenerationJob:
        started_at = time.perf_counter()
        logger.info("generation_request_started")
        with self.session_factory() as session:
            job = GenerationRepository(session).create(request)
            logger.info("generation_job_created job_id=%s", job.id)
        self.dispatcher.submit(job.id)
        elapsed_ms = round((time.perf_counter() - started_at) * 1_000, 2)
        logger.info("generation_request_finished job_id=%s duration_ms=%s", job.id, elapsed_ms)
        return job

    def get(self, job_id: str) -> GenerationJob:
        with self.session_factory() as session:
            job = GenerationRepository(session).get(job_id)
            if job is None:
                raise ResourceNotFoundError("생성 작업")
            session.expunge(job)
            return job

    def list_files(self, job_id: str) -> list[GeneratedFile]:
        with self.session_factory() as session:
            repository = GenerationRepository(session)
            if repository.get(job_id) is None:
                raise ResourceNotFoundError("생성 작업")
            files = repository.list_files(job_id)
            for generated_file in files:
                session.expunge(generated_file)
            return files
