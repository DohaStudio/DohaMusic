"""Opt-in ACE-Step 반복 추론 벤치마크; 모델을 자동 다운로드하지 않는다."""

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
    pytest.mark.benchmark,
    pytest.mark.skipif(
        os.getenv("RUN_ACE_STEP_BENCHMARK") != "1",
        reason="set RUN_ACE_STEP_BENCHMARK=1 after installing the isolated runtime",
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


def test_installed_ace_step_runtime_repeats_all_cases(tmp_path: Path) -> None:
    runtime_python = required_path("DOHAMUSIC_AI_ACE_STEP_RUNTIME_PYTHON")
    project_root = required_path("DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT")
    required_path("DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH")
    repository_root = Path(__file__).parents[3]
    runner = repository_root / "ai_worker/scripts/run_ace_step_benchmark.py"
    suite = repository_root / "ai_worker/benchmarks/quality-resident.json"
    result_path = tmp_path / "benchmark.json"

    completed = subprocess.run(
        [
            str(runtime_python),
            str(runner),
            "--suite",
            str(suite),
            "--output-dir",
            str(tmp_path / "outputs"),
            "--metadata-path",
            str(result_path),
        ],
        cwd=project_root,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=1_200,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["summary"]["success_count"] == 6
    assert result["summary"]["failure_count"] == 0
    output_dir = tmp_path / "outputs"
    assert all((output_dir / run["output_file"]).is_file() for run in result["runs"])
