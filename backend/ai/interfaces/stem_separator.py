"""Model-independent vocal and instrumental separation contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class StemSeparationInput:
    job_id: str
    source_path: Path


@dataclass(frozen=True, slots=True)
class StemSeparationResult:
    vocals_path: Path
    instrumental_path: Path
    provider: str
    model_name: str
    model_version: str
    duration_seconds: float
    separation_time_seconds: float
    peak_vram_mb: float | None
    peak_process_memory_mb: float | None
    metadata_path: Path | None = None


class StemSeparator(Protocol):
    model_name: str

    def separate(self, request: StemSeparationInput) -> StemSeparationResult:
        """Separate one local mixture into 48 kHz stereo vocal and instrumental WAVs."""
        ...
