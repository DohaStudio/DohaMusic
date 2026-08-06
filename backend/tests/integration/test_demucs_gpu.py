"""Opt-in end-to-end Backend API validation against the offline Demucs runtime."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.core.config import Settings

pytestmark = [pytest.mark.integration, pytest.mark.gpu, pytest.mark.slow]


def required_path(name: str) -> Path:
    value = os.getenv(name)
    if not value:
        pytest.skip(f"{name} is not configured")
    path = Path(value).resolve()
    if not path.exists():
        pytest.skip(f"{name} does not exist")
    return path


def wait_for_job(client: TestClient, endpoint: str, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        response = client.get(f"{endpoint}/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"COMPLETED", "FAILED"}:
            return job
        time.sleep(0.1)
    raise AssertionError("GPU integration job did not reach a terminal state")


def test_demucs_provider_completes_through_backend_api(tmp_path: Path) -> None:
    if os.getenv("RUN_DEMUCS_GPU_TEST") != "1":
        pytest.skip("set RUN_DEMUCS_GPU_TEST=1 to run the real Demucs integration")
    runtime_python = required_path("DEMUCS_TEST_RUNTIME_PYTHON")
    model_cache = required_path("DEMUCS_TEST_MODEL_CACHE")
    source_audio = required_path("DEMUCS_TEST_SOURCE_AUDIO")
    runner_path = Path("ai_worker/scripts/run_demucs_separation.py").resolve()
    app = create_app(
        Settings(
            database_url=f"sqlite:///{(tmp_path / 'demucs.db').as_posix()}",
            auto_migrate=True,
            storage_root=tmp_path / "storage",
            mock_generation_delay_seconds=0,
            stem_provider="demucs",
            demucs_runtime_python=str(runtime_python),
            demucs_runner_path=str(runner_path),
            demucs_model_cache_path=str(model_cache),
            demucs_model_name="htdemucs",
            demucs_model_version="4.1.0",
            demucs_device="cuda",
            demucs_segment_seconds=7.0,
            demucs_shifts=1,
            demucs_overlap=0.25,
            log_level="WARNING",
        )
    )
    with TestClient(app) as client:
        generation = client.post(
            "/api/generations",
            json={"prompt": "Demucs API integration", "duration_seconds": 20},
        ).json()
        generation = wait_for_job(client, "/api/generations", generation["id"])
        assert generation["status"] == "COMPLETED"
        source_file = client.get(f"/api/generations/{generation['id']}/files").json()[0]
        source_path = app.state.storage.resolve_relative_path(source_file["file_path"])
        shutil.copy2(source_audio, source_path)

        response = client.post(
            "/api/stems",
            json={"source_file_id": source_file["id"]},
        )
        assert response.status_code == 202
        stem_job = wait_for_job(client, "/api/stems", response.json()["id"])
        assert stem_job["status"] == "COMPLETED", stem_job
        assert stem_job["provider"] == "demucs"
        files = client.get(f"/api/stems/{stem_job['id']}/files").json()
        assert {item["file_type"] for item in files} == {
            "vocals",
            "instrumental",
            "metadata",
        }
