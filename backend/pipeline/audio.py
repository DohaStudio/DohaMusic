"""Replaceable audio exporter contract used after the Mixer step."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Protocol


class AudioExporter(Protocol):
    def export(self, job_id: str, source_path: Path) -> Path: ...


class WavExporter:
    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root

    def export(self, job_id: str, source_path: Path) -> Path:
        if not source_path.is_file():
            raise FileNotFoundError("Exporter input is unavailable")
        output = self.output_root / job_id / "final.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, output)
        return output
