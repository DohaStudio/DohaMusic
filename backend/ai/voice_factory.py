"""Voice converter provider factory."""

from pathlib import Path

from backend.ai.adapters.seed_vc.adapter import SeedVCAdapter
from backend.ai.adapters.seed_vc.config import SeedVCConfig
from backend.ai.errors import VoiceProviderNotConfiguredError
from backend.ai.interfaces.voice_converter import VoiceConverter
from backend.ai.mock.voice_converter import MockVoiceConverter
from backend.core.config import Settings
from backend.storage.service import StorageService


def create_voice_converter(
    settings: Settings, storage: StorageService
) -> VoiceConverter:
    provider = settings.voice_provider.strip().lower()
    if provider == "mock":
        return MockVoiceConverter(storage, settings.mock_voice_delay_seconds)
    if provider == "seed_vc":
        return SeedVCAdapter(
            SeedVCConfig(
                runtime_python=Path(settings.seed_vc_runtime_python),
                runner_path=Path(settings.seed_vc_runner_path),
                project_root=Path(settings.seed_vc_project_root),
                checkpoint_path=Path(settings.seed_vc_checkpoint_path),
                config_path=Path(settings.seed_vc_config_path),
                model_cache_path=Path(settings.seed_vc_model_cache_path),
                voice_root=storage.voices_dir,
                model_name=settings.seed_vc_model_name,
                model_version=settings.seed_vc_model_version,
                device=settings.seed_vc_device,
                diffusion_steps=settings.seed_vc_diffusion_steps,
                timeout_seconds=settings.seed_vc_timeout_seconds,
            )
        )
    raise VoiceProviderNotConfiguredError(f"지원하지 않는 Voice Provider: {provider}")
