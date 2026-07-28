"""Deterministic file-copying mock music generator."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from backend.ai.interfaces.music_generator import GenerationInput


class MockMusicGenerator:
    def __init__(
        self,
        sample_file: Path,
        output_root: Path,
        delay_seconds: float,
        model_name: str = "mock-music-generator",
    ) -> None:
        self.sample_file = sample_file
        self.output_root = output_root
        self.delay_seconds = delay_seconds
        self.model_name = model_name

    def generate(self, request: GenerationInput) -> Path:
        time.sleep(self.delay_seconds)
        if not self.sample_file.is_file():
            raise FileNotFoundError("Mock sample audio is unavailable")
        job_output_dir = self.output_root / request.job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        output_file = job_output_dir / "generated.wav"
        shutil.copy2(self.sample_file, output_file)
        return output_file
