from __future__ import annotations

import io
import wave
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.models.voice_profile import VoiceProfile
from backend.models.voice_sample import VoiceSample
from backend.services import voice_upload_service


def wav_bytes(
    duration_seconds: float = 5.1,
    *,
    sample_rate: int = 16_000,
    channels: int = 1,
    amplitude: int = 1_000,
) -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        sample = int(amplitude).to_bytes(2, "little", signed=True)
        audio.writeframes(sample * channels * int(duration_seconds * sample_rate))
    return target.getvalue()


def upload(
    client: TestClient,
    content: bytes | None = None,
    *,
    filename: str = "my-voice.wav",
    content_type: str = "audio/wav",
    consent: str | None = "true",
):
    data = {"name": "내 목소리", "consent_text_version": "v1"}
    if consent is not None:
        data["consent_confirmed"] = consent
    files = None if content is None else {"file": (filename, content, content_type)}
    return client.post("/api/voice-profiles/upload", data=data, files=files)


def test_upload_list_get_and_delete_voice_profile(client: TestClient) -> None:
    response = upload(client, wav_bytes())
    assert response.status_code == 201
    profile = response.json()
    assert profile["display_filename"] == "my-voice.wav"
    assert profile["mime_type"] == "audio/wav"
    assert profile["duration_seconds"] == 5.1
    assert profile["sample_rate"] == 16_000
    assert profile["channels"] == 1
    assert profile["status"] == "READY"
    assert profile["consent_text_version"] == "v1"
    assert "reference_file_path" not in profile
    assert not any("path" in key for key in profile)

    stored = client.app.state.storage.voice_references_dir / profile["id"] / "reference.wav"
    assert stored.is_file()
    assert stored.resolve().is_relative_to(client.app.state.storage.voice_references_dir.resolve())
    with client.app.state.session_factory() as session:
        persisted_profile = session.get(VoiceProfile, profile["id"])
        compatibility_sample = session.scalar(
            select(VoiceSample).where(VoiceSample.voice_profile_id == profile["id"])
        )
        assert persisted_profile.active_reference_sample_id == compatibility_sample.id
        assert compatibility_sample.source_type == "FILE_UPLOAD"
        assert compatibility_sample.status == "PROMOTED"

    listed = client.get("/api/voice-profiles")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [profile["id"]]
    detail = client.get(f"/api/voice-profiles/{profile['id']}")
    assert detail.status_code == 200
    assert detail.json() == profile

    deleted = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert deleted.status_code == 204
    assert not stored.exists()
    assert not stored.parent.exists()
    assert client.get(f"/api/voice-profiles/{profile['id']}").status_code == 404
    with client.app.state.session_factory() as session:
        assert (
            session.scalar(
                select(VoiceSample.id).where(VoiceSample.voice_profile_id == profile["id"])
            )
            is None
        )


def test_legacy_profile_has_nullable_upload_metadata(client: TestClient) -> None:
    storage = client.app.state.storage
    legacy = storage.voice_references_dir / "legacy.wav"
    legacy.write_bytes(wav_bytes())
    created = client.post(
        "/api/voice-profiles",
        json={
            "name": "legacy",
            "reference_file_path": "voices/references/legacy.wav",
            "consent_confirmed": True,
        },
    )
    assert created.status_code == 201
    profile = created.json()
    assert profile["display_filename"] is None
    assert profile["duration_seconds"] is None
    assert profile["quality_warnings"] == []
    assert client.get(f"/api/voice-profiles/{profile['id']}").status_code == 200


def test_empty_profile_list_and_missing_detail(client: TestClient) -> None:
    assert client.get("/api/voice-profiles").json() == []
    missing = client.get("/api/voice-profiles/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "VOICE_PROFILE_NOT_FOUND"


def test_upload_requires_file_and_consent(client: TestClient) -> None:
    no_file = upload(client)
    assert no_file.status_code == 422
    assert no_file.json()["error"]["code"] == "VOICE_FILE_REQUIRED"
    for consent in (None, "false"):
        response = upload(client, wav_bytes(), consent=consent)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VOICE_CONSENT_REQUIRED"


def test_upload_rejects_empty_short_long_and_corrupt_wav(client: TestClient) -> None:
    cases = [
        (b"", "VOICE_FILE_EMPTY"),
        (wav_bytes(1), "VOICE_FILE_TOO_SHORT"),
        (wav_bytes(60.1), "VOICE_FILE_TOO_LONG"),
        (b"RIFFbroken-WAVE", "VOICE_FILE_DECODE_FAILED"),
        (b"not a riff", "VOICE_FILE_DECODE_FAILED"),
    ]
    for content, code in cases:
        response = upload(client, content)
        assert response.status_code in {413, 422}
        assert response.json()["error"]["code"] == code
    assert list((client.app.state.storage.voice_references_dir / ".uploads").glob("*")) == []


def test_upload_rejects_extension_mime_and_traversal_filename(
    client: TestClient,
) -> None:
    cases = [
        ("voice.mp3", "audio/wav"),
        ("voice.wav", "audio/mpeg"),
        ("../voice.wav", "audio/wav"),
    ]
    for filename, content_type in cases:
        response = upload(client, wav_bytes(), filename=filename, content_type=content_type)
        assert response.status_code == 415
        assert response.json()["error"]["code"] == "VOICE_FILE_TYPE_UNSUPPORTED"


def test_streaming_upload_enforces_actual_size_limit(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(voice_upload_service, "MAX_VOICE_UPLOAD_BYTES", 128)
    response = upload(client, wav_bytes())
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "VOICE_FILE_TOO_LARGE"


def test_quality_warnings_are_public(client: TestClient) -> None:
    response = upload(client, wav_bytes(amplitude=0))
    assert response.status_code == 201
    assert response.json()["quality_warnings"] == [
        "LOW_VOLUME",
        "HIGH_SILENCE_RATIO",
    ]


def test_profile_in_use_cannot_be_deleted(client: TestClient) -> None:
    profile = upload(client, wav_bytes()).json()
    pipeline = client.post(
        "/api/pipelines",
        json={"prompt": "voice", "voice_profile_id": profile["id"]},
    )
    assert pipeline.status_code == 202
    response = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "VOICE_PROFILE_IN_USE"


def test_storage_delete_failure_preserves_profile_and_file(client: TestClient, monkeypatch) -> None:
    profile = upload(client, wav_bytes()).json()
    stored = client.app.state.storage.voice_references_dir / profile["id"] / "reference.wav"
    original_unlink = Path.unlink

    def fail_tombstone(self: Path, *args, **kwargs):
        if self.suffix == ".deleting":
            raise OSError("simulated")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_tombstone)
    response = client.delete(f"/api/voice-profiles/{profile['id']}")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "VOICE_STORAGE_DELETE_FAILED"
    assert stored.is_file()
    assert client.get(f"/api/voice-profiles/{profile['id']}").status_code == 200


def test_storage_write_failure_cleans_temporary_file(client: TestClient, monkeypatch) -> None:
    upload_dir = client.app.state.storage.voice_references_dir / ".uploads"
    original_replace = Path.replace

    def fail_replace(self: Path, target: Path):
        if self.parent == upload_dir:
            raise OSError("simulated")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", fail_replace)
    response = upload(client, wav_bytes())
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "VOICE_STORAGE_WRITE_FAILED"
    assert list(upload_dir.glob("*")) == []
