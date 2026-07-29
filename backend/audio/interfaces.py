"""Provider-neutral audio mixer contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AudioMixInput:
    job_id: str
    vocals_path: Path
    instrumental_path: Path


@dataclass(frozen=True, slots=True)
class AudioMixResult:
    audio_path: Path
    provider: str
    mixing_time_seconds: float
    metadata: dict[str, Any]


class AudioMixer(Protocol):
    provider: str

    def mix(self, request: AudioMixInput) -> AudioMixResult:
        """Mix synchronized vocals and instrumental audio into one WAV."""
        ...
