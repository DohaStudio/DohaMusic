"""Model-independent Seed-VC adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from backend.ai.adapters.seed_vc.config import SeedVCConfig
from backend.ai.adapters.seed_vc.runtime import (
    SeedVCRuntimeResult,
    SubprocessSeedVCRuntime,
)
from backend.ai.errors import VoiceOutputNotCreatedError
from backend.ai.interfaces.voice_converter import (
    VoiceConversionInput,
    VoiceConversionResult,
)


class SeedVCRuntime(Protocol):
    def convert(
        self, source_path: Path, reference_path: Path, job_id: str
    ) -> SeedVCRuntimeResult: ...


class SeedVCAdapter:
    provider = "seed_vc"

    def __init__(self, config: SeedVCConfig, runtime: SeedVCRuntime | None = None) -> None:
        self.config = config
        self.runtime = runtime or SubprocessSeedVCRuntime(config)
        self.model_name = config.model_name

    def convert(self, request: VoiceConversionInput) -> VoiceConversionResult:
        result = self.runtime.convert(request.source_path, request.reference_path, request.job_id)
        if not result.converted_path.is_file() or result.converted_path.stat().st_size == 0:
            raise VoiceOutputNotCreatedError("Seed-VC 출력 파일이 생성되지 않았습니다.")
        return VoiceConversionResult(
            converted_path=result.converted_path,
            metadata_path=result.metadata_path,
            provider=self.provider,
            model_name=self.config.model_name,
            model_version=self.config.model_version,
            duration_seconds=result.duration_seconds,
            conversion_time_seconds=result.conversion_time_seconds,
            peak_vram_mb=result.peak_vram_mb,
            peak_process_memory_mb=result.peak_process_memory_mb,
        )
