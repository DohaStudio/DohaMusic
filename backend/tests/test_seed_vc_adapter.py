from pathlib import Path

import pytest

from backend.ai.adapters.seed_vc.adapter import SeedVCAdapter
from backend.ai.adapters.seed_vc.config import SeedVCConfig
from backend.ai.adapters.seed_vc.runtime import SeedVCRuntimeResult
from backend.ai.errors import VoiceOutputNotCreatedError, VoiceProviderNotConfiguredError
from backend.ai.interfaces.voice_converter import VoiceConversionInput


def config(tmp_path: Path) -> SeedVCConfig:
    return SeedVCConfig(
        runtime_python=tmp_path / "python.exe",
        runner_path=tmp_path / "runner.py",
        project_root=tmp_path / "seed-vc",
        checkpoint_path=tmp_path / "model.pth",
        config_path=tmp_path / "model.yml",
        model_cache_path=tmp_path / "cache",
        voice_root=tmp_path / "voices",
        model_name="seed-uvit-whisper-base-f0-44k",
        model_version="pinned-commit",
        device="cuda",
        diffusion_steps=30,
        timeout_seconds=60,
    )


class RuntimeStub:
    def __init__(self, result: SeedVCRuntimeResult) -> None:
        self.result = result

    def convert(self, source_path: Path, reference_path: Path, job_id: str) -> SeedVCRuntimeResult:
        return self.result


def test_seed_vc_adapter_maps_runtime_result(tmp_path: Path) -> None:
    output = tmp_path / "converted.wav"
    metadata = tmp_path / "metadata.json"
    output.write_bytes(b"wav")
    metadata.write_text("{}", encoding="utf-8")
    runtime_result = SeedVCRuntimeResult(output, metadata, 5.0, 2.0, 4000.0, 1000.0)
    adapter = SeedVCAdapter(config(tmp_path), RuntimeStub(runtime_result))
    result = adapter.convert(
        VoiceConversionInput("job", tmp_path / "source.wav", tmp_path / "reference.wav")
    )
    assert result.provider == "seed_vc"
    assert result.converted_path == output
    assert result.peak_vram_mb == 4000.0


def test_seed_vc_adapter_rejects_missing_output(tmp_path: Path) -> None:
    result = SeedVCRuntimeResult(tmp_path / "missing.wav", tmp_path / "m.json", 0, 0, None, None)
    with pytest.raises(VoiceOutputNotCreatedError):
        SeedVCAdapter(config(tmp_path), RuntimeStub(result)).convert(
            VoiceConversionInput("job", tmp_path / "source.wav", tmp_path / "reference.wav")
        )


def test_seed_vc_config_requires_all_runtime_assets(tmp_path: Path) -> None:
    with pytest.raises(VoiceProviderNotConfiguredError):
        config(tmp_path).validate()
