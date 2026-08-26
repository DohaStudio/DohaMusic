"""Model-independent ACE-Step music generator adapter."""

from __future__ import annotations

from typing import Protocol

from backend.ai.adapters.ace_step.config import AceStepConfig
from backend.ai.adapters.ace_step.mapper import to_runner_request
from backend.ai.adapters.ace_step.runtime import (
    AceStepRuntimeResult,
    SubprocessAceStepRuntime,
)
from backend.ai.errors import AIOutputNotCreatedError
from backend.ai.interfaces.music_generator import GenerationInput, GenerationResult


class AceStepRuntime(Protocol):
    def generate(
        self,
        request: dict[str, object],
        job_id: str,
    ) -> AceStepRuntimeResult: ...


class AceStepAdapter:
    provider = "ace_step"

    def __init__(
        self,
        config: AceStepConfig,
        runtime: AceStepRuntime | None = None,
    ) -> None:
        self.config = config
        self.runtime = runtime or SubprocessAceStepRuntime(config)
        self.model_name = config.model_variant

    def generate(self, request: GenerationInput) -> GenerationResult:
        runtime_result = self.runtime.generate(to_runner_request(request), request.job_id)
        if not runtime_result.audio_path.is_file() or runtime_result.audio_path.stat().st_size == 0:
            raise AIOutputNotCreatedError("ACE-Step 출력 파일이 생성되지 않았습니다.")
        return GenerationResult(
            audio_path=runtime_result.audio_path,
            provider=self.provider,
            model_name=self.config.model_variant,
            model_version=self.config.model_version,
            seed=runtime_result.seed,
            duration_seconds=runtime_result.duration_seconds,
            generation_time_seconds=runtime_result.generation_time_seconds,
            peak_vram_mb=runtime_result.peak_vram_mb,
            file_type="generated_audio",
            metadata_path=runtime_result.metadata_path,
        )
