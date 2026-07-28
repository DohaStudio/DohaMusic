from __future__ import annotations

import time

from fastapi.testclient import TestClient


def wait_for_terminal_state(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        response = client.get(f"/api/generations/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"COMPLETED", "FAILED"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Job did not reach a terminal state")


def test_create_get_and_list_mock_generation_files(client: TestClient) -> None:
    response = client.post(
        "/api/generations",
        json={
            "prompt": "잔잔한 피아노 발라드",
            "lyrics": "테스트 가사",
            "genre": "ballad",
            "duration_seconds": 30,
            "seed": 42,
        },
    )

    assert response.status_code == 202
    created = response.json()
    assert created["status"] == "PENDING"

    completed = wait_for_terminal_state(client, created["id"])
    assert completed["status"] == "COMPLETED"
    assert completed["current_step"] == "completed"

    files_response = client.get(f"/api/generations/{created['id']}/files")
    assert files_response.status_code == 200
    files = files_response.json()
    assert len(files) == 1
    assert files[0]["file_type"] == "mock_audio"
    assert files[0]["file_path"].endswith("generated.wav")


def test_generation_not_found_returns_stable_error(client: TestClient) -> None:
    response = client.get("/api/generations/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_generation_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/generations",
        json={"prompt": "", "duration_seconds": 0},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


class FailingMusicGenerator:
    def generate(self, _request: object) -> None:
        raise RuntimeError("expected test failure")


def test_worker_failure_updates_job_state(client: TestClient) -> None:
    client.app.state.worker.music_generator = FailingMusicGenerator()
    response = client.post(
        "/api/generations",
        json={"prompt": "실패 경로 테스트", "duration_seconds": 10},
    )
    assert response.status_code == 202

    failed = wait_for_terminal_state(client, response.json()["id"])
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == "MOCK_GENERATION_FAILED"
    assert failed["error_message"] == "Mock 생성 작업에 실패했습니다."
