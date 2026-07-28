"""Deterministic mock stem separator without optional AI dependencies."""

from __future__ import annotations

import json
import math
import struct
import time
import wave
from pathlib import Path

from backend.ai.interfaces.stem_separator import (
    StemSeparationInput,
    StemSeparationResult,
)


class MockStemSeparator:
    provider = "mock"

    def __init__(
        self,
        stem_root: Path,
        delay_seconds: float,
        model_name: str = "mock-stem-separator",
        model_version: str = "foundation-v1",
    ) -> None:
        self.stem_root = stem_root
        self.delay_seconds = delay_seconds
        self.model_name = model_name
        self.model_version = model_version

    def separate(self, request: StemSeparationInput) -> StemSeparationResult:
        started_at = time.perf_counter()
        time.sleep(self.delay_seconds)
        vocals_path = self.stem_root / "vocals" / f"{request.job_id}.wav"
        instrumental_path = self.stem_root / "instrumentals" / f"{request.job_id}.wav"
        metadata_path = self.stem_root / "metadata" / f"{request.job_id}.json"
        for path in (vocals_path, instrumental_path, metadata_path):
            path.parent.mkdir(parents=True, exist_ok=True)
        self._write_tone(vocals_path, frequency=440.0)
        self._write_tone(instrumental_path, frequency=220.0)
        elapsed = time.perf_counter() - started_at
        metadata_path.write_text(
            json.dumps(
                {
                    "success": True,
                    "provider": self.provider,
                    "model_name": self.model_name,
                    "model_version": self.model_version,
                    "duration_actual": 0.1,
                    "separation_time_seconds": round(elapsed, 3),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        return StemSeparationResult(
            vocals_path=vocals_path,
            instrumental_path=instrumental_path,
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
            duration_seconds=0.1,
            separation_time_seconds=elapsed,
            peak_vram_mb=None,
            peak_process_memory_mb=None,
            metadata_path=metadata_path,
        )

    @staticmethod
    def _write_tone(path: Path, frequency: float) -> None:
        sample_rate = 48_000
        frames = bytearray()
        for index in range(sample_rate // 10):
            value = int(1_000 * math.sin(2 * math.pi * frequency * index / sample_rate))
            frames.extend(struct.pack("<hh", value, value))
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(2)
            audio.setsampwidth(2)
            audio.setframerate(sample_rate)
            audio.writeframes(frames)
