"""Run one dependency-free Mock Pipeline benchmark and print its metadata."""

from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path
from typing import Literal

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.core.config import Settings


def run_benchmark(
    audio_mixer: Literal["mock", "default"] = "mock",
) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="dohamusic-pipeline-") as temp_dir:
        root = Path(temp_dir)
        app = create_app(
            Settings(
                database_url=f"sqlite:///{(root / 'benchmark.db').as_posix()}",
                storage_root=root / "storage",
                mock_generation_delay_seconds=0.01,
                mock_stem_delay_seconds=0.01,
                mock_voice_delay_seconds=0.01,
                audio_mixer=audio_mixer,
                worker_max_threads=1,
                log_level="WARNING",
            )
        )
        with TestClient(app) as client:
            storage = client.app.state.storage
            reference = storage.voice_references_dir / "benchmark-reference.wav"
            shutil.copyfile(storage.sample_file, reference)
            profile = client.post(
                "/api/voice-profiles",
                json={
                    "name": "Pipeline benchmark",
                    "reference_file_path": "voices/references/benchmark-reference.wav",
                    "consent_confirmed": True,
                },
            )
            profile.raise_for_status()
            response = client.post(
                "/api/pipelines",
                json={
                    "prompt": "Mock pipeline benchmark",
                    "duration_seconds": 10,
                    "seed": 20260729,
                    "voice_profile_id": profile.json()["id"],
                },
            )
            response.raise_for_status()
            job_id = response.json()["id"]
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                job = client.get(f"/api/pipelines/{job_id}").json()
                if job["status"] in {"COMPLETED", "FAILED"}:
                    return job["result_metadata"]
                time.sleep(0.01)
            raise TimeoutError("Mock Pipeline benchmark timed out")


def main() -> int:
    result = run_benchmark()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("success") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
