"""Replaceable Voice Enrollment audio normalization implementations."""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import wave
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

from backend.voice_enrollment.contracts import (
    NormalizedAudio,
    VoiceAudioProcessingError,
    VoiceContainer,
)


class VoiceAudioNormalizer(ABC):
    @abstractmethod
    def normalize(
        self, source_path: Path, output_path: Path, container: VoiceContainer
    ) -> NormalizedAudio: ...


class HybridVoiceAudioNormalizer(VoiceAudioNormalizer):
    """Use Python for PCM16 WAV and FFmpeg only for Opus containers."""

    def __init__(
        self,
        *,
        ffmpeg_executable: str,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> None:
        self.ffmpeg_executable = ffmpeg_executable
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def normalize(
        self, source_path: Path, output_path: Path, container: VoiceContainer
    ) -> NormalizedAudio:
        temporary_output = output_path.with_suffix(".normalizing")
        temporary_output.unlink(missing_ok=True)
        try:
            if container == VoiceContainer.WAV:
                self._normalize_wav(source_path, temporary_output)
            else:
                self._normalize_with_ffmpeg(source_path, temporary_output)
            if not temporary_output.is_file() or temporary_output.stat().st_size == 0:
                raise VoiceAudioProcessingError("VOICE_SAMPLE_NORMALIZATION_FAILED")
            if temporary_output.stat().st_size > self.max_output_bytes:
                raise VoiceAudioProcessingError("VOICE_SAMPLE_NORMALIZATION_FAILED")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_output.replace(output_path)
            return NormalizedAudio(
                path=output_path,
                content_type="audio/wav",
                size_bytes=output_path.stat().st_size,
            )
        except VoiceAudioProcessingError:
            temporary_output.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
            raise
        except OSError:
            temporary_output.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
            raise VoiceAudioProcessingError(
                "VOICE_SAMPLE_NORMALIZATION_FAILED"
            ) from None

    @staticmethod
    def _normalize_wav(source_path: Path, output_path: Path) -> None:
        try:
            with wave.open(str(source_path), "rb") as source:
                channels = source.getnchannels()
                sample_rate = source.getframerate()
                if (
                    channels not in {1, 2}
                    or sample_rate < 16_000
                    or source.getsampwidth() != 2
                    or source.getcomptype() != "NONE"
                ):
                    raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
                raw = source.readframes(source.getnframes())
        except VoiceAudioProcessingError:
            raise
        except (OSError, EOFError, wave.Error):
            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED") from None
        if not raw:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_EMPTY_AUDIO")

        pcm = np.frombuffer(raw, dtype="<i2")
        if channels == 2:
            if pcm.size % 2:
                raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
            pcm = pcm.reshape(-1, 2).astype(np.float64).mean(axis=1)
        else:
            pcm = pcm.astype(np.float64)
        if sample_rate != 48_000:
            divisor = math.gcd(sample_rate, 48_000)
            pcm = resample_poly(pcm, 48_000 // divisor, sample_rate // divisor)
        normalized = np.clip(np.rint(pcm), -32_768, 32_767).astype("<i2")
        try:
            with wave.open(str(output_path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(48_000)
                target.writeframes(normalized.tobytes())
        except (OSError, wave.Error):
            raise VoiceAudioProcessingError(
                "VOICE_SAMPLE_NORMALIZATION_FAILED"
            ) from None

    def _normalize_with_ffmpeg(self, source_path: Path, output_path: Path) -> None:
        executable = self._resolve_executable()
        command = [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(source_path),
            "-map",
            "0:a:0",
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=self.timeout_seconds,
                shell=False,
                env=self._minimal_environment(),
            )
        except subprocess.TimeoutExpired:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_TIMEOUT") from None
        except OSError:
            raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE") from None
        if completed.returncode != 0:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")

    def _resolve_executable(self) -> str:
        configured = Path(self.ffmpeg_executable)
        if configured.is_absolute():
            if not configured.is_file():
                raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE")
            return str(configured)
        resolved = shutil.which(self.ffmpeg_executable)
        if resolved is None:
            raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE")
        return resolved

    @staticmethod
    def _minimal_environment() -> dict[str, str]:
        allowed = ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP")
        return {name: os.environ[name] for name in allowed if name in os.environ}
