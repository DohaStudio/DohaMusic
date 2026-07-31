"""Pipeline orchestration use cases."""

from __future__ import annotations

import stat
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, ResourceNotFoundError
from backend.core.job_status import JobStatus
from backend.core.logging import get_logger
from backend.models.pipeline_file import PipelineFile
from backend.models.pipeline_job import PipelineJob
from backend.models.project import Project
from backend.repositories.pipeline_repository import PipelineRepository
from backend.schemas.pipeline import PipelineCreate
from backend.storage.service import StorageService

logger = get_logger(__name__)

PUBLIC_AUDIO_FILE_TYPES = {
    "music",
    "vocals",
    "instrumental",
    "converted_voice",
    "final",
}
ALLOWED_AUDIO_TYPES = {("audio/wav", ".wav"), ("audio/x-wav", ".wav")}
MAX_AUDIO_FILE_BYTES = 1_073_741_824


@dataclass(frozen=True)
class AudioFileAccess:
    path: Path
    mime_type: str
    filename: str
    size: int


class PipelineDispatcher(Protocol):
    def submit(self, job_id: str) -> None: ...


class PipelineService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        dispatcher: PipelineDispatcher,
        pipeline_version: str,
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.dispatcher = dispatcher
        self.pipeline_version = pipeline_version
        self.storage = storage

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
            if (
                request.project_id is not None
                and repository.session.get(Project, request.project_id) is None
            ):
                raise ResourceNotFoundError("Project")
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

    def cancel(self, job_id: str) -> PipelineJob:
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            job = repository.get(job_id)
            if job is None:
                raise AppError(
                    "PIPELINE_JOB_NOT_FOUND", "음악 작업을 찾을 수 없습니다.", 404
                )
            if job.status in {JobStatus.COMPLETED.value, JobStatus.FAILED.value}:
                raise AppError(
                    "PIPELINE_CANCEL_NOT_ALLOWED",
                    "현재 상태에서는 음악 만들기를 취소할 수 없습니다.",
                    409,
                )
            job = repository.request_cancel(job)
            session.expunge(job)
            return job

    def retry(self, job_id: str) -> PipelineJob:
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            source = repository.get(job_id)
            if source is None:
                raise AppError(
                    "PIPELINE_JOB_NOT_FOUND", "음악 작업을 찾을 수 없습니다.", 404
                )
            if source.status not in {JobStatus.FAILED.value, JobStatus.CANCELLED.value}:
                raise AppError(
                    "PIPELINE_RETRY_NOT_ALLOWED",
                    "실패하거나 취소된 음악만 다시 만들 수 있습니다.",
                    409,
                )
            existing = repository.retry_for(source.id)
            if existing is not None:
                session.expunge(existing)
                return existing
            profile = repository.get_profile(source.voice_profile_id)
            if (
                profile is None
                or profile.status != "READY"
                or not profile.consent_confirmed
            ):
                raise AppError(
                    "RETRY_VOICE_PROFILE_UNAVAILABLE",
                    "사용한 목소리를 더 이상 사용할 수 없어 다시 만들 수 없습니다.",
                    409,
                )
            snapshot = source.input_snapshot or {
                "prompt": source.prompt,
                "lyrics": source.lyrics,
                "genre": source.genre,
                "duration_seconds": source.duration_seconds,
                "seed": source.seed,
                "voice_profile_id": source.voice_profile_id,
                "project_id": source.project_id,
            }
            if (
                source.project_id is not None
                and repository.session.get(Project, source.project_id) is None
            ):
                snapshot["project_id"] = None
            try:
                request = PipelineCreate.model_validate(snapshot)
            except ValueError as error:
                raise AppError(
                    "PIPELINE_RETRY_INPUT_MISSING",
                    "기존 음악 설정을 확인할 수 없어 다시 만들 수 없습니다.",
                    409,
                ) from error
            job = repository.create(
                request,
                self.pipeline_version,
                retry_of_job_id=source.id,
            )
            session.expunge(job)
        self.dispatcher.submit(job.id)
        return job

    def list_files(self, job_id: str) -> list[PipelineFile]:
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            job = repository.get(job_id)
            if job is None:
                raise ResourceNotFoundError("Pipeline 작업")
            files = repository.list_files(job_id)
            for item in files:
                available = job.status == "COMPLETED" and self._is_accessible(item)
                item.content_available = available
                item.download_available = available
                item.content_url = (
                    f"/api/pipelines/{job_id}/files/{item.id}/content"
                    if available
                    else None
                )
                item.download_url = (
                    f"/api/pipelines/{job_id}/files/{item.id}/download"
                    if available
                    else None
                )
                session.expunge(item)
            return files

    def access_audio_file(
        self,
        job_id: str,
        file_id: str,
        *,
        download: bool,
        range_header: str | None,
    ) -> AudioFileAccess:
        with self.session_factory() as session:
            repository = PipelineRepository(session)
            job = repository.get(job_id)
            if job is None:
                raise AppError(
                    "PIPELINE_NOT_FOUND", "Pipeline 작업을 찾을 수 없습니다.", 404
                )
            item = repository.get_file(file_id)
            if item is None:
                raise AppError("FILE_NOT_FOUND", "파일을 찾을 수 없습니다.", 404)
            if item.job_id != job_id:
                raise AppError("FILE_JOB_MISMATCH", "해당 작업의 파일이 아닙니다.", 404)
            if job.status != "COMPLETED":
                raise AppError(
                    "PIPELINE_NOT_COMPLETED",
                    "완료된 Pipeline 파일만 사용할 수 있습니다.",
                    409,
                )
            try:
                path, size = self._validate_file(item)
            except AppError as error:
                if error.code == "FILE_CONTENT_UNAVAILABLE" and download:
                    raise AppError(
                        "FILE_DOWNLOAD_UNAVAILABLE",
                        "다운로드할 수 없는 파일입니다.",
                        error.status_code,
                    ) from None
                raise
            self._validate_range(range_header, size)
            safe_type = (
                "".join(
                    character
                    for character in item.file_type.lower()
                    if character.isascii()
                    and (character.isalnum() or character in "-_")
                )[:40]
                or "audio"
            )
            filename = f"doha-{job_id[:8]}-{safe_type}.wav"
            return AudioFileAccess(path, item.mime_type, filename, size)

    def _is_accessible(self, item: PipelineFile) -> bool:
        try:
            self._validate_file(item)
        except AppError:
            return False
        return True

    def _validate_file(self, item: PipelineFile) -> tuple[Path, int]:
        if item.file_type not in PUBLIC_AUDIO_FILE_TYPES:
            raise AppError(
                "FILE_CONTENT_UNAVAILABLE", "재생할 수 없는 파일입니다.", 409
            )
        raw_path = Path(item.file_path)
        if raw_path.is_absolute():
            raise AppError(
                "INVALID_FILE_STORAGE_PATH", "파일 저장 위치가 올바르지 않습니다.", 409
            )
        candidate = self.storage.root / raw_path
        current = candidate
        while current != self.storage.root:
            if current.is_symlink():
                raise AppError(
                    "INVALID_FILE_STORAGE_PATH",
                    "파일 저장 위치가 올바르지 않습니다.",
                    409,
                )
            current = current.parent
        try:
            path = candidate.resolve(strict=True)
            path.relative_to(self.storage.pipeline_dir.resolve(strict=True))
        except FileNotFoundError:
            raise AppError(
                "FILE_MISSING_FROM_STORAGE", "저장된 파일을 찾을 수 없습니다.", 404
            ) from None
        except (OSError, ValueError):
            raise AppError(
                "INVALID_FILE_STORAGE_PATH", "파일 저장 위치가 올바르지 않습니다.", 409
            ) from None
        file_stat = path.stat()
        if not stat.S_ISREG(file_stat.st_mode):
            raise AppError(
                "INVALID_FILE_STORAGE_PATH", "일반 파일만 사용할 수 있습니다.", 409
            )
        if (item.mime_type.lower(), path.suffix.lower()) not in ALLOWED_AUDIO_TYPES:
            raise AppError(
                "UNSUPPORTED_AUDIO_FILE", "지원하지 않는 오디오 형식입니다.", 415
            )
        if file_stat.st_size <= 0 or file_stat.st_size > MAX_AUDIO_FILE_BYTES:
            raise AppError(
                "FILE_CONTENT_UNAVAILABLE", "허용된 파일 크기를 벗어났습니다.", 409
            )
        try:
            with path.open("rb") as audio:
                header = audio.read(12)
        except OSError:
            raise AppError(
                "FILE_MISSING_FROM_STORAGE", "저장된 파일을 읽을 수 없습니다.", 404
            ) from None
        if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
            raise AppError(
                "UNSUPPORTED_AUDIO_FILE", "지원하지 않는 오디오 형식입니다.", 415
            )
        return path, file_stat.st_size

    @staticmethod
    def _validate_range(value: str | None, size: int) -> None:
        if value is None:
            return
        error_headers = {
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes */{size}",
        }
        if not value.startswith("bytes=") or "," in value:
            raise AppError(
                "INVALID_RANGE",
                "요청한 파일 범위가 올바르지 않습니다.",
                416,
                error_headers,
            )
        spec = value.removeprefix("bytes=")
        if "-" not in spec:
            raise AppError(
                "INVALID_RANGE",
                "요청한 파일 범위가 올바르지 않습니다.",
                416,
                error_headers,
            )
        start_text, end_text = spec.split("-", 1)
        if not start_text and not end_text:
            raise AppError(
                "INVALID_RANGE",
                "요청한 파일 범위가 올바르지 않습니다.",
                416,
                error_headers,
            )
        if (start_text and not start_text.isdigit()) or (
            end_text and not end_text.isdigit()
        ):
            raise AppError(
                "INVALID_RANGE",
                "요청한 파일 범위가 올바르지 않습니다.",
                416,
                error_headers,
            )
        if start_text:
            start = int(start_text)
            if start >= size or (end_text and int(end_text) < start):
                raise AppError(
                    "INVALID_RANGE",
                    "요청한 파일 범위가 올바르지 않습니다.",
                    416,
                    error_headers,
                )
        elif int(end_text) <= 0:
            raise AppError(
                "INVALID_RANGE",
                "요청한 파일 범위가 올바르지 않습니다.",
                416,
                error_headers,
            )
