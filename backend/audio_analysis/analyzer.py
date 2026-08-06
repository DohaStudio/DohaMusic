"""Pure final-WAV audio quality analyzer using NumPy, SciPy, and BS.1770."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
from scipy.io import wavfile

from backend.audio_analysis.contracts import (
    AudioAnalysisResult,
    AudioAnalysisStatus,
    AudioAnalysisWarning,
    AudioQualityMetrics,
    PUBLIC_WARNING_MESSAGES,
)

# One signed PCM16 quantization step. This recognizes both PCM16 endpoints and
# safely covers decoder-normalized 24/32-bit PCM values immediately below 1.0.
CLIPPING_EPSILON = 1.0 / 32_768.0


class AudioQualityAnalyzer(ABC):
    @abstractmethod
    def analyze(self, file_path: Path) -> AudioAnalysisResult:
        """Analyze a local final WAV without exposing the input path."""


class DefaultAudioQualityAnalyzer(AudioQualityAnalyzer):
    def analyze(self, file_path: Path) -> AudioAnalysisResult:
        if not file_path.exists() or not file_path.is_file():
            return self._failed("AUDIO_DECODE_FAILED")
        if file_path.suffix.lower() != ".wav":
            return self._unsupported("UNSUPPORTED_AUDIO_FORMAT")
        try:
            sample_rate, raw_samples = wavfile.read(file_path)
        except (OSError, ValueError):
            return self._failed("AUDIO_DECODE_FAILED")

        if sample_rate <= 0 or raw_samples.size == 0:
            return self._failed("INVALID_AUDIO_DATA")
        channels = 1 if raw_samples.ndim == 1 else raw_samples.shape[1]
        if raw_samples.ndim not in {1, 2} or channels not in {1, 2}:
            return self._unsupported("UNSUPPORTED_CHANNELS")

        samples = self._normalized_samples(raw_samples)
        if samples is None or not np.isfinite(samples).all():
            return self._failed("INVALID_AUDIO_DATA")

        frame_count = raw_samples.shape[0]
        duration_seconds = frame_count / sample_rate
        if (
            frame_count <= 0
            or not math.isfinite(duration_seconds)
            or duration_seconds <= 0
        ):
            return self._failed("INVALID_AUDIO_DATA")

        peak_linear = float(np.max(np.abs(samples)))
        warnings: list[AudioAnalysisWarning] = []
        if peak_linear == 0:
            sample_peak_dbfs = None
            warnings.append(self._warning("SILENT_AUDIO"))
        else:
            sample_peak_dbfs = round(20.0 * math.log10(peak_linear), 6)

        clipped = np.abs(samples) >= 1.0 - CLIPPING_EPSILON
        clipping_sample_count = int(np.count_nonzero(clipped))
        total_scalar_samples = int(samples.size)
        clipping_ratio = clipping_sample_count / total_scalar_samples
        if clipping_sample_count:
            warnings.append(self._warning("CLIPPING_DETECTED"))

        integrated_lufs: float | None
        try:
            measured_lufs = float(pyln.Meter(sample_rate).integrated_loudness(samples))
            integrated_lufs = (
                round(measured_lufs, 6) if math.isfinite(measured_lufs) else None
            )
        except (ArithmeticError, IndexError, ValueError):
            integrated_lufs = None
        if integrated_lufs is None:
            warnings.append(self._warning("LUFS_UNAVAILABLE"))

        quality = AudioQualityMetrics(
            duration_seconds=round(duration_seconds, 6),
            sample_rate=int(sample_rate),
            channels=int(channels),
            sample_peak_dbfs=sample_peak_dbfs,
            clipping_detected=clipping_sample_count > 0,
            clipping_sample_count=clipping_sample_count,
            clipping_ratio=round(clipping_ratio, 10),
            integrated_lufs=integrated_lufs,
        )
        return AudioAnalysisResult(
            analysis_status=(
                AudioAnalysisStatus.COMPLETED
                if integrated_lufs is not None and sample_peak_dbfs is not None
                else AudioAnalysisStatus.PARTIAL
            ),
            quality=quality,
            warnings=warnings,
        )

    @staticmethod
    def _normalized_samples(raw: np.ndarray) -> np.ndarray | None:
        if np.issubdtype(raw.dtype, np.floating):
            return raw.astype(np.float64, copy=False)
        if np.issubdtype(raw.dtype, np.signedinteger):
            scale = float(max(abs(np.iinfo(raw.dtype).min), np.iinfo(raw.dtype).max))
            return raw.astype(np.float64) / scale
        if np.issubdtype(raw.dtype, np.unsignedinteger):
            info = np.iinfo(raw.dtype)
            midpoint = (info.max + 1) / 2.0
            return (raw.astype(np.float64) - midpoint) / midpoint
        return None

    @staticmethod
    def _warning(code: str) -> AudioAnalysisWarning:
        return AudioAnalysisWarning(code=code, message=PUBLIC_WARNING_MESSAGES[code])

    def _failed(self, code: str) -> AudioAnalysisResult:
        return AudioAnalysisResult(
            analysis_status=AudioAnalysisStatus.FAILED,
            quality=None,
            warnings=[self._warning(code)],
        )

    def _unsupported(self, code: str) -> AudioAnalysisResult:
        return AudioAnalysisResult(
            analysis_status=AudioAnalysisStatus.UNSUPPORTED,
            quality=None,
            warnings=[self._warning(code)],
        )
