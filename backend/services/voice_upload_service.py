"""Chunked, consent-gated WAV upload for local voice profiles."""

from __future__ import annotations

import math
import os
import uuid
import wave
from array import array
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.core.exceptions import AppError
from backend.models.voice_profile import VoiceProfile
from backend.repositories.voice_profile_repository import VoiceProfileRepository
from backend.storage.service import StorageService

MAX_VOICE_UPLOAD_BYTES = 25 * 1024 * 1024
MIN_VOICE_DURATION_SECONDS = 5.0
MAX_VOICE_DURATION_SECONDS = 60.0
MIN_VOICE_SAMPLE_RATE = 16_000
UPLOAD_CHUNK_BYTES = 1024 * 1024
ALLOWED_VOICE_MIME_TYPES = {"audio/wav", "audio/x-wav"}


@dataclass(frozen=True)
class WavMetadata:
    duration_seconds: float
    sample_rate: int
    channels: int
    quality_warnings: list[str]


class VoiceUploadService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage

    async def upload(
        self,
        *,
        file: UploadFile | None,
        name: str,
        consent_confirmed: bool,
        consent_text_version: str,
        content_length: int | None,
    ) -> VoiceProfile:
        if not consent_confirmed:
            raise AppError(
                "VOICE_CONSENT_REQUIRED", "음성 사용 동의가 필요합니다.", 422
            )
        if (
            content_length is not None
            and content_length > MAX_VOICE_UPLOAD_BYTES + 64_000
        ):
            raise AppError(
                "VOICE_FILE_TOO_LARGE", "음성 파일은 25MB 이하여야 합니다.", 413
            )
        if file is None or not file.filename:
            raise AppError("VOICE_FILE_REQUIRED", "음성 파일을 선택해 주세요.", 422)

        profile_id = str(uuid.uuid4())
        upload_dir = self.storage.voice_references_dir / ".uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        temporary_path = upload_dir / f"{profile_id}.tmp"
        final_dir = self.storage.voice_references_dir / profile_id
        final_path = final_dir / "reference.wav"
        size_bytes = 0
        try:
            self._validate_declared_file(file)
            with temporary_path.open("xb") as target:
                while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > MAX_VOICE_UPLOAD_BYTES:
                        raise AppError(
                            "VOICE_FILE_TOO_LARGE",
                            "음성 파일은 25MB 이하여야 합니다.",
                            413,
                        )
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if size_bytes == 0:
                raise AppError(
                    "VOICE_FILE_EMPTY", "빈 음성 파일은 등록할 수 없습니다.", 422
                )
            metadata = self._inspect_wav(temporary_path)
            final_dir.mkdir(parents=False, exist_ok=False)
            temporary_path.replace(final_path)
        except AppError:
            self._cleanup(temporary_path, final_path, final_dir)
            raise
        except OSError:
            self._cleanup(temporary_path, final_path, final_dir)
            raise AppError(
                "VOICE_STORAGE_WRITE_FAILED",
                "음성 파일을 안전하게 저장하지 못했습니다.",
                500,
            ) from None
        finally:
            await file.close()

        try:
            with self.session_factory() as session:
                profile = VoiceProfileRepository(session).create(
                    id=profile_id,
                    name=name,
                    reference_file_path=self.storage.relative_path(final_path),
                    display_filename=self._display_filename(file.filename),
                    mime_type="audio/wav",
                    size_bytes=size_bytes,
                    duration_seconds=metadata.duration_seconds,
                    sample_rate=metadata.sample_rate,
                    channels=metadata.channels,
                    status="READY",
                    quality_warnings=metadata.quality_warnings,
                    consent_confirmed=True,
                    consent_text_version=consent_text_version,
                    consent_confirmed_at=datetime.now(UTC),
                )
                session.expunge(profile)
                return profile
        except Exception:
            self._cleanup(temporary_path, final_path, final_dir)
            raise

    @staticmethod
    def _validate_declared_file(file: UploadFile) -> None:
        filename = file.filename or ""
        if any(character in filename for character in ("/", "\\", "\x00")):
            raise AppError(
                "VOICE_FILE_TYPE_UNSUPPORTED", "안전하지 않은 파일명입니다.", 415
            )
        if Path(filename).suffix.lower() != ".wav":
            raise AppError(
                "VOICE_FILE_TYPE_UNSUPPORTED", "WAV 파일만 등록할 수 있습니다.", 415
            )
        if file.content_type not in ALLOWED_VOICE_MIME_TYPES:
            raise AppError(
                "VOICE_FILE_TYPE_UNSUPPORTED", "WAV MIME 형식만 허용됩니다.", 415
            )

    @staticmethod
    def _inspect_wav(path: Path) -> WavMetadata:
        try:
            with wave.open(str(path), "rb") as audio:
                channels = audio.getnchannels()
                sample_rate = audio.getframerate()
                sample_width = audio.getsampwidth()
                frame_count = audio.getnframes()
                compression = audio.getcomptype()
                if (
                    channels not in {1, 2}
                    or sample_rate < MIN_VOICE_SAMPLE_RATE
                    or sample_width != 2
                    or compression != "NONE"
                ):
                    raise AppError(
                        "VOICE_REFERENCE_INVALID",
                        "16-bit PCM, 16kHz 이상, mono 또는 stereo WAV가 필요합니다.",
                        422,
                    )
                duration = frame_count / sample_rate
                if duration < MIN_VOICE_DURATION_SECONDS:
                    raise AppError(
                        "VOICE_FILE_TOO_SHORT", "음성은 5초 이상이어야 합니다.", 422
                    )
                if duration > MAX_VOICE_DURATION_SECONDS:
                    raise AppError(
                        "VOICE_FILE_TOO_LONG", "음성은 60초 이하여야 합니다.", 422
                    )

                total_samples = 0
                sum_squares = 0
                silent_samples = 0
                clipped_samples = 0
                while frames := audio.readframes(16_384):
                    samples = array("h")
                    samples.frombytes(frames)
                    if os.sys.byteorder != "little":
                        samples.byteswap()
                    total_samples += len(samples)
                    sum_squares += sum(sample * sample for sample in samples)
                    silent_samples += sum(abs(sample) < 164 for sample in samples)
                    clipped_samples += sum(abs(sample) >= 32_735 for sample in samples)
        except AppError:
            raise
        except (OSError, EOFError, wave.Error):
            raise AppError(
                "VOICE_FILE_DECODE_FAILED", "손상되었거나 지원하지 않는 WAV입니다.", 422
            ) from None

        if total_samples == 0:
            raise AppError("VOICE_REFERENCE_INVALID", "음성 데이터가 없습니다.", 422)
        rms = math.sqrt(sum_squares / total_samples) / 32_768
        silence_ratio = silent_samples / total_samples
        clipping_ratio = clipped_samples / total_samples
        warnings: list[str] = []
        if rms < 0.01:
            warnings.append("LOW_VOLUME")
        if silence_ratio > 0.8:
            warnings.append("HIGH_SILENCE_RATIO")
        if clipping_ratio > 0.001:
            warnings.append("POSSIBLE_CLIPPING")
        return WavMetadata(duration, sample_rate, channels, warnings)

    @staticmethod
    def _display_filename(filename: str) -> str:
        cleaned = "".join(
            character for character in filename if character.isprintable()
        ).strip()
        stem = Path(cleaned).stem[:200].rstrip(" .") or "voice-reference"
        if stem.upper() in {"CON", "PRN", "AUX", "NUL", "COM1", "LPT1"}:
            stem = "voice-reference"
        return f"{stem}.wav"

    @staticmethod
    def _cleanup(temporary_path: Path, final_path: Path, final_dir: Path) -> None:
        for path in (temporary_path, final_path):
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        try:
            final_dir.rmdir()
        except OSError:
            pass
