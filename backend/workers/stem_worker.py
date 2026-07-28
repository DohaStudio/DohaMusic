"""Provider-neutral asynchronous stem separation worker."""

from __future__ import annotations

import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.ai.errors import StemSeparationError
from backend.ai.interfaces.stem_separator import StemSeparationInput, StemSeparator
from backend.ai.interfaces.stem_separator import StemSeparationResult
from backend.core.job_status import JobStatus
from backend.core.logging import get_logger
from backend.repositories.stem_repository import StemRepository
from backend.storage.service import StorageService

logger = get_logger(__name__)


class StemWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        stem_separator: StemSeparator,
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.stem_separator = stem_separator
        self.storage = storage

    def run(self, job_id: str) -> None:
        started_at = time.perf_counter()
        logger.info("stem_worker_started job_id=%s", job_id)
        with self.session_factory() as session:
            repository = StemRepository(session)
            job = repository.get(job_id)
            if job is None:
                logger.error("stem_worker_job_not_found job_id=%s", job_id)
                return
            try:
                repository.transition(job, JobStatus.VALIDATING, "validating_source")
                source_file = repository.get_source_file(job.source_file_id)
                if source_file is None:
                    raise FileNotFoundError("Stem source metadata is unavailable")
                source_path = self.storage.resolve_relative_path(source_file.file_path)
                if not source_path.is_file():
                    raise FileNotFoundError("Stem source file is unavailable")
                repository.transition(
                    job, JobStatus.STEM_SEPARATING, "stem_separation_started"
                )
                logger.info(
                    "stem_inference_started job_id=%s model=%s",
                    job_id,
                    self.stem_separator.model_name,
                )
                result = self.stem_separator.separate(
                    StemSeparationInput(job_id=job.id, source_path=source_path)
                )
                repository.set_model(
                    job, result.provider, result.model_name, result.model_version
                )
                self._add_result_files(repository, job.id, result)
                repository.transition(job, JobStatus.COMPLETED, "completed")
                logger.info(
                    "stem_worker_completed job_id=%s provider=%s model=%s version=%s "
                    "duration_seconds=%s peak_vram_mb=%s",
                    job_id,
                    result.provider,
                    result.model_name,
                    result.model_version,
                    round(result.separation_time_seconds, 3),
                    result.peak_vram_mb,
                )
            except StemSeparationError as exc:
                logger.error(
                    "stem_worker_ai_failed job_id=%s error_code=%s error_type=%s",
                    job_id,
                    exc.code,
                    type(exc).__name__,
                )
                session.rollback()
                repository.mark_failed(job, exc.code, "Stem 분리 작업에 실패했습니다.")
            except Exception:
                logger.exception("stem_worker_failed job_id=%s", job_id)
                session.rollback()
                repository.mark_failed(
                    job,
                    "STEM_SEPARATION_FAILED",
                    "Stem 분리 작업에 실패했습니다.",
                )
            finally:
                logger.info(
                    "stem_worker_finished job_id=%s duration_ms=%s",
                    job_id,
                    round((time.perf_counter() - started_at) * 1_000, 2),
                )

    def _add_result_files(
        self,
        repository: StemRepository,
        job_id: str,
        result: StemSeparationResult,
    ) -> None:
        repository.add_file(
            job_id,
            "vocals",
            self.storage.relative_path(result.vocals_path),
            "audio/wav",
        )
        repository.add_file(
            job_id,
            "instrumental",
            self.storage.relative_path(result.instrumental_path),
            "audio/wav",
        )
        if result.metadata_path is not None:
            repository.add_file(
                job_id,
                "metadata",
                self.storage.relative_path(result.metadata_path),
                "application/json",
            )
