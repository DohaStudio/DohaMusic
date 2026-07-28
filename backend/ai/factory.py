"""Select a music generator without importing optional model dependencies."""

from pathlib import Path

from backend.ai.adapters.ace_step import AceStepAdapter, AceStepConfig
from backend.ai.errors import AIProviderNotConfiguredError
from backend.ai.interfaces.music_generator import MusicGenerator
from backend.ai.mock.music_generator import MockMusicGenerator
from backend.core.config import Settings
from backend.storage.service import StorageService


def create_music_generator(
    settings: Settings,
    storage: StorageService,
) -> MusicGenerator:
    if settings.music_generator == "mock":
        return MockMusicGenerator(
            sample_file=storage.sample_file,
            output_root=storage.outputs_dir,
            delay_seconds=settings.mock_generation_delay_seconds,
            model_name=settings.model_name,
            model_version=settings.model_version,
        )
    if settings.music_generator == "ace_step":
        config = AceStepConfig(
            runtime_python=Path(settings.ace_step_runtime_python),
            runner_path=Path(settings.ace_step_runner_path),
            project_root=Path(settings.ace_step_project_root),
            checkpoint_path=Path(settings.ace_step_checkpoint_path),
            output_root=storage.outputs_dir,
            model_variant=settings.ace_step_model_variant,
            model_version=settings.ace_step_model_version,
            device=settings.ace_step_device,
            quantization=settings.ace_step_quantization,
            cpu_offload=settings.ace_step_cpu_offload,
            dit_cpu_offload=settings.ace_step_dit_cpu_offload,
            timeout_seconds=settings.ace_step_timeout_seconds,
        )
        return AceStepAdapter(config)
    raise AIProviderNotConfiguredError(
        f"지원하지 않는 MusicGenerator provider입니다: {settings.music_generator}"
    )
