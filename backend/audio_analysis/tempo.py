"""Provider-neutral tempo estimation for a completed Pipeline final WAV."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from scipy.io import wavfile
from scipy.signal import fftconvolve, find_peaks

from backend.audio_analysis.contracts import (
    AudioAnalysisStatus,
    AudioAnalysisWarning,
    PUBLIC_WARNING_MESSAGES,
    TempoAnalysisResult,
)

MIN_DURATION_SECONDS = 4.0
MIN_BPM = 50.0
MAX_BPM = 200.0
LOW_CONFIDENCE_THRESHOLD = 0.5


class TempoAnalyzer(ABC):
    @abstractmethod
    def analyze(
        self, file_path: Path, requested_bpm: float | None = None
    ) -> TempoAnalysisResult:
        """Estimate tempo without using requested BPM as an estimator prior."""


class DefaultTempoAnalyzer(TempoAnalyzer):
    """Estimate global tempo from an onset-energy autocorrelation."""

    def analyze(
        self, file_path: Path, requested_bpm: float | None = None
    ) -> TempoAnalysisResult:
        if not file_path.exists() or not file_path.is_file():
            return self._failed(requested_bpm, "TEMPO_DETECTION_FAILED")
        if file_path.suffix.lower() != ".wav":
            return self._failed(
                requested_bpm, "TEMPO_UNSUPPORTED_AUDIO", unsupported=True
            )
        try:
            sample_rate, raw = wavfile.read(file_path)
        except (OSError, ValueError):
            return self._failed(requested_bpm, "TEMPO_DETECTION_FAILED")
        if sample_rate <= 0 or raw.size == 0 or raw.ndim not in {1, 2}:
            return self._failed(requested_bpm, "TEMPO_DETECTION_FAILED")
        channels = 1 if raw.ndim == 1 else raw.shape[1]
        if channels not in {1, 2}:
            return self._failed(
                requested_bpm, "TEMPO_UNSUPPORTED_AUDIO", unsupported=True
            )
        samples = self._normalized_samples(raw)
        if samples is None or not np.isfinite(samples).all():
            return self._failed(requested_bpm, "TEMPO_DETECTION_FAILED")
        mono = samples if samples.ndim == 1 else np.mean(samples, axis=1)
        duration = mono.size / float(sample_rate)
        if not math.isfinite(duration) or duration < MIN_DURATION_SECONDS:
            return self._failed(requested_bpm, "TEMPO_AUDIO_TOO_SHORT")
        if float(np.max(np.abs(mono))) < 1e-6:
            return self._failed(requested_bpm, "TEMPO_SILENT_AUDIO")

        estimate = self._estimate(mono, int(sample_rate))
        if estimate is None:
            return self._failed(requested_bpm, "TEMPO_DETECTION_FAILED")
        detected_bpm, confidence = estimate
        bpm_error = (
            round(detected_bpm - requested_bpm, 3)
            if requested_bpm is not None
            else None
        )
        tolerance = (
            max(3.0, requested_bpm * 0.03) if requested_bpm is not None else None
        )
        half_time = bool(
            tolerance is not None
            and abs(detected_bpm * 2.0 - requested_bpm) <= tolerance
        )
        double_time = bool(
            tolerance is not None
            and abs(detected_bpm / 2.0 - requested_bpm) <= tolerance
        )
        warnings = (
            [self._warning("TEMPO_CONFIDENCE_LOW")]
            if confidence < LOW_CONFIDENCE_THRESHOLD
            else []
        )
        return TempoAnalysisResult(
            status=(
                AudioAnalysisStatus.PARTIAL
                if warnings
                else AudioAnalysisStatus.COMPLETED
            ),
            requested_bpm=requested_bpm,
            detected_bpm=round(detected_bpm, 3),
            confidence=round(confidence, 4),
            bpm_error=bpm_error,
            absolute_bpm_error=(abs(bpm_error) if bpm_error is not None else None),
            half_time_candidate=half_time,
            double_time_candidate=double_time,
            warnings=warnings,
        )

    @staticmethod
    def _estimate(samples: np.ndarray, sample_rate: int) -> tuple[float, float] | None:
        hop_length = max(128, round(sample_rate * 0.0116))
        frame_count = samples.size // hop_length
        if frame_count < 3:
            return None
        frames = samples[: frame_count * hop_length].reshape(frame_count, hop_length)
        energy = np.einsum("ij,ij->i", frames, frames, dtype=np.float64) / hop_length
        energy = fftconvolve(energy, np.ones(4, dtype=np.float64) / 4.0, mode="same")
        envelope = np.maximum(np.diff(np.sqrt(np.maximum(energy, 0.0))), 0.0)
        if envelope.size < 3 or float(np.max(envelope)) <= 0:
            return None
        envelope /= float(np.max(envelope))
        envelope[envelope < np.percentile(envelope, 70)] = 0.0

        min_lag = max(1, math.floor(60.0 * sample_rate / (MAX_BPM * hop_length)))
        max_lag = min(
            envelope.size - 2,
            math.ceil(60.0 * sample_rate / (MIN_BPM * hop_length)),
        )
        if max_lag <= min_lag:
            return None
        lags = np.arange(min_lag, max_lag + 1)
        scores = np.array(
            [
                DefaultTempoAnalyzer._normalized_correlation(envelope, int(lag))
                for lag in lags
            ]
        )
        if not np.isfinite(scores).all() or float(np.max(scores)) <= 0:
            return None
        peak_indexes, properties = find_peaks(scores, prominence=0.01)
        if peak_indexes.size == 0:
            best_index = int(np.argmax(scores))
            prominence = 0.0
        else:
            peak_scores = scores[peak_indexes]
            # Autocorrelation also peaks at integer beat multiples. Prefer the
            # shortest musically plausible lag when its periodic evidence is
            # at least three quarters of the strongest multiple.
            strong = peak_indexes[peak_scores >= float(np.max(peak_scores)) * 0.75]
            best_index = int(np.min(strong))
            property_index = int(np.flatnonzero(peak_indexes == best_index)[0])
            prominence = float(properties["prominences"][property_index])

        refined_lag = float(lags[best_index])
        if 0 < best_index < scores.size - 1:
            left, center, right = scores[best_index - 1 : best_index + 2]
            denominator = left - 2.0 * center + right
            if abs(denominator) > 1e-12:
                refined_lag += float(0.5 * (left - right) / denominator)
        detected_bpm = 60.0 * sample_rate / (hop_length * refined_lag)
        if not MIN_BPM <= detected_bpm <= MAX_BPM:
            return None
        peak_score = float(np.clip(scores[best_index], 0.0, 1.0))
        confidence = float(np.clip(0.8 * peak_score + 0.2 * prominence, 0.0, 1.0))
        return detected_bpm, confidence

    @staticmethod
    def _normalized_correlation(envelope: np.ndarray, lag: int) -> float:
        left = envelope[:-lag]
        right = envelope[lag:]
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        return float(np.dot(left, right) / denominator) if denominator > 0 else 0.0

    @staticmethod
    def _normalized_samples(raw: np.ndarray) -> np.ndarray | None:
        if np.issubdtype(raw.dtype, np.floating):
            return raw.astype(np.float32, copy=False)
        if np.issubdtype(raw.dtype, np.signedinteger):
            scale = float(max(abs(np.iinfo(raw.dtype).min), np.iinfo(raw.dtype).max))
            return raw.astype(np.float32) / scale
        if np.issubdtype(raw.dtype, np.unsignedinteger):
            info = np.iinfo(raw.dtype)
            midpoint = (info.max + 1) / 2.0
            return (raw.astype(np.float32) - midpoint) / midpoint
        return None

    @staticmethod
    def _warning(code: str) -> AudioAnalysisWarning:
        return AudioAnalysisWarning(code=code, message=PUBLIC_WARNING_MESSAGES[code])

    def _failed(
        self,
        requested_bpm: float | None,
        code: str,
        *,
        unsupported: bool = False,
    ) -> TempoAnalysisResult:
        return TempoAnalysisResult.failed(
            requested_bpm,
            self._warning(code),
            unsupported=unsupported,
        )
