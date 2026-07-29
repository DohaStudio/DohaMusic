"""Replaceable audio mixer and exporter contracts with Phase 5 mock implementations."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True, slots=True)
class MixResult:
    audio_path: Path
    provider: str


class AudioMixer(Protocol):
    def mix(
        self, job_id: str, instrumental_path: Path, converted_voice_path: Path
    ) -> MixResult: ...


class MockAudioMixer:
    """Copy the converted vocal to prove the boundary without real audio mixing."""

    provider = "mock"

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root

    def mix(
        self, job_id: str, instrumental_path: Path, converted_voice_path: Path
    ) -> MixResult:
        if not instrumental_path.is_file() or not converted_voice_path.is_file():
            raise FileNotFoundError("Mixer input is unavailable")
        output = self.output_root / job_id / "mixed.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(converted_voice_path, output)
        return MixResult(audio_path=output, provider=self.provider)


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
