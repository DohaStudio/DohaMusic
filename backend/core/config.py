"""Environment-backed application configuration."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Settings(BaseModel):
    """Validated runtime settings with safe local defaults."""

    model_config = ConfigDict(frozen=True)

    app_name: str = "DohaMusic Backend"
    database_url: str = "sqlite:///./backend/storage/doha_music.db"
    storage_root: Path = Path("backend/storage")
    music_generator: str = "mock"
    model_name: str = "mock-music-generator"
    model_version: str = "mock"
    worker_max_threads: int = Field(default=1, ge=1, le=8)
    mock_generation_delay_seconds: float = Field(default=3.0, ge=0, le=60)
    ace_step_runtime_python: str = ""
    ace_step_runner_path: str = ""
    ace_step_project_root: str = ""
    ace_step_checkpoint_path: str = ""
    ace_step_model_variant: str = "acestep-v15-turbo"
    ace_step_model_version: str = "v0.1.8"
    ace_step_device: str = "cuda"
    ace_step_quantization: str | None = "int8_weight_only"
    ace_step_cpu_offload: bool = True
    ace_step_dit_cpu_offload: bool = True
    ace_step_timeout_seconds: int = Field(default=900, ge=10, le=7_200)
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.upper()

    @classmethod
    def from_environment(cls) -> "Settings":
        """Read supported settings without loading or exposing secrets."""

        values: dict[str, object] = {}
        mapping = {
            "APP_NAME": "app_name",
            "DATABASE_URL": "database_url",
            "AUDIO_STORAGE_ROOT": "storage_root",
            "DOHAMUSIC_MUSIC_GENERATOR": "music_generator",
            "MODEL_NAME": "model_name",
            "MODEL_VERSION": "model_version",
            "WORKER_MAX_THREADS": "worker_max_threads",
            "MOCK_GENERATION_DELAY_SECONDS": "mock_generation_delay_seconds",
            "DOHAMUSIC_AI_ACE_STEP_RUNTIME_PYTHON": "ace_step_runtime_python",
            "DOHAMUSIC_AI_ACE_STEP_RUNNER_PATH": "ace_step_runner_path",
            "DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT": "ace_step_project_root",
            "DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH": "ace_step_checkpoint_path",
            "DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT": "ace_step_model_variant",
            "DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION": "ace_step_model_version",
            "DOHAMUSIC_AI_ACE_STEP_DEVICE": "ace_step_device",
            "DOHAMUSIC_AI_ACE_STEP_QUANTIZATION": "ace_step_quantization",
            "DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD": "ace_step_cpu_offload",
            "DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD": "ace_step_dit_cpu_offload",
            "DOHAMUSIC_AI_ACE_STEP_TIMEOUT_SECONDS": "ace_step_timeout_seconds",
            "LOG_LEVEL": "log_level",
        }
        for environment_name, field_name in mapping.items():
            value = os.getenv(environment_name)
            if value is not None:
                values[field_name] = value
        return cls.model_validate(values)


@lru_cache
def get_settings() -> Settings:
    return Settings.from_environment()
