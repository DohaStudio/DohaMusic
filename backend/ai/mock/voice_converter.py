"""Deterministic mock voice converter for local development and tests."""

from __future__ import annotations

import json
import shutil
import time
import wave
from pathlib import Path

from backend.ai.interfaces.voice_converter import (
    VoiceConversionInput,
    VoiceConversionResult,
)
from backend.storage.service import StorageService


class MockVoiceConverter:
    provider = "mock"
    model_name = "mock-voice-converter"
    model_version = "1"

    def __init__(self, storage: StorageService, delay_seconds: float = 0.1) -> None:
        self.storage = storage
        self.delay_seconds = delay_seconds

    def convert(self, request: VoiceConversionInput) -> VoiceConversionResult:
        started_at = time.perf_counter()
        if not request.source_path.is_file() or not request.reference_path.is_file():
            raise FileNotFoundError("Voice conversion input is unavailable")
        time.sleep(self.delay_seconds)
        output = self.storage.voice_converted_dir / f"{request.job_id}.wav"
        metadata = self.storage.voice_metadata_dir / f"{request.job_id}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        metadata.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(request.source_path, output)
        duration = _wav_duration(output)
        elapsed = time.perf_counter() - started_at
        metadata.write_text(
            json.dumps(
                {
                    "provider": self.provider,
                    "model_name": self.model_name,
                    "model_version": self.model_version,
                    "duration_seconds": duration,
                    "conversion_time_seconds": elapsed,
                    "mock": True,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return VoiceConversionResult(
            converted_path=output,
            metadata_path=metadata,
            provider=self.provider,
            model_name=self.model_name,
            model_version=self.model_version,
            duration_seconds=duration,
            conversion_time_seconds=elapsed,
        )


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as audio:
        return audio.getnframes() / audio.getframerate()
