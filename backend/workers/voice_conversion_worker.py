"""Provider-neutral asynchronous voice conversion worker."""

import time
from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.ai.errors import VoiceConversionError
from backend.ai.interfaces.voice_converter import VoiceConversionInput, VoiceConverter
from backend.core.job_status import JobStatus
from backend.core.logging import get_logger
from backend.repositories.voice_conversion_repository import VoiceConversionRepository
from backend.storage.service import StorageService

logger = get_logger(__name__)


class VoiceConversionWorker:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        voice_converter: VoiceConverter,
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.voice_converter = voice_converter
        self.storage = storage

    def run(self, job_id: str) -> None:
        started_at = time.perf_counter()
        logger.info("voice_worker_started job_id=%s", job_id)
        with self.session_factory() as session:
            repository = VoiceConversionRepository(session)
            job = repository.get(job_id)
            if job is None:
                logger.error("voice_worker_job_not_found job_id=%s", job_id)
                return
            try:
                repository.transition(job, JobStatus.VALIDATING, "validating_inputs")
                source = repository.get_source_file(job.source_file_id)
                profile = repository.get_profile(job.voice_profile_id)
                if source is None or source.file_type != "vocals":
                    raise FileNotFoundError("Vocal source metadata is unavailable")
                if profile is None or not profile.consent_confirmed:
                    raise PermissionError("Voice profile consent is unavailable")
                source_path = self.storage.resolve_relative_path(source.file_path)
                reference_path = self.storage.resolve_voice_reference(profile.reference_file_path)
                if not source_path.is_file() or not reference_path.is_file():
                    raise FileNotFoundError("Voice conversion input is unavailable")
                repository.transition(job, JobStatus.VOICE_CONVERTING, "voice_conversion_started")
                logger.info(
                    "voice_inference_started job_id=%s model=%s",
                    job_id,
                    self.voice_converter.model_name,
                )
                result = self.voice_converter.convert(
                    VoiceConversionInput(job.id, source_path, reference_path)
                )
                repository.set_model(job, result.provider, result.model_name, result.model_version)
                repository.add_file(
                    job.id,
                    "converted_voice",
                    self.storage.relative_path(result.converted_path),
                    "audio/wav",
                )
                if result.metadata_path is not None:
                    repository.add_file(
                        job.id,
                        "metadata",
                        self.storage.relative_path(result.metadata_path),
                        "application/json",
                    )
                repository.transition(job, JobStatus.COMPLETED, "completed")
                logger.info(
                    "voice_worker_completed job_id=%s provider=%s model=%s version=%s "
                    "duration_seconds=%s peak_vram_mb=%s",
                    job_id,
                    result.provider,
                    result.model_name,
                    result.model_version,
                    round(result.conversion_time_seconds, 3),
                    result.peak_vram_mb,
                )
            except VoiceConversionError as exc:
                logger.error("voice_worker_ai_failed job_id=%s error_code=%s", job_id, exc.code)
                session.rollback()
                repository.mark_failed(job, exc.code, "Voice Conversion 작업이 실패했습니다.")
            except Exception:
                logger.exception("voice_worker_failed job_id=%s", job_id)
                session.rollback()
                repository.mark_failed(
                    job,
                    "VOICE_CONVERSION_FAILED",
                    "Voice Conversion 작업이 실패했습니다.",
                )
            finally:
                logger.info(
                    "voice_worker_finished job_id=%s duration_ms=%s",
                    job_id,
                    round((time.perf_counter() - started_at) * 1000, 2),
                )
