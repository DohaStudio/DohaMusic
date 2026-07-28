from fastapi.testclient import TestClient


def test_create_and_delete_consented_voice_profile(client: TestClient) -> None:
    response = client.post(
        "/api/voice-profiles",
        json={
            "name": "본인 테스트 음성",
            "reference_file_path": "voices/reference.wav",
            "consent_confirmed": True,
        },
    )
    assert response.status_code == 201
    profile = response.json()
    assert profile["consent_confirmed"] is True

    delete_response = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert delete_response.status_code == 204

    missing_response = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert missing_response.status_code == 404


def test_voice_profile_requires_explicit_consent(client: TestClient) -> None:
    response = client.post(
        "/api/voice-profiles",
        json={
            "name": "동의 없는 음성",
            "reference_file_path": "voices/reference.wav",
            "consent_confirmed": False,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "INVALID_INPUT"
