from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


def create_reference(client: TestClient, name: str = "profile.wav") -> Path:
    path = client.app.state.storage.voice_references_dir / name
    path.write_bytes(client.app.state.storage.sample_file.read_bytes())
    return path


def test_create_and_delete_consented_voice_profile(client: TestClient) -> None:
    create_reference(client)
    response = client.post(
        "/api/voice-profiles",
        json={
            "name": "본인 테스트 음성",
            "reference_file_path": "voices/references/profile.wav",
            "consent_confirmed": True,
        },
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["consent_confirmed"] is True
    assert "reference_file_path" not in profile

    delete_response = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert delete_response.status_code == 204

    missing_response = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert missing_response.status_code == 404


def test_voice_profile_requires_explicit_consent(client: TestClient) -> None:
    create_reference(client)
    response = client.post(
        "/api/voice-profiles",
        json={
            "name": "동의 없는 음성",
            "reference_file_path": "voices/references/profile.wav",
            "consent_confirmed": False,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"


@pytest.mark.parametrize(
    "reference_file_path",
    [
        "voices/references/missing.wav",
        "voices/references/profile.txt",
        "voices/references/../outside.wav",
        "samples/sample.wav",
        "C:/Windows/system.ini",
    ],
)
def test_voice_profile_rejects_invalid_reference_paths(
    client: TestClient, reference_file_path: str
) -> None:
    response = client.post(
        "/api/voice-profiles",
        json={
            "name": "잘못된 참조",
            "reference_file_path": reference_file_path,
            "consent_confirmed": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_VOICE_REFERENCE_PATH"


def test_voice_profile_rejects_symlink_reference(client: TestClient) -> None:
    storage = client.app.state.storage
    link = storage.voice_references_dir / "linked.wav"
    try:
        link.symlink_to(storage.sample_file)
    except OSError:
        pytest.skip("현재 Windows 권한에서 심볼릭 링크를 만들 수 없습니다.")

    response = client.post(
        "/api/voice-profiles",
        json={
            "name": "링크 참조",
            "reference_file_path": "voices/references/linked.wav",
            "consent_confirmed": True,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_VOICE_REFERENCE_PATH"
