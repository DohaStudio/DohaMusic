from __future__ import annotations

import time
import wave

from fastapi.testclient import TestClient

from backend.ai.errors import StemInferenceError


def wait_for_generation(client: TestClient, job_id: str) -> dict[str, object]:
    return wait_for_terminal_state(client, "/api/generations", job_id)


def wait_for_stem(client: TestClient, job_id: str) -> dict[str, object]:
    return wait_for_terminal_state(client, "/api/stems", job_id)


def wait_for_terminal_state(
    client: TestClient,
    endpoint: str,
    job_id: str,
) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        response = client.get(f"{endpoint}/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"COMPLETED", "FAILED"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Job did not reach a terminal state")


def create_source_file(client: TestClient) -> str:
    response = client.post(
        "/api/generations",
        json={"prompt": "Stem 분리 테스트", "duration_seconds": 10},
    )
    assert response.status_code == 202
    completed = wait_for_generation(client, response.json()["id"])
    assert completed["status"] == "COMPLETED"
    files = client.get(f"/api/generations/{completed['id']}/files").json()
    return str(files[0]["id"])


def test_create_get_and_list_mock_stems(client: TestClient) -> None:
    source_file_id = create_source_file(client)

    response = client.post("/api/stems", json={"source_file_id": source_file_id})
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"

    completed = wait_for_stem(client, response.json()["id"])
    assert completed["status"] == "COMPLETED"
    assert completed["current_step"] == "completed"
    assert completed["provider"] == "mock"
    assert completed["model_name"] == "mock-stem-separator"

    files_response = client.get(f"/api/stems/{completed['id']}/files")
    assert files_response.status_code == 200
    files = files_response.json()
    assert {item["file_type"] for item in files} == {
        "vocals",
        "instrumental",
        "metadata",
    }
    storage = client.app.state.storage
    for item in files:
        path = storage.resolve_relative_path(item["file_path"])
        assert path.is_file()
        assert path.stat().st_size > 0
        if item["file_type"] != "metadata":
            with wave.open(str(path), "rb") as audio:
                assert audio.getframerate() == 48_000
                assert audio.getnchannels() == 2


def test_stem_source_and_job_not_found_return_stable_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/stems",
        json={"source_file_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    response = client.get("/api/stems/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"

    response = client.get("/api/stems/missing/files")
    assert response.status_code == 404


def test_stem_validation_error(client: TestClient) -> None:
    response = client.post("/api/stems", json={"source_file_id": "short"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


class FailingStemSeparator:
    model_name = "failing-stem-separator"

    def separate(self, _request: object) -> None:
        raise StemInferenceError("expected test failure")


def test_stem_worker_failure_updates_job_state(client: TestClient) -> None:
    source_file_id = create_source_file(client)
    client.app.state.stem_worker.stem_separator = FailingStemSeparator()

    response = client.post("/api/stems", json={"source_file_id": source_file_id})
    assert response.status_code == 202
    failed = wait_for_stem(client, response.json()["id"])
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == "STEM_SEPARATION_FAILED"
    assert failed["error_message"] == "Stem 분리 작업에 실패했습니다."
    assert client.get(f"/api/stems/{failed['id']}/files").json() == []
