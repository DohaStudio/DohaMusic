"""Mock generation worker with explicit job state transitions."""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.ai.interfaces.music_generator import GenerationInput, MusicGenerator
from backend.core.job_status import JobStatus
from backend.core.logging import get_logger
from backend.repositories.generation_repository import GenerationRepository
from backend.storage.service import StorageService

logger = get_logger(__name__)


class MockGenerationWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        music_generator: MusicGenerator,
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.music_generator = music_generator
        self.storage = storage

    def run(self, job_id: str) -> None:
        started_at = time.perf_counter()
        logger.info("worker_started job_id=%s", job_id)
        with self.session_factory() as session:
            repository = GenerationRepository(session)
            job = repository.get(job_id)
            if job is None:
                logger.error("worker_job_not_found job_id=%s", job_id)
                return
            try:
                repository.transition(job, JobStatus.VALIDATING, "validating_request")
                request = GenerationInput(
                    job_id=job.id,
                    prompt=job.prompt,
                    lyrics=job.lyrics,
                    genre=job.genre,
                    duration_seconds=job.duration_seconds,
                    seed=job.seed,
                )
                repository.transition(job, JobStatus.GENERATING, "mock_generation")
                model_name = getattr(
                    self.music_generator, "model_name", "configured-adapter"
                )
                logger.info(
                    "inference_started job_id=%s model=%s",
                    job_id,
                    model_name,
                )
                output_file = self.music_generator.generate(request)
                logger.info(
                    "inference_finished job_id=%s model=%s",
                    job_id,
                    model_name,
                )
                repository.add_file(
                    job_id=job.id,
                    file_type="mock_audio",
                    file_path=self.storage.relative_path(output_file),
                    mime_type="audio/wav",
                )
                repository.transition(job, JobStatus.COMPLETED, "completed")
                logger.info("worker_completed job_id=%s", job_id)
            except Exception:
                logger.exception("worker_failed job_id=%s", job_id)
                session.rollback()
                repository.mark_failed(
                    job,
                    code="MOCK_GENERATION_FAILED",
                    message="Mock 생성 작업에 실패했습니다.",
                )
            finally:
                elapsed_ms = round((time.perf_counter() - started_at) * 1_000, 2)
                logger.info(
                    "worker_finished job_id=%s duration_ms=%s", job_id, elapsed_ms
                )
