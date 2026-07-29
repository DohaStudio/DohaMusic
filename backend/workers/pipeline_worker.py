"""Asynchronous orchestrator worker for the complete mock AI workflow."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.core.job_status import JobStatus
from backend.core.logging import get_logger
from backend.pipeline.context import PipelineContext
from backend.pipeline.errors import PipelineError
from backend.pipeline.executor import PipelineExecutor
from backend.pipeline.steps import PipelineStep
from backend.repositories.pipeline_repository import PipelineRepository
from backend.storage.service import StorageService

logger = get_logger(__name__)


class PipelineWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        executor: PipelineExecutor,
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.executor = executor
        self.storage = storage

    def run(self, job_id: str) -> None:
        started_at = time.perf_counter()
        logger.info("pipeline_worker_started job_id=%s", job_id)
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            job = repository.get(job_id)
            if job is None:
                logger.error("pipeline_job_not_found job_id=%s", job_id)
                return
            context: PipelineContext | None = None
            try:
                repository.transition(job, JobStatus.VALIDATING, "validating_inputs", 0)
                profile = repository.get_profile(job.voice_profile_id)
                if profile is None or not profile.consent_confirmed:
                    raise PermissionError("동의된 음성 프로필이 필요합니다.")
                reference_path = self.storage.resolve_voice_reference(
                    profile.reference_file_path
                )
                if not reference_path.is_file():
                    raise FileNotFoundError("참조 음성 파일이 없습니다.")
                context = PipelineContext(
                    job_id=job.id,
                    prompt=job.prompt,
                    lyrics=job.lyrics,
                    genre=job.genre,
                    duration_seconds=job.duration_seconds,
                    seed=job.seed,
                    voice_profile_id=job.voice_profile_id,
                    reference_voice_path=reference_path,
                    pipeline_version=job.pipeline_version,
                )
                self.executor.execute(
                    context,
                    lambda step: self._start_step(repository, job, step),
                )
                metadata = self._metadata(context, started_at, success=True)
                metadata_path = self._write_metadata(job.id, metadata)
                context.metadata_file = metadata_path
                repository.set_metadata(job, metadata)
                self._persist_files(repository, context)
                repository.transition(job, JobStatus.COMPLETED, "completed", 100)
                logger.info(
                    "pipeline_worker_completed job_id=%s duration_ms=%s",
                    job_id,
                    round((time.perf_counter() - started_at) * 1_000, 2),
                )
            except PipelineError as exc:
                logger.error(
                    "pipeline_step_failed job_id=%s step=%s code=%s",
                    job_id,
                    exc.step,
                    exc.code,
                )
                session.rollback()
                self._fail(repository, job, context, started_at, exc)
            except Exception as exc:
                logger.exception("pipeline_worker_failed job_id=%s", job_id)
                session.rollback()
                wrapped = PipelineError(
                    "PIPELINE_FAILED", str(exc), step=job.current_step
                )
                self._fail(repository, job, context, started_at, wrapped)
            finally:
                logger.info(
                    "pipeline_worker_finished job_id=%s duration_ms=%s",
                    job_id,
                    round((time.perf_counter() - started_at) * 1_000, 2),
                )

    @staticmethod
    def _start_step(
        repository: PipelineRepository, job: Any, step: PipelineStep
    ) -> None:
        repository.transition(
            job, step.status, f"{step.name}_started", step.progress_percent
        )
        logger.info("pipeline_step_started job_id=%s step=%s", job.id, step.name)

    def _fail(
        self,
        repository: PipelineRepository,
        job: Any,
        context: PipelineContext | None,
        started_at: float,
        error: PipelineError,
    ) -> None:
        if context is not None:
            self._cleanup_partial_outputs(context)
            metadata = self._metadata(context, started_at, success=False)
        else:
            metadata = {
                "pipeline_version": job.pipeline_version,
                "success": False,
                "execution_time_seconds": round(time.perf_counter() - started_at, 6),
                "step_execution": [],
                "errors": [],
            }
        final_error = {"step": error.step, "code": error.code, "message": error.message}
        if not any(
            item.get("step") == error.step and item.get("code") == error.code
            for item in metadata["errors"]
        ):
            metadata["errors"].append(final_error)
        metadata_path = self._write_metadata(job.id, metadata)
        repository.add_file(
            job.id,
            "metadata",
            self.storage.relative_path(metadata_path),
            "application/json",
        )
        repository.mark_failed(
            job,
            error.code,
            "Pipeline 작업이 실패했습니다.",
            error.step,
            metadata,
        )

    def _metadata(
        self, context: PipelineContext, started_at: float, success: bool
    ) -> dict[str, Any]:
        timings = [item["execution_time_seconds"] for item in context.step_execution]
        vram_values = [
            item["peak_vram_mb"]
            for item in context.step_execution
            if item.get("peak_vram_mb") is not None
        ]
        return {
            "pipeline_version": context.pipeline_version,
            "success": success,
            "seed": context.seed,
            "duration_seconds": context.duration_seconds,
            "execution_time_seconds": round(time.perf_counter() - started_at, 6),
            "providers": context.providers,
            "step_execution": context.step_execution,
            "benchmark": {
                "step_time_seconds": round(sum(timings), 6),
                "peak_vram_mb": max(vram_values, default=None),
                "cpu_percent": None,
                "gpu_percent": None,
                "success": success,
                "failed_step": None
                if success
                else (context.errors[-1]["step"] if context.errors else None),
            },
            "errors": list(context.errors),
        }

    def _write_metadata(self, job_id: str, metadata: dict[str, Any]) -> Path:
        path = self.storage.pipeline_dir / job_id / "metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def _persist_files(
        self, repository: PipelineRepository, context: PipelineContext
    ) -> None:
        entries = (
            ("music", context.music_file, "audio/wav"),
            ("vocals", context.vocals_file, "audio/wav"),
            ("instrumental", context.instrumental_file, "audio/wav"),
            ("converted_voice", context.converted_voice, "audio/wav"),
            ("final", context.output_file, "audio/wav"),
            ("metadata", context.metadata_file, "application/json"),
        )
        for file_type, path, mime_type in entries:
            if path is not None:
                repository.add_file(
                    context.job_id,
                    file_type,
                    self.storage.relative_path(path),
                    mime_type,
                )

    @staticmethod
    def _cleanup_partial_outputs(context: PipelineContext) -> None:
        for path in context.generated_paths():
            try:
                path.unlink(missing_ok=True)
            except OSError:
                logger.exception("pipeline_partial_cleanup_failed path=%s", path)
