"""Provider-neutral Hook candidate estimation for a final WAV."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from backend.audio_analysis.contracts import (
    PUBLIC_WARNING_MESSAGES,
    AudioAnalysisStatus,
    AudioAnalysisWarning,
    HookAnalysisResult,
    HookCandidate,
    HookSelectionStrategy,
)

CANDIDATE_DURATION_SECONDS = 15.0
FEATURE_FRAME_SECONDS = 0.5
WINDOW_HOP_SECONDS = 1.0
MIN_HOOK_CONFIDENCE = 0.5


class HookAnalyzer(ABC):
    @abstractmethod
    def analyze(self, file_path: Path) -> HookAnalysisResult:
        """Estimate one Hook candidate without asserting an exact Chorus."""


class DefaultHookAnalyzer(HookAnalyzer):
    """Select a 15-second candidate from energy and repetition evidence."""

    def analyze(self, file_path: Path) -> HookAnalysisResult:
        if not file_path.exists() or not file_path.is_file():
            return self._failed("HOOK_DETECTION_FAILED")
        if file_path.suffix.lower() != ".wav":
            return self._failed("HOOK_UNSUPPORTED_AUDIO", unsupported=True)
        try:
            sample_rate, raw = wavfile.read(file_path)
        except (OSError, ValueError):
            return self._failed("HOOK_DETECTION_FAILED")
        if sample_rate <= 0 or raw.size == 0 or raw.ndim not in {1, 2}:
            return self._failed("HOOK_DETECTION_FAILED")
        channels = 1 if raw.ndim == 1 else raw.shape[1]
        if channels not in {1, 2}:
            return self._failed("HOOK_UNSUPPORTED_AUDIO", unsupported=True)
        samples = self._normalized_samples(raw)
        if samples is None or not np.isfinite(samples).all():
            return self._failed("HOOK_DETECTION_FAILED")
        mono = samples if samples.ndim == 1 else np.mean(samples, axis=1)
        duration = mono.size / float(sample_rate)
        if not math.isfinite(duration) or duration <= 0:
            return self._failed("HOOK_DETECTION_FAILED")
        if float(np.max(np.abs(mono))) < 1e-6:
            return self._failed("HOOK_SILENT_AUDIO")
        if duration < CANDIDATE_DURATION_SECONDS:
            return HookAnalysisResult(
                status=AudioAnalysisStatus.PARTIAL,
                candidate=self._candidate(
                    0.0,
                    duration,
                    0.0,
                    HookSelectionStrategy.FALLBACK_MIDDLE,
                ),
                warnings=[self._warning("HOOK_AUDIO_TOO_SHORT")],
            )

        estimate = self._estimate(mono, int(sample_rate))
        if estimate is None:
            return self._middle_fallback(duration, 0.0)
        start_seconds, confidence, strategy = estimate
        if confidence < MIN_HOOK_CONFIDENCE:
            return self._middle_fallback(duration, confidence)
        return HookAnalysisResult(
            status=AudioAnalysisStatus.COMPLETED,
            candidate=self._candidate(
                start_seconds,
                min(duration, start_seconds + CANDIDATE_DURATION_SECONDS),
                confidence,
                strategy,
            ),
        )

    @staticmethod
    def _estimate(
        samples: np.ndarray, sample_rate: int
    ) -> tuple[float, float, HookSelectionStrategy] | None:
        frame_length = max(1, round(sample_rate * FEATURE_FRAME_SECONDS))
        frame_count = samples.size // frame_length
        window_frames = round(CANDIDATE_DURATION_SECONDS / FEATURE_FRAME_SECONDS)
        hop_frames = max(1, round(WINDOW_HOP_SECONDS / FEATURE_FRAME_SECONDS))
        if frame_count < window_frames:
            return None
        frames = samples[: frame_count * frame_length].reshape(frame_count, frame_length)
        frame_energy = np.sqrt(
            np.einsum("ij,ij->i", frames, frames, dtype=np.float64) / frame_length
        )
        starts = np.arange(0, frame_count - window_frames + 1, hop_frames)
        if starts.size == 0:
            return None
        windows = np.stack([frame_energy[start : start + window_frames] for start in starts])
        means = np.mean(windows, axis=1)
        median = float(np.median(means))
        maximum = float(np.max(means))
        if maximum <= 0:
            return None
        prominence = (
            np.clip((means - median) / (maximum - median), 0.0, 1.0)
            if maximum - median > 1e-12
            else np.zeros_like(means)
        )
        repetition = DefaultHookAnalyzer._repetition_scores(windows, starts, window_frames)
        combined = 0.55 * repetition + 0.45 * prominence
        best = int(np.argmax(combined))

        if repetition[best] >= 0.45 and combined[best] >= MIN_HOOK_CONFIDENCE:
            strategy = HookSelectionStrategy.ENERGY_REPETITION
            confidence = float(combined[best])
        elif prominence[best] >= 0.75:
            strategy = HookSelectionStrategy.ENERGY_PEAK
            confidence = float(0.5 + 0.25 * prominence[best])
        else:
            strategy = HookSelectionStrategy.FALLBACK_MIDDLE
            confidence = float(combined[best])
        return (
            float(starts[best] * FEATURE_FRAME_SECONDS),
            float(np.clip(confidence, 0.0, 1.0)),
            strategy,
        )

    @staticmethod
    def _repetition_scores(
        windows: np.ndarray, starts: np.ndarray, window_frames: int
    ) -> np.ndarray:
        centered = windows - np.mean(windows, axis=1, keepdims=True)
        norms = np.linalg.norm(centered, axis=1)
        scores = np.zeros(windows.shape[0], dtype=np.float64)
        for index, start in enumerate(starts):
            if norms[index] <= 1e-12:
                continue
            eligible = np.flatnonzero(np.abs(starts - start) >= window_frames)
            if eligible.size == 0:
                continue
            valid = eligible[norms[eligible] > 1e-12]
            if valid.size == 0:
                continue
            correlations = centered[valid] @ centered[index]
            correlations /= norms[valid] * norms[index]
            scores[index] = max(0.0, float(np.max(correlations)))
        return np.clip(scores, 0.0, 1.0)

    def _middle_fallback(self, duration: float, confidence: float) -> HookAnalysisResult:
        start = max(0.0, (duration - CANDIDATE_DURATION_SECONDS) / 2.0)
        return HookAnalysisResult(
            status=AudioAnalysisStatus.PARTIAL,
            candidate=self._candidate(
                start,
                min(duration, start + CANDIDATE_DURATION_SECONDS),
                min(confidence, MIN_HOOK_CONFIDENCE - 0.0001),
                HookSelectionStrategy.FALLBACK_MIDDLE,
            ),
            warnings=[self._warning("HOOK_FALLBACK_MIDDLE")],
        )

    @staticmethod
    def _candidate(
        start: float,
        end: float,
        confidence: float,
        strategy: HookSelectionStrategy,
    ) -> HookCandidate:
        return HookCandidate(
            start_seconds=round(start, 3),
            end_seconds=round(end, 3),
            duration_seconds=round(end - start, 3),
            confidence=round(confidence, 4),
            selection_strategy=strategy,
        )

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

    def _failed(self, code: str, *, unsupported: bool = False) -> HookAnalysisResult:
        return HookAnalysisResult.failed(self._warning(code), unsupported=unsupported)
