"""Provider-neutral voice conversion contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class VoiceConversionInput:
    job_id: str
    source_path: Path
    reference_path: Path


@dataclass(frozen=True, slots=True)
class VoiceConversionResult:
    converted_path: Path
    metadata_path: Path | None
    provider: str
    model_name: str
    model_version: str
    duration_seconds: float
    conversion_time_seconds: float
    peak_vram_mb: float | None = None
    peak_process_memory_mb: float | None = None


class VoiceConverter(Protocol):
    model_name: str

    def convert(self, request: VoiceConversionInput) -> VoiceConversionResult: ...
