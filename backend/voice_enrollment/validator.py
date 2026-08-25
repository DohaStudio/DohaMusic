"""Authoritative PCM16 WAV metadata and basic signal quality validation."""

from __future__ import annotations

import math
import os
import wave
from array import array
from pathlib import Path

from backend.voice_enrollment.contracts import (
    ValidatedVoiceAudio,
    VoiceAudioProcessingError,
    VoiceQualityMetrics,
)

QUALITY_VERSION = "basic-v1"


class VoiceAudioValidator:
    def __init__(self, *, min_duration_seconds: float, max_duration_seconds: float) -> None:
        self.min_duration_seconds = min_duration_seconds
        self.max_duration_seconds = max_duration_seconds

    def validate(self, path: Path) -> ValidatedVoiceAudio:
        try:
            with wave.open(str(path), "rb") as audio:
                channels = audio.getnchannels()
                sample_rate = audio.getframerate()
                sample_width = audio.getsampwidth()
                frame_count = audio.getnframes()
                if (
                    channels != 1
                    or sample_rate != 48_000
                    or sample_width != 2
                    or audio.getcomptype() != "NONE"
                ):
                    raise VoiceAudioProcessingError("VOICE_SAMPLE_INVALID_WAV_OUTPUT")
                duration = frame_count / sample_rate
                if duration < self.min_duration_seconds:
                    raise VoiceAudioProcessingError("VOICE_SAMPLE_DURATION_TOO_SHORT")
                if duration > self.max_duration_seconds:
                    raise VoiceAudioProcessingError("VOICE_SAMPLE_DURATION_TOO_LONG")
                samples = array("h")
                while frames := audio.readframes(16_384):
                    chunk = array("h")
                    chunk.frombytes(frames)
                    if os.sys.byteorder != "little":
                        chunk.byteswap()
                    samples.extend(chunk)
        except VoiceAudioProcessingError:
            raise
        except (OSError, EOFError, wave.Error):
            raise VoiceAudioProcessingError("VOICE_SAMPLE_INVALID_WAV_OUTPUT") from None
        if not samples:
            raise VoiceAudioProcessingError("VOICE_SAMPLE_EMPTY_AUDIO")

        metrics, warnings = analyze_pcm16(samples)
        return ValidatedVoiceAudio(
            duration_seconds=duration,
            sample_rate=sample_rate,
            channels=channels,
            bit_depth=sample_width * 8,
            quality_status="WARNING" if warnings else "PASS",
            quality_warnings=warnings,
            metrics=metrics,
        )


def analyze_pcm16(samples: array[int]) -> tuple[VoiceQualityMetrics, list[str]]:
    total = len(samples)
    peak_sample = max(abs(sample) for sample in samples)
    sum_squares = sum(sample * sample for sample in samples)
    silent = sum(abs(sample) < 164 for sample in samples)
    clipped = sum(abs(sample) >= 32_735 for sample in samples)
    metrics = VoiceQualityMetrics(
        peak=peak_sample / 32_768,
        rms=math.sqrt(sum_squares / total) / 32_768,
        silence_ratio=silent / total,
        clipping_ratio=clipped / total,
    )
    warnings: list[str] = []
    if metrics.rms < 0.01:
        warnings.append("LOW_VOLUME")
    if metrics.silence_ratio > 0.8:
        warnings.append("HIGH_SILENCE_RATIO")
    if metrics.clipping_ratio > 0.001:
        warnings.append("POSSIBLE_CLIPPING")
    return metrics, warnings
