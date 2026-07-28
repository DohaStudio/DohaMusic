"""Deterministic file-copying mock music generator."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from backend.ai.interfaces.music_generator import GenerationInput, GenerationResult


class MockMusicGenerator:
    def __init__(
        self,
        sample_file: Path,
        output_root: Path,
        delay_seconds: float,
        model_name: str,
        model_version: str,
    ) -> None:
        self.sample_file = sample_file
        self.output_root = output_root
        self.delay_seconds = delay_seconds
        self.model_name = model_name
        self.model_version = model_version

    def generate(self, request: GenerationInput) -> GenerationResult:
        started_at = time.perf_counter()
        time.sleep(self.delay_seconds)
        if not self.sample_file.is_file():
            raise FileNotFoundError("Mock sample audio is unavailable")
        job_output_dir = self.output_root / request.job_id
        job_output_dir.mkdir(parents=True, exist_ok=True)
        output_file = job_output_dir / "generated.wav"
        shutil.copy2(self.sample_file, output_file)
        return GenerationResult(
            audio_path=output_file,
            provider="mock",
            model_name=self.model_name,
            model_version=self.model_version,
            seed=request.seed,
            duration_seconds=float(request.duration_seconds),
            generation_time_seconds=time.perf_counter() - started_at,
            peak_vram_mb=None,
            file_type="mock_audio",
        )
