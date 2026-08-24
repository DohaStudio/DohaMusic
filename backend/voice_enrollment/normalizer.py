"""Replaceable Voice Enrollment audio normalization implementations."""

from __future__ import annotations

import math
import os
import shutil
import struct
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
        self._verified_ffmpeg_executable: str | None = None

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
                raise VoiceAudioProcessingError("VOICE_SAMPLE_DURATION_TOO_LONG")
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
            raise VoiceAudioProcessingError("VOICE_SAMPLE_NORMALIZATION_FAILED") from None

    def _normalize_wav(self, source_path: Path, output_path: Path) -> None:
        format_tag, bit_depth = self._read_wav_format(source_path)
        if format_tag != 1 or bit_depth != 16:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_UNSUPPORTED_CODEC")
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
        frame_bytes = channels * 2
        if len(raw) % frame_bytes:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
        source_frames = len(raw) // frame_bytes
        normalized_frames = math.ceil(source_frames * 48_000 / sample_rate)
        if normalized_frames * 2 + 44 > self.max_output_bytes:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_DURATION_TOO_LONG")

        pcm = np.frombuffer(raw, dtype="<i2")
        if channels == 2:
            if pcm.size % 2:
                raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
            pcm = pcm.reshape(-1, 2).astype(np.float64).mean(axis=1)
        else:
            pcm = pcm.astype(np.float64)
        if sample_rate != 48_000:
            divisor = math.gcd(sample_rate, 48_000)
            try:
                pcm = resample_poly(pcm, 48_000 // divisor, sample_rate // divisor)
            except (OverflowError, ValueError):
                raise VoiceAudioProcessingError("VOICE_SAMPLE_NORMALIZATION_FAILED") from None
        if not np.isfinite(pcm).all():
            raise VoiceAudioProcessingError("VOICE_SAMPLE_NORMALIZATION_FAILED")
        normalized = np.clip(np.rint(pcm), -32_768, 32_767).astype("<i2")
        try:
            with wave.open(str(output_path), "wb") as target:
                target.setnchannels(1)
                target.setsampwidth(2)
                target.setframerate(48_000)
                target.writeframes(normalized.tobytes())
        except (OSError, wave.Error):
            raise VoiceAudioProcessingError("VOICE_SAMPLE_NORMALIZATION_FAILED") from None

    @staticmethod
    def _read_wav_format(source_path: Path) -> tuple[int, int]:
        try:
            with source_path.open("rb") as source:
                header = source.read(12)
                if len(header) != 12 or header[:4] != b"RIFF" or header[8:] != b"WAVE":
                    raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
                while chunk_header := source.read(8):
                    if len(chunk_header) != 8:
                        raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
                    chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
                    if chunk_id == b"fmt ":
                        if chunk_size < 16:
                            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
                        payload = source.read(16)
                        if len(payload) != 16:
                            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")
                        format_tag, _, _, _, _, bit_depth = struct.unpack("<HHIIHH", payload)
                        return format_tag, bit_depth
                    source.seek(chunk_size + (chunk_size % 2), os.SEEK_CUR)
        except VoiceAudioProcessingError:
            raise
        except (EOFError, OSError, OverflowError, struct.error):
            raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED") from None
        raise VoiceAudioProcessingError("VOICE_SAMPLE_DECODE_FAILED")

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
            "-f",
            "wav",
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
        if self._verified_ffmpeg_executable is not None:
            return self._verified_ffmpeg_executable
        configured = Path(self.ffmpeg_executable)
        if configured.is_absolute():
            if not configured.is_file():
                raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE")
            resolved = str(configured)
        else:
            resolved = shutil.which(self.ffmpeg_executable)
        if resolved is None or not Path(resolved).is_file():
            raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE")
        self._verify_executable(resolved)
        self._verified_ffmpeg_executable = resolved
        return resolved

    def _verify_executable(self, executable: str) -> None:
        try:
            completed = subprocess.run(
                [executable, "-version"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=min(self.timeout_seconds, 5),
                shell=False,
                env=self._minimal_environment(),
                text=True,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE") from None
        first_line = completed.stdout.splitlines()[0] if completed.stdout else ""
        if completed.returncode != 0 or not first_line.startswith("ffmpeg version "):
            raise VoiceAudioProcessingError("VOICE_NORMALIZER_UNAVAILABLE")

    @staticmethod
    def _minimal_environment() -> dict[str, str]:
        allowed = ("PATH", "SystemRoot", "WINDIR", "TEMP", "TMP")
        return {name: os.environ[name] for name in allowed if name in os.environ}
