"""Opt-in Seed-VC GPU integration test.

Run only with DOHAMUSIC_RUN_SEED_VC_GPU_TEST=1 and the documented runtime
environment variables. No personal reference audio is required or committed.
"""

from __future__ import annotations

import os
import wave
from pathlib import Path

import pytest

from backend.ai.adapters.seed_vc.adapter import SeedVCAdapter
from backend.ai.adapters.seed_vc.config import SeedVCConfig
from backend.ai.interfaces.voice_converter import VoiceConversionInput


@pytest.mark.integration
@pytest.mark.gpu
@pytest.mark.slow
def test_seed_vc_official_example_gpu(tmp_path: Path) -> None:
    if os.getenv("DOHAMUSIC_RUN_SEED_VC_GPU_TEST") != "1":
        pytest.skip("Set DOHAMUSIC_RUN_SEED_VC_GPU_TEST=1 for Seed-VC GPU test")

    required = {
        "runtime_python": os.getenv("DOHAMUSIC_VOICE_SEED_VC_RUNTIME_PYTHON", ""),
        "runner_path": os.getenv("DOHAMUSIC_VOICE_SEED_VC_RUNNER_PATH", ""),
        "project_root": os.getenv("DOHAMUSIC_VOICE_SEED_VC_PROJECT_ROOT", ""),
        "checkpoint_path": os.getenv("DOHAMUSIC_VOICE_SEED_VC_CHECKPOINT_PATH", ""),
        "config_path": os.getenv("DOHAMUSIC_VOICE_SEED_VC_CONFIG_PATH", ""),
        "model_cache_path": os.getenv("DOHAMUSIC_VOICE_SEED_VC_MODEL_CACHE_PATH", ""),
        "source": os.getenv("DOHAMUSIC_SEED_VC_TEST_SOURCE", ""),
        "reference": os.getenv("DOHAMUSIC_SEED_VC_TEST_REFERENCE", ""),
    }
    missing = [key for key, value in required.items() if not value]
    if missing:
        pytest.fail("Missing Seed-VC test settings: " + ", ".join(missing))

    config = SeedVCConfig(
        runtime_python=Path(required["runtime_python"]),
        runner_path=Path(required["runner_path"]),
        project_root=Path(required["project_root"]),
        checkpoint_path=Path(required["checkpoint_path"]),
        config_path=Path(required["config_path"]),
        model_cache_path=Path(required["model_cache_path"]),
        voice_root=tmp_path / "voices",
        model_name="seed-uvit-whisper-base-f0-44k",
        model_version="51383efd921027683c89e5348211d93ff12ac2a8",
        device="cuda",
        diffusion_steps=30,
        timeout_seconds=1800,
    )
    result = SeedVCAdapter(config).convert(
        VoiceConversionInput(
            job_id="gpu-test",
            source_path=Path(required["source"]),
            reference_path=Path(required["reference"]),
        )
    )
    assert result.converted_path.is_file()
    assert result.duration_seconds > 0
    assert result.peak_vram_mb is not None
    with wave.open(str(result.converted_path), "rb") as audio:
        assert audio.getframerate() == 48_000
        assert audio.getnchannels() == 2
