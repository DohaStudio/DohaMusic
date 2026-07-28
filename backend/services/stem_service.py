"""Stem separation use cases."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.core.logging import get_logger
from backend.models.stem_file import StemFile
from backend.models.stem_job import StemJob
from backend.repositories.stem_repository import StemRepository
from backend.schemas.stem import StemCreate

logger = get_logger(__name__)


class StemJobDispatcher(Protocol):
    def submit(self, job_id: str) -> None: ...


class StemService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        dispatcher: StemJobDispatcher,
    ) -> None:
        self.session_factory = session_factory
        self.dispatcher = dispatcher

    def create(self, request: StemCreate) -> StemJob:
        started_at = time.perf_counter()
        logger.info("stem_request_started")
        with self.session_factory() as session:
            repository = StemRepository(session)
            if repository.get_source_file(request.source_file_id) is None:
                raise ResourceNotFoundError("분리할 생성 파일")
            job = repository.create(request.source_file_id)
            logger.info("stem_job_created job_id=%s", job.id)
        self.dispatcher.submit(job.id)
        logger.info(
            "stem_request_finished job_id=%s duration_ms=%s",
            job.id,
            round((time.perf_counter() - started_at) * 1_000, 2),
        )
        return job

    def get(self, job_id: str) -> StemJob:
        with self.session_factory() as session:
            job = StemRepository(session).get(job_id)
            if job is None:
                raise ResourceNotFoundError("Stem 분리 작업")
            session.expunge(job)
            return job

    def list_files(self, job_id: str) -> list[StemFile]:
        with self.session_factory() as session:
            repository = StemRepository(session)
            if repository.get(job_id) is None:
                raise ResourceNotFoundError("Stem 분리 작업")
            files = repository.list_files(job_id)
            for stem_file in files:
                session.expunge(stem_file)
            return files
