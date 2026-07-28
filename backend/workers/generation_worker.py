"""Provider-neutral generation worker with explicit job state transitions."""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.ai.interfaces.music_generator import GenerationInput, MusicGenerator
from backend.ai.errors import MusicGenerationError
from backend.core.job_status import JobStatus
from backend.core.logging import get_logger
from backend.repositories.generation_repository import GenerationRepository
from backend.storage.service import StorageService

logger = get_logger(__name__)


class GenerationWorker:
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
                repository.transition(job, JobStatus.GENERATING, "generation_started")
                model_name = getattr(
                    self.music_generator, "model_name", "configured-adapter"
                )
                logger.info(
                    "inference_started job_id=%s model=%s",
                    job_id,
                    model_name,
                )
                result = self.music_generator.generate(request)
                logger.info(
                    "inference_finished job_id=%s provider=%s model=%s version=%s "
                    "duration_seconds=%s peak_vram_mb=%s",
                    job_id,
                    result.provider,
                    result.model_name,
                    result.model_version,
                    round(result.generation_time_seconds, 3),
                    result.peak_vram_mb,
                )
                repository.add_file(
                    job_id=job.id,
                    file_type=result.file_type,
                    file_path=self.storage.relative_path(result.audio_path),
                    mime_type="audio/wav",
                )
                repository.transition(job, JobStatus.COMPLETED, "completed")
                logger.info("worker_completed job_id=%s", job_id)
            except MusicGenerationError as exc:
                logger.error(
                    "worker_ai_failed job_id=%s error_code=%s error_type=%s",
                    job_id,
                    exc.code,
                    type(exc).__name__,
                )
                session.rollback()
                repository.mark_failed(
                    job,
                    code=exc.code,
                    message="AI 생성 작업에 실패했습니다.",
                )
            except Exception:
                logger.exception("worker_failed job_id=%s", job_id)
                session.rollback()
                repository.mark_failed(
                    job,
                    code="AI_INFERENCE_FAILED",
                    message="AI 생성 작업에 실패했습니다.",
                )
            finally:
                elapsed_ms = round((time.perf_counter() - started_at) * 1_000, 2)
                logger.info(
                    "worker_finished job_id=%s duration_ms=%s", job_id, elapsed_ms
                )
