from __future__ import annotations

import shutil
import time
import wave

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.ai.errors import VoiceInferenceError
from backend.models.stem_file import StemFile
from backend.models.voice_conversion_file import VoiceConversionFile


def wait_for_terminal(client: TestClient, endpoint: str, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"{endpoint}/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in {"COMPLETED", "FAILED"}:
            return job
        time.sleep(0.01)
    raise AssertionError("Job did not reach a terminal state")


def prepare_inputs(client: TestClient) -> tuple[str, str]:
    generation = client.post(
        "/api/generations",
        json={"prompt": "Voice conversion test", "duration_seconds": 10},
    )
    generated = wait_for_terminal(client, "/api/generations", generation.json()["id"])
    generated_file_id = client.get(f"/api/generations/{generated['id']}/files").json()[0]["id"]
    stem = client.post("/api/stems", json={"source_file_id": generated_file_id})
    stemmed = wait_for_terminal(client, "/api/stems", stem.json()["id"])
    files = client.get(f"/api/stems/{stemmed['id']}/files").json()
    vocals = next(item for item in files if item["file_type"] == "vocals")

    storage = client.app.state.storage
    reference = storage.voice_references_dir / "consented-test.wav"
    with client.app.state.session_factory() as session:
        vocal_record = session.scalar(select(StemFile).where(StemFile.id == vocals["id"]))
        assert vocal_record is not None
        source_path = storage.resolve_relative_path(vocal_record.file_path)
    shutil.copyfile(source_path, reference)
    profile = client.post(
        "/api/voice-profiles",
        json={
            "name": "동의된 테스트 음성",
            "reference_file_path": "voices/references/consented-test.wav",
            "consent_confirmed": True,
        },
    )
    assert profile.status_code == 201
    return vocals["id"], profile.json()["id"]


def test_create_get_and_list_mock_voice_conversion(client: TestClient) -> None:
    source_file_id, profile_id = prepare_inputs(client)
    response = client.post(
        "/api/voice-conversion",
        json={"source_file_id": source_file_id, "voice_profile_id": profile_id},
    )
    assert response.status_code == 202
    assert response.json()["status"] == "PENDING"

    completed = wait_for_terminal(client, "/api/voice-conversion", response.json()["id"])
    assert completed["status"] == "COMPLETED"
    assert completed["provider"] == "mock"
    files = client.get(f"/api/voice-conversion/{completed['id']}/files").json()
    assert {item["file_type"] for item in files} == {"converted_voice", "metadata"}
    output = next(item for item in files if item["file_type"] == "converted_voice")
    assert "file_path" not in output
    with client.app.state.session_factory() as session:
        output_record = session.scalar(
            select(VoiceConversionFile).where(VoiceConversionFile.id == output["id"])
        )
        assert output_record is not None
        path = client.app.state.storage.resolve_relative_path(output_record.file_path)
    with wave.open(str(path), "rb") as audio:
        assert audio.getframerate() == 48_000
        assert audio.getnchannels() == 2


def test_voice_conversion_rejects_missing_or_non_vocal_input(
    client: TestClient,
) -> None:
    missing = "00000000-0000-0000-0000-000000000000"
    response = client.post(
        "/api/voice-conversion",
        json={"source_file_id": missing, "voice_profile_id": missing},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert client.get("/api/voice-conversion/missing").status_code == 404
    assert client.get("/api/voice-conversion/missing/files").status_code == 404


def test_voice_conversion_validation_error(client: TestClient) -> None:
    response = client.post(
        "/api/voice-conversion",
        json={"source_file_id": "short", "voice_profile_id": "short"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


class FailingVoiceConverter:
    model_name = "failing-voice-converter"

    def convert(self, _request: object) -> None:
        raise VoiceInferenceError("expected test failure")


def test_voice_worker_failure_updates_job(client: TestClient) -> None:
    source_file_id, profile_id = prepare_inputs(client)
    client.app.state.voice_worker.voice_converter = FailingVoiceConverter()
    response = client.post(
        "/api/voice-conversion",
        json={"source_file_id": source_file_id, "voice_profile_id": profile_id},
    )
    failed = wait_for_terminal(client, "/api/voice-conversion", response.json()["id"])
    assert failed["status"] == "FAILED"
    assert failed["error_code"] == "VOICE_CONVERSION_FAILED"
    assert client.get(f"/api/voice-conversion/{failed['id']}/files").json() == []


def test_api_rejects_reference_outside_reference_directory(
    client: TestClient,
) -> None:
    profile = client.post(
        "/api/voice-profiles",
        json={
            "name": "잘못된 경로",
            "reference_file_path": "samples/sample.wav",
            "consent_confirmed": True,
        },
    )
    assert profile.status_code == 422
    assert profile.json()["error"]["code"] == "INVALID_VOICE_REFERENCE_PATH"
