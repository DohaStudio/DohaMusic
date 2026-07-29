"""Mutable data passed only through declared pipeline step boundaries."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class PipelineContext:
    job_id: str
    prompt: str
    lyrics: str | None
    genre: str | None
    duration_seconds: int
    seed: int | None
    voice_profile_id: str
    reference_voice_path: Path
    pipeline_version: str
    music_file: Path | None = None
    vocals_file: Path | None = None
    instrumental_file: Path | None = None
    converted_voice: Path | None = None
    mixed_file: Path | None = None
    output_file: Path | None = None
    metadata_file: Path | None = None
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)
    step_execution: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def generated_paths(self) -> tuple[Path, ...]:
        values = (
            self.music_file,
            self.vocals_file,
            self.instrumental_file,
            self.converted_voice,
            self.mixed_file,
            self.output_file,
        )
        return tuple(path for path in values if path is not None)
