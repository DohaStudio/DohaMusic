"""Validated configuration for the isolated Demucs runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.ai.errors import (
    StemDependencyNotInstalledError,
    StemModelNotFoundError,
    StemProviderNotConfiguredError,
)


@dataclass(frozen=True, slots=True)
class DemucsConfig:
    runtime_python: Path
    runner_path: Path
    model_cache_path: Path
    stem_root: Path
    model_name: str
    model_version: str
    device: str
    segment_seconds: float
    shifts: int
    overlap: float
    timeout_seconds: int

    def validate(self) -> None:
        if not self.runtime_python.is_file():
            raise StemDependencyNotInstalledError(
                "Demucs 격리 Python 실행 파일을 찾을 수 없습니다."
            )
        if not self.runner_path.is_file():
            raise StemDependencyNotInstalledError(
                "Demucs runner 스크립트를 찾을 수 없습니다."
            )
        if not self.model_cache_path.is_dir():
            raise StemModelNotFoundError("Demucs 모델 캐시를 찾을 수 없습니다.")
        if not any(self.model_cache_path.rglob("*.safetensors")):
            raise StemModelNotFoundError("Demucs checkpoint를 찾을 수 없습니다.")
        if not self.model_name or not self.model_version or not self.device:
            raise StemProviderNotConfiguredError(
                "Demucs 모델·버전·장치 설정이 필요합니다."
            )
