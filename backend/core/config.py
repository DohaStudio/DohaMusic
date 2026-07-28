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
    model_name: str = "mock-music-generator"
    worker_max_threads: int = Field(default=1, ge=1, le=8)
    mock_generation_delay_seconds: float = Field(default=3.0, ge=0, le=60)
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
            "MODEL_NAME": "model_name",
            "WORKER_MAX_THREADS": "worker_max_threads",
            "MOCK_GENERATION_DELAY_SECONDS": "mock_generation_delay_seconds",
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
