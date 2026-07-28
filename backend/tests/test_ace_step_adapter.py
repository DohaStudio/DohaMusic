from __future__ import annotations

from pathlib import Path

import pytest

from backend.ai.adapters.ace_step.adapter import AceStepAdapter
from backend.ai.adapters.ace_step.config import AceStepConfig
from backend.ai.adapters.ace_step.mapper import to_runner_request
from backend.ai.adapters.ace_step.runtime import (
    AceStepRuntimeResult,
    SubprocessAceStepRuntime,
)
from backend.ai.errors import (
    AIDependencyNotInstalledError,
    AIModelLoadError,
    AIOutOfMemoryError,
    AIOutputNotCreatedError,
    AIProviderNotConfiguredError,
)
from backend.ai.factory import create_music_generator
from backend.ai.interfaces.music_generator import GenerationInput
from backend.core.config import Settings
from backend.storage.service import StorageService


def generation_input() -> GenerationInput:
    return GenerationInput(
        job_id="job-1",
        prompt="테스트 프롬프트",
        lyrics="테스트 가사",
        genre="ballad",
        duration_seconds=20,
        seed=42,
    )


def ace_config(tmp_path: Path) -> AceStepConfig:
    runtime_python = tmp_path / "python.exe"
    runner_path = tmp_path / "runner.py"
    runtime_python.touch()
    runner_path.touch()
    project_root = tmp_path / "project"
    checkpoint_path = tmp_path / "checkpoints"
    project_root.mkdir()
    checkpoint_path.mkdir()
    return AceStepConfig(
        runtime_python=runtime_python,
        runner_path=runner_path,
        project_root=project_root,
        checkpoint_path=checkpoint_path,
        output_root=tmp_path / "outputs",
        model_variant="test-variant",
        model_version="test-version",
        device="cuda",
        quantization="int8_weight_only",
        cpu_offload=True,
        dit_cpu_offload=True,
        timeout_seconds=30,
    )


class SuccessfulRuntime:
    def __init__(self, audio_path: Path, metadata_path: Path) -> None:
        self.audio_path = audio_path
        self.metadata_path = metadata_path
        self.request: dict[str, object] | None = None

    def generate(
        self,
        request: dict[str, object],
        _job_id: str,
    ) -> AceStepRuntimeResult:
        self.request = request
        return AceStepRuntimeResult(
            audio_path=self.audio_path,
            metadata_path=self.metadata_path,
            duration_seconds=20.0,
            generation_time_seconds=12.5,
            peak_vram_mb=4096.0,
            seed=42,
        )


def test_common_request_maps_to_ace_step_runner_contract() -> None:
    mapped = to_runner_request(generation_input())
    assert mapped["prompt"] == "테스트 프롬프트"
    assert mapped["lyrics"] == "테스트 가사"
    assert mapped["instrumental"] is False
    assert mapped["duration_seconds"] == 20
    assert mapped["seed"] == 42


def test_missing_seed_requests_runtime_randomization() -> None:
    request = generation_input()
    request = GenerationInput(
        job_id=request.job_id,
        prompt=request.prompt,
        lyrics=request.lyrics,
        genre=request.genre,
        duration_seconds=request.duration_seconds,
        seed=None,
    )

    assert to_runner_request(request)["seed"] is None


def test_adapter_maps_runtime_result(tmp_path: Path) -> None:
    audio_path = tmp_path / "generated.wav"
    audio_path.write_bytes(b"RIFF-test")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text("{}", encoding="utf-8")
    runtime = SuccessfulRuntime(audio_path, metadata_path)

    result = AceStepAdapter(ace_config(tmp_path), runtime=runtime).generate(
        generation_input()
    )

    assert result.audio_path == audio_path
    assert result.provider == "ace_step"
    assert result.model_name == "test-variant"
    assert result.model_version == "test-version"
    assert result.generation_time_seconds == 12.5
    assert result.peak_vram_mb == 4096.0


def test_adapter_rejects_missing_output(tmp_path: Path) -> None:
    runtime = SuccessfulRuntime(tmp_path / "missing.wav", tmp_path / "metadata.json")
    adapter = AceStepAdapter(ace_config(tmp_path), runtime=runtime)
    with pytest.raises(AIOutputNotCreatedError):
        adapter.generate(generation_input())


def test_ace_step_config_reports_missing_runtime(tmp_path: Path) -> None:
    config = AceStepConfig(
        runtime_python=tmp_path / "missing-python.exe",
        runner_path=tmp_path / "missing-runner.py",
        project_root=tmp_path,
        checkpoint_path=tmp_path,
        output_root=tmp_path,
        model_variant="test-variant",
        model_version="test-version",
        device="cuda",
        quantization=None,
        cpu_offload=True,
        dit_cpu_offload=True,
        timeout_seconds=30,
    )
    with pytest.raises(AIDependencyNotInstalledError):
        config.validate()


def test_factory_rejects_unsupported_provider(tmp_path: Path) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.ensure_layout()
    with pytest.raises(AIProviderNotConfiguredError):
        create_music_generator(Settings(music_generator="unsupported"), storage)


def test_factory_builds_ace_adapter_without_importing_optional_runtime(
    tmp_path: Path,
) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.ensure_layout()
    settings = Settings(
        music_generator="ace_step",
        ace_step_runtime_python=str(tmp_path / "missing-python.exe"),
        ace_step_runner_path=str(tmp_path / "missing-runner.py"),
        ace_step_project_root=str(tmp_path / "missing-project"),
        ace_step_checkpoint_path=str(tmp_path / "missing-checkpoints"),
    )

    generator = create_music_generator(settings, storage)

    assert isinstance(generator, AceStepAdapter)


def test_runtime_maps_oom_error() -> None:
    with pytest.raises(AIOutOfMemoryError):
        SubprocessAceStepRuntime._raise_failure(
            {
                "error_code": "AI_OUT_OF_MEMORY",
                "error_message": "test OOM",
            }
        )


def test_runtime_maps_model_load_error() -> None:
    with pytest.raises(AIModelLoadError):
        SubprocessAceStepRuntime._raise_failure(
            {
                "error_code": "AI_MODEL_LOAD_FAILED",
                "error_message": "test load failure",
            }
        )


def test_settings_load_ace_step_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DOHAMUSIC_MUSIC_GENERATOR", "ace_step")
    monkeypatch.setenv("DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT", "custom-variant")
    monkeypatch.setenv("DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD", "false")

    settings = Settings.from_environment()

    assert settings.music_generator == "ace_step"
    assert settings.ace_step_model_variant == "custom-variant"
    assert settings.ace_step_cpu_offload is False
