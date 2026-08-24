"""Model-independent Demucs stem separator adapter."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from backend.ai.adapters.demucs.config import DemucsConfig
from backend.ai.adapters.demucs.runtime import (
    DemucsRuntimeResult,
    SubprocessDemucsRuntime,
)
from backend.ai.errors import StemOutputNotCreatedError
from backend.ai.interfaces.stem_separator import (
    StemSeparationInput,
    StemSeparationResult,
)


class DemucsRuntime(Protocol):
    def separate(self, source_path: Path, job_id: str) -> DemucsRuntimeResult: ...


class DemucsAdapter:
    provider = "demucs"

    def __init__(
        self,
        config: DemucsConfig,
        runtime: DemucsRuntime | None = None,
    ) -> None:
        self.config = config
        self.runtime = runtime or SubprocessDemucsRuntime(config)
        self.model_name = config.model_name

    def separate(self, request: StemSeparationInput) -> StemSeparationResult:
        result = self.runtime.separate(request.source_path, request.job_id)
        for path in (result.vocals_path, result.instrumental_path):
            if not path.is_file() or path.stat().st_size == 0:
                raise StemOutputNotCreatedError("Demucs Stem 출력 파일이 생성되지 않았습니다.")
        return StemSeparationResult(
            vocals_path=result.vocals_path,
            instrumental_path=result.instrumental_path,
            provider=self.provider,
            model_name=self.config.model_name,
            model_version=self.config.model_version,
            duration_seconds=result.duration_seconds,
            separation_time_seconds=result.separation_time_seconds,
            peak_vram_mb=result.peak_vram_mb,
            peak_process_memory_mb=result.peak_process_memory_mb,
            metadata_path=result.metadata_path,
        )
