from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from backend.ai.adapters.demucs import DemucsAdapter, DemucsConfig
from backend.ai.adapters.demucs.runtime import (
    DemucsRuntimeResult,
    SubprocessDemucsRuntime,
)
from backend.ai.errors import (
    StemDependencyNotInstalledError,
    StemInferenceError,
    StemModelLoadError,
    StemModelNotFoundError,
    StemOutOfMemoryError,
    StemOutputNotCreatedError,
    StemProviderNotConfiguredError,
    StemTimeoutError,
)
from backend.ai.interfaces.stem_separator import StemSeparationInput
from backend.ai.mock.stem_separator import MockStemSeparator
from backend.ai.stem_factory import create_stem_separator
from backend.core.config import Settings
from backend.storage.service import StorageService


def demucs_config(tmp_path: Path) -> DemucsConfig:
    runtime_python = tmp_path / "python.exe"
    runner_path = tmp_path / "runner.py"
    model_cache_path = tmp_path / "models"
    runtime_python.touch()
    runner_path.touch()
    model_cache_path.mkdir()
    (model_cache_path / "htdemucs.safetensors").touch()
    return DemucsConfig(
        runtime_python=runtime_python,
        runner_path=runner_path,
        model_cache_path=model_cache_path,
        stem_root=tmp_path / "stems",
        model_name="htdemucs",
        model_version="4.1.0",
        device="cuda",
        segment_seconds=7.0,
        shifts=1,
        overlap=0.25,
        timeout_seconds=30,
    )


class SuccessfulRuntime:
    def __init__(self, result: DemucsRuntimeResult) -> None:
        self.result = result
        self.request: tuple[Path, str] | None = None

    def separate(self, source_path: Path, job_id: str) -> DemucsRuntimeResult:
        self.request = (source_path, job_id)
        return self.result


def runtime_result(tmp_path: Path) -> DemucsRuntimeResult:
    vocals_path = tmp_path / "vocals.wav"
    instrumental_path = tmp_path / "instrumental.wav"
    metadata_path = tmp_path / "metadata.json"
    vocals_path.write_bytes(b"RIFF-vocals")
    instrumental_path.write_bytes(b"RIFF-instrumental")
    metadata_path.write_text("{}", encoding="utf-8")
    return DemucsRuntimeResult(
        vocals_path=vocals_path,
        instrumental_path=instrumental_path,
        metadata_path=metadata_path,
        duration_seconds=20.0,
        separation_time_seconds=4.2,
        peak_vram_mb=2529.0,
        peak_process_memory_mb=1533.0,
    )


def test_adapter_maps_runtime_result(tmp_path: Path) -> None:
    source_path = tmp_path / "source.wav"
    source_path.touch()
    runtime = SuccessfulRuntime(runtime_result(tmp_path))

    result = DemucsAdapter(demucs_config(tmp_path), runtime).separate(
        StemSeparationInput(job_id="stem-job", source_path=source_path)
    )

    assert runtime.request == (source_path, "stem-job")
    assert result.provider == "demucs"
    assert result.model_name == "htdemucs"
    assert result.model_version == "4.1.0"
    assert result.duration_seconds == 20.0
    assert result.separation_time_seconds == 4.2
    assert result.peak_vram_mb == 2529.0


def test_adapter_rejects_missing_output(tmp_path: Path) -> None:
    result = runtime_result(tmp_path)
    result.instrumental_path.unlink()
    adapter = DemucsAdapter(demucs_config(tmp_path), SuccessfulRuntime(result))

    with pytest.raises(StemOutputNotCreatedError):
        adapter.separate(
            StemSeparationInput(job_id="missing-output", source_path=tmp_path)
        )


def test_config_reports_missing_runtime(tmp_path: Path) -> None:
    config = demucs_config(tmp_path)
    config.runtime_python.unlink()
    with pytest.raises(StemDependencyNotInstalledError):
        config.validate()


def test_config_reports_missing_model(tmp_path: Path) -> None:
    config = demucs_config(tmp_path)
    next(config.model_cache_path.rglob("*.safetensors")).unlink()
    with pytest.raises(StemModelNotFoundError):
        config.validate()


def test_factory_builds_mock_and_demucs_providers(tmp_path: Path) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.ensure_layout()
    assert isinstance(create_stem_separator(Settings(), storage), MockStemSeparator)
    separator = create_stem_separator(
        Settings(stem_provider="demucs", demucs_runtime_python="missing"), storage
    )
    assert isinstance(separator, DemucsAdapter)


def test_factory_rejects_unsupported_provider(tmp_path: Path) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.ensure_layout()
    with pytest.raises(StemProviderNotConfiguredError):
        create_stem_separator(Settings(stem_provider="unsupported"), storage)


@pytest.mark.parametrize(
    ("code", "error_type"),
    [
        ("STEM_OUT_OF_MEMORY", StemOutOfMemoryError),
        ("STEM_MODEL_LOAD_FAILED", StemModelLoadError),
        ("UNKNOWN", StemInferenceError),
    ],
)
def test_runtime_maps_stable_error_codes(
    code: str,
    error_type: type[Exception],
) -> None:
    with pytest.raises(error_type):
        SubprocessDemucsRuntime._raise_failure(
            {"error_code": code, "error_message": "expected"}
        )


def test_runtime_maps_subprocess_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = demucs_config(tmp_path)

    def raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("demucs", 30)

    monkeypatch.setattr(subprocess, "run", raise_timeout)
    with pytest.raises(StemTimeoutError):
        SubprocessDemucsRuntime(config).separate(tmp_path / "input.wav", "timeout")


def test_runtime_maps_abnormal_subprocess_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = demucs_config(tmp_path)
    completed = subprocess.CompletedProcess(
        args=["demucs"],
        returncode=3,
        stdout=(
            '{"success":false,"error_code":"STEM_SEPARATION_FAILED",'
            '"error_message":"expected"}'
        ),
        stderr="runtime failed",
    )
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: completed)
    with pytest.raises(StemInferenceError):
        SubprocessDemucsRuntime(config).separate(tmp_path / "input.wav", "failed")


def test_settings_load_demucs_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOHAMUSIC_STEM_PROVIDER", "demucs")
    monkeypatch.setenv("DOHAMUSIC_STEM_DEMUCS_MODEL_NAME", "custom-demucs")
    monkeypatch.setenv("DOHAMUSIC_STEM_DEMUCS_SEGMENT_SECONDS", "6.5")

    settings = Settings.from_environment()

    assert settings.stem_provider == "demucs"
    assert settings.demucs_model_name == "custom-demucs"
    assert settings.demucs_segment_seconds == 6.5
