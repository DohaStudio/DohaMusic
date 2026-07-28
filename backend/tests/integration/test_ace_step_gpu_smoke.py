"""Opt-in ACE-Step GPU smoke test; never downloads models implicitly."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.gpu,
    pytest.mark.slow,
    pytest.mark.skipif(
        os.getenv("RUN_ACE_STEP_GPU_TEST") != "1",
        reason="set RUN_ACE_STEP_GPU_TEST=1 after installing the isolated runtime",
    ),
]


def required_path(name: str) -> Path:
    value = os.getenv(name)
    if not value:
        pytest.fail(f"{name} must point to an existing local installation")
    path = Path(value).resolve()
    if not path.exists():
        pytest.fail(f"{name} does not exist: {path}")
    return path


def test_installed_ace_step_runtime_generates_wav(tmp_path: Path) -> None:
    runtime_python = required_path("DOHAMUSIC_AI_ACE_STEP_RUNTIME_PYTHON")
    project_root = required_path("DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT")
    required_path("DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH")
    runner = Path(__file__).parents[3] / "ai_worker/scripts/run_ace_step_smoke_test.py"
    request = {
        "experiment_case": "pytest-gpu-smoke",
        "prompt": "calm ambient instrumental, soft piano and warm pads",
        "lyrics": "",
        "instrumental": True,
        "duration_seconds": 10,
        "seed": 20260729,
        "vocal_language": "unknown",
    }
    request_path = tmp_path / "request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")

    environment = os.environ.copy()
    environment.setdefault("DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT", "acestep-v15-turbo")
    environment.setdefault("DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION", "v0.1.8")
    environment.setdefault("DOHAMUSIC_AI_ACE_STEP_DEVICE", "cuda")
    environment.setdefault("DOHAMUSIC_AI_ACE_STEP_QUANTIZATION", "int8_weight_only")
    environment.setdefault("DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD", "true")
    environment.setdefault("DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD", "true")

    completed = subprocess.run(
        [
            str(runtime_python),
            str(runner),
            "--request-json",
            str(request_path),
            "--output-dir",
            str(tmp_path / "output"),
            "--metadata-path",
            str(tmp_path / "output" / "metadata.json"),
        ],
        cwd=project_root,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=900,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout.strip().splitlines()[-1])
    audio_path = tmp_path / "output" / result["output_path"]
    assert audio_path.is_file()
    assert audio_path.suffix == ".wav"
