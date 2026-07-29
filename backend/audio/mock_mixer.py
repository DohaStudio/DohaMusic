"""Copy-only mixer retained for explicit tests and fallback development."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from backend.audio.interfaces import AudioMixInput, AudioMixResult


class MockAudioMixer:
    provider = "mock"

    def __init__(self, output_root: Path) -> None:
        self.output_root = output_root

    def mix(self, request: AudioMixInput) -> AudioMixResult:
        started_at = time.perf_counter()
        if not request.instrumental_path.is_file() or not request.vocals_path.is_file():
            raise FileNotFoundError("Mixer input is unavailable")
        output = self.output_root / request.job_id / "mixed.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(request.vocals_path, output)
        elapsed = time.perf_counter() - started_at
        return AudioMixResult(
            audio_path=output,
            provider=self.provider,
            mixing_time_seconds=elapsed,
            metadata={
                "provider": self.provider,
                "mock": True,
                "mixing_time_seconds": elapsed,
            },
        )
