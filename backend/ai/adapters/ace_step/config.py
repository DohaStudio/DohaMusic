"""Validated configuration for an isolated ACE-Step runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.ai.errors import (
    AIDependencyNotInstalledError,
    AIModelNotFoundError,
    AIProviderNotConfiguredError,
)


@dataclass(frozen=True, slots=True)
class AceStepConfig:
    runtime_python: Path
    runner_path: Path
    project_root: Path
    checkpoint_path: Path
    output_root: Path
    model_variant: str
    model_version: str
    device: str
    quantization: str | None
    cpu_offload: bool
    dit_cpu_offload: bool
    timeout_seconds: int

    def validate(self) -> None:
        if not self.runtime_python.is_file():
            raise AIDependencyNotInstalledError(
                "ACE-Step 격리 Python 실행 파일을 찾을 수 없습니다."
            )
        if not self.runner_path.is_file():
            raise AIDependencyNotInstalledError(
                "ACE-Step runner 스크립트를 찾을 수 없습니다."
            )
        if not self.project_root.is_dir():
            raise AIProviderNotConfiguredError(
                "ACE-Step 공식 프로젝트 경로가 준비되지 않았습니다."
            )
        if not self.checkpoint_path.is_dir():
            raise AIModelNotFoundError("ACE-Step checkpoint를 찾을 수 없습니다.")
        if not self.model_variant or not self.model_version:
            raise AIProviderNotConfiguredError(
                "ACE-Step 모델 variant와 version 설정이 필요합니다."
            )
        if not (self.checkpoint_path / self.model_variant).is_dir():
            raise AIModelNotFoundError(
                "설정한 ACE-Step 모델 variant를 checkpoint에서 찾을 수 없습니다."
            )
