"""Select a StemSeparator without importing optional model dependencies."""

from pathlib import Path

from backend.ai.adapters.demucs import DemucsAdapter, DemucsConfig
from backend.ai.errors import StemProviderNotConfiguredError
from backend.ai.interfaces.stem_separator import StemSeparator
from backend.ai.mock.stem_separator import MockStemSeparator
from backend.core.config import Settings
from backend.storage.service import StorageService


def create_stem_separator(
    settings: Settings,
    storage: StorageService,
) -> StemSeparator:
    if settings.stem_provider == "mock":
        return MockStemSeparator(
            stem_root=storage.stems_dir,
            delay_seconds=settings.mock_stem_delay_seconds,
        )
    if settings.stem_provider == "demucs":
        return DemucsAdapter(
            DemucsConfig(
                runtime_python=Path(settings.demucs_runtime_python),
                runner_path=Path(settings.demucs_runner_path),
                model_cache_path=Path(settings.demucs_model_cache_path),
                stem_root=storage.stems_dir,
                model_name=settings.demucs_model_name,
                model_version=settings.demucs_model_version,
                device=settings.demucs_device,
                segment_seconds=settings.demucs_segment_seconds,
                shifts=settings.demucs_shifts,
                overlap=settings.demucs_overlap,
                timeout_seconds=settings.demucs_timeout_seconds,
            )
        )
    raise StemProviderNotConfiguredError(
        f"지원하지 않는 StemSeparator provider입니다: {settings.stem_provider}"
    )
