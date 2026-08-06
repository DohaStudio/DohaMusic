"""Internal contracts for Voice Enrollment normalization and validation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


class VoiceContainer(StrEnum):
    WAV = "wav"
    WEBM = "webm"
    OGG = "ogg"


@dataclass(frozen=True, slots=True)
class NormalizedAudio:
    path: Path
    content_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class VoiceQualityMetrics:
    peak: float
    rms: float
    silence_ratio: float
    clipping_ratio: float


@dataclass(frozen=True, slots=True)
class ValidatedVoiceAudio:
    duration_seconds: float
    sample_rate: int
    channels: int
    bit_depth: int
    quality_status: str
    quality_warnings: list[str]
    metrics: VoiceQualityMetrics


class VoiceAudioProcessingError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code
