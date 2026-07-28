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


class MusicGenerator(Protocol):
    def generate(self, request: GenerationInput) -> Path:
        """Generate one audio file and return its local path."""
        ...
