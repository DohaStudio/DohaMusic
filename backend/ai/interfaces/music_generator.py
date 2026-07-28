"""Model-independent music generation contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class GenerationInput:
    job_id: str
    prompt: str
    lyrics: str | None
    genre: str | None
    duration_seconds: int
    seed: int | None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    audio_path: Path
    provider: str
    model_name: str
    model_version: str
    seed: int | None
    duration_seconds: float
    generation_time_seconds: float
    peak_vram_mb: float | None
    file_type: str
    metadata_path: Path | None = None


class MusicGenerator(Protocol):
    model_name: str

    def generate(self, request: GenerationInput) -> GenerationResult:
        """Generate one validated audio file and return common metadata."""
        ...
