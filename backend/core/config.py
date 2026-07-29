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
    stem_provider: str = "mock"
    mock_stem_delay_seconds: float = Field(default=0.1, ge=0, le=60)
    voice_provider: str = "mock"
    mock_voice_delay_seconds: float = Field(default=0.1, ge=0, le=60)
    pipeline_version: str = "1"
    pipeline_max_retries: int = Field(default=1, ge=0, le=5)
    pipeline_step_timeout_seconds: float = Field(default=900, ge=0.01, le=7_200)
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
    demucs_runtime_python: str = ""
    demucs_runner_path: str = "ai_worker/scripts/run_demucs_separation.py"
    demucs_model_cache_path: str = ""
    demucs_model_name: str = "htdemucs"
    demucs_model_version: str = "4.1.0"
    demucs_device: str = "cuda"
    demucs_segment_seconds: float = Field(default=7.0, ge=1.0, le=7.8)
    demucs_shifts: int = Field(default=1, ge=0, le=10)
    demucs_overlap: float = Field(default=0.25, ge=0.0, lt=1.0)
    demucs_timeout_seconds: int = Field(default=900, ge=10, le=7_200)
    seed_vc_runtime_python: str = ""
    seed_vc_runner_path: str = "ai_worker/scripts/run_seed_vc_conversion.py"
    seed_vc_project_root: str = ""
    seed_vc_checkpoint_path: str = ""
    seed_vc_config_path: str = ""
    seed_vc_model_cache_path: str = ""
    seed_vc_model_name: str = "seed-uvit-whisper-base-f0-44k"
    seed_vc_model_version: str = "51383efd921027683c89e5348211d93ff12ac2a8"
    seed_vc_device: str = "cuda"
    seed_vc_diffusion_steps: int = Field(default=30, ge=1, le=100)
    seed_vc_timeout_seconds: int = Field(default=1800, ge=10, le=7_200)
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
            "DOHAMUSIC_STEM_PROVIDER": "stem_provider",
            "MOCK_STEM_DELAY_SECONDS": "mock_stem_delay_seconds",
            "DOHAMUSIC_VOICE_PROVIDER": "voice_provider",
            "MOCK_VOICE_DELAY_SECONDS": "mock_voice_delay_seconds",
            "DOHAMUSIC_PIPELINE_VERSION": "pipeline_version",
            "DOHAMUSIC_PIPELINE_MAX_RETRIES": "pipeline_max_retries",
            "DOHAMUSIC_PIPELINE_STEP_TIMEOUT_SECONDS": "pipeline_step_timeout_seconds",
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
            "DOHAMUSIC_STEM_DEMUCS_RUNTIME_PYTHON": "demucs_runtime_python",
            "DOHAMUSIC_STEM_DEMUCS_RUNNER_PATH": "demucs_runner_path",
            "DOHAMUSIC_STEM_DEMUCS_MODEL_CACHE_PATH": "demucs_model_cache_path",
            "DOHAMUSIC_STEM_DEMUCS_MODEL_NAME": "demucs_model_name",
            "DOHAMUSIC_STEM_DEMUCS_MODEL_VERSION": "demucs_model_version",
            "DOHAMUSIC_STEM_DEMUCS_DEVICE": "demucs_device",
            "DOHAMUSIC_STEM_DEMUCS_SEGMENT_SECONDS": "demucs_segment_seconds",
            "DOHAMUSIC_STEM_DEMUCS_SHIFTS": "demucs_shifts",
            "DOHAMUSIC_STEM_DEMUCS_OVERLAP": "demucs_overlap",
            "DOHAMUSIC_STEM_DEMUCS_TIMEOUT_SECONDS": "demucs_timeout_seconds",
            "DOHAMUSIC_VOICE_SEED_VC_RUNTIME_PYTHON": "seed_vc_runtime_python",
            "DOHAMUSIC_VOICE_SEED_VC_RUNNER_PATH": "seed_vc_runner_path",
            "DOHAMUSIC_VOICE_SEED_VC_PROJECT_ROOT": "seed_vc_project_root",
            "DOHAMUSIC_VOICE_SEED_VC_CHECKPOINT_PATH": "seed_vc_checkpoint_path",
            "DOHAMUSIC_VOICE_SEED_VC_CONFIG_PATH": "seed_vc_config_path",
            "DOHAMUSIC_VOICE_SEED_VC_MODEL_CACHE_PATH": "seed_vc_model_cache_path",
            "DOHAMUSIC_VOICE_SEED_VC_MODEL_NAME": "seed_vc_model_name",
            "DOHAMUSIC_VOICE_SEED_VC_MODEL_VERSION": "seed_vc_model_version",
            "DOHAMUSIC_VOICE_SEED_VC_DEVICE": "seed_vc_device",
            "DOHAMUSIC_VOICE_SEED_VC_DIFFUSION_STEPS": "seed_vc_diffusion_steps",
            "DOHAMUSIC_VOICE_SEED_VC_TIMEOUT_SECONDS": "seed_vc_timeout_seconds",
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
