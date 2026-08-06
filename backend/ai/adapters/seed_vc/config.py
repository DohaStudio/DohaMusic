"""Validated configuration for the isolated Seed-VC runtime."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from backend.ai.errors import VoiceProviderNotConfiguredError


@dataclass(frozen=True, slots=True)
class SeedVCConfig:
    runtime_python: Path
    runner_path: Path
    project_root: Path
    checkpoint_path: Path
    config_path: Path
    model_cache_path: Path
    voice_root: Path
    model_name: str
    model_version: str
    device: str
    diffusion_steps: int
    timeout_seconds: int

    def validate(self) -> None:
        required_files = {
            "runtime Python": self.runtime_python,
            "runner": self.runner_path,
            "checkpoint": self.checkpoint_path,
            "model config": self.config_path,
        }
        required_directories = {
            "Seed-VC project": self.project_root,
            "model cache": self.model_cache_path,
        }
        missing = [
            label for label, path in required_files.items() if not path.is_file()
        ]
        missing.extend(
            label for label, path in required_directories.items() if not path.is_dir()
        )
        if missing:
            raise VoiceProviderNotConfiguredError(
                "Seed-VC 설정이 준비되지 않았습니다: " + ", ".join(missing)
            )
