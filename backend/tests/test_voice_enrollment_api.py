from __future__ import annotations

import io
import json
import os
import shutil
import struct
import uuid
import wave
from array import array
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.models.voice_enrollment import VoiceEnrollment
from backend.models.voice_profile import VoiceProfile
from backend.models.voice_sample import VoiceSample
from backend.repositories.idempotency_repository import IdempotencyRepository


def _system_ffmpeg() -> str | None:
    configured = os.getenv("DOHAMUSIC_VOICE_FFMPEG_EXECUTABLE", "ffmpeg")
    candidate = Path(configured)
    if candidate.is_absolute():
        return str(candidate) if candidate.is_file() else None
    return shutil.which(configured)


def _wav_bytes(
    *,
    duration: float = 6.0,
    value: int = 5000,
    rate: int = 16_000,
    channels: int = 2,
) -> bytes:
    output = io.BytesIO()
    samples = array("h", [value] * int(duration * rate) * channels)
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def _encoded_wav_bytes(
    *, format_tag: int, bit_depth: int, payload: bytes, extra: bytes = b""
) -> bytes:
    rate = 48_000
    channels = 1
    block_align = channels * ((bit_depth + 7) // 8)
    fmt = struct.pack(
        "<HHIIHH",
        format_tag,
        channels,
        rate,
        rate * block_align,
        block_align,
        bit_depth,
    ) + extra
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WAVE" + chunks


def _create(client: TestClient, key: str | None = None):
    headers = {"Idempotency-Key": key or str(uuid.uuid4())}
    return client.post(
        "/api/voice-enrollments",
        headers=headers,
        json={
            "name": "기본 목소리",
            "description": "테스트 프로필",
            "consent_confirmed": True,
            "consent_policy_version": "v1",
        },
    )


def _upload(
    client: TestClient,
    enrollment_id: str,
    *,
    key: str | None = None,
    wav: bytes | None = None,
):
    return client.post(
        f"/api/voice-enrollments/{enrollment_id}/samples",
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
        data={"source_type": "FILE_UPLOAD", "category": "BASIC_SPEECH"},
        files={
            "file": (
                "voice.wav",
                wav if wav is not None else _wav_bytes(),
                "audio/wav",
            )
        },
    )


def test_create_get_idempotency_and_safe_dto(client: TestClient) -> None:
    key = str(uuid.uuid4())
    created = _create(client, key)
    assert created.status_code == 201
    payload = created.json()
    assert payload["status"] == "DRAFT"
    assert payload["sample_count"] == 0
    assert payload["can_submit"] is False
    assert payload["expires_at"] < payload["absolute_expires_at"]

    replayed = _create(client, key)
    assert replayed.status_code == 201
    assert replayed.json()["id"] == payload["id"]
    conflict = client.post(
        "/api/voice-enrollments",
        headers={"Idempotency-Key": key},
        json={
            "name": "다른 이름",
            "consent_confirmed": True,
            "consent_policy_version": "v1",
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    missing_key = client.post(
        "/api/voice-enrollments",
        json={
            "name": "키 없음",
            "consent_confirmed": True,
            "consent_policy_version": "v1",
        },
    )
    assert missing_key.status_code == 422
    assert missing_key.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"
    fetched = client.get(f"/api/voice-enrollments/{payload['id']}")
    assert fetched.status_code == 200
    assert fetched.headers["cache-control"] == "private, no-store"
    serialized = json.dumps(fetched.json())
    assert "storage" not in serialized.lower()
    assert "ffmpeg" not in serialized.lower()


def test_idempotency_in_progress_and_hashed_key(
    app: FastAPI, client: TestClient
) -> None:
    assert client.get("/health").status_code == 200
    key = "raw-key-that-must-not-be-stored"
    now = datetime.now(UTC)
    with app.state.session_factory() as session:
        claim = IdempotencyRepository(session).claim(
            scope="voice-enrollment:test",
            key=key,
            fingerprint="a" * 64,
            now=now,
        )
        session.commit()
        assert claim.record.key_hash != key
    with (
        app.state.session_factory() as session,
        pytest.raises(ValueError, match="IDEMPOTENCY_IN_PROGRESS"),
    ):
        IdempotencyRepository(session).claim(
            scope="voice-enrollment:test",
            key=key,
            fingerprint="a" * 64,
            now=now,
        )


def test_upload_submit_profile_compatibility_and_duplicate_submit(
    client: TestClient, app: FastAPI
) -> None:
    created = _create(client).json()
    enrollment_id = created["id"]
    upload_key = str(uuid.uuid4())
    uploaded = _upload(client, enrollment_id, key=upload_key)
    assert uploaded.status_code == 201, uploaded.text
    sample = uploaded.json()
    assert sample["status"] == "READY"
    assert sample["sample_rate"] == 48_000
    assert sample["channels"] == 1
    assert sample["bit_depth"] == 16
    assert sample["quality"]["status"] == "PASS"
    assert sample["submit_eligible"] is True
    after_upload = client.get(f"/api/voice-enrollments/{enrollment_id}").json()
    assert after_upload["expires_at"] >= created["expires_at"]
    assert after_upload["expires_at"] <= after_upload["absolute_expires_at"]

    replayed = _upload(client, enrollment_id, key=upload_key)
    assert replayed.status_code == 201
    assert replayed.json()["id"] == sample["id"]
    sample_detail = client.get(
        f"/api/voice-enrollments/{enrollment_id}/samples/{sample['id']}"
    )
    assert sample_detail.status_code == 200

    submit_key = str(uuid.uuid4())
    submitted = client.post(
        f"/api/voice-enrollments/{enrollment_id}/submit",
        headers={"Idempotency-Key": submit_key},
        json={
            "active_reference_sample_id": sample["id"],
            "included_sample_ids": [sample["id"]],
            "acknowledged_warning_codes": [],
            "consent_confirmed": True,
            "consent_policy_version": "v1",
        },
    )
    assert submitted.status_code == 201, submitted.text
    result = submitted.json()
    assert result["status"] == "COMPLETED"
    assert result["cleanup_status"] == "COMPLETED"
    profile_id = result["voice_profile_id"]
    profile = client.get(f"/api/voice-profiles/{profile_id}")
    assert profile.status_code == 200
    with app.state.session_factory() as session:
        stored_profile = session.get(VoiceProfile, profile_id)
        assert stored_profile is not None
        assert stored_profile.active_reference_sample_id == sample["id"]
        assert stored_profile.reference_file_path.endswith("/reference.wav")
        reference_file_path = stored_profile.reference_file_path
    final_path = app.state.storage.resolve_voice_reference(reference_file_path)
    assert final_path.is_file()

    duplicate = client.post(
        f"/api/voice-enrollments/{enrollment_id}/submit",
        headers={"Idempotency-Key": submit_key},
        json={
            "active_reference_sample_id": sample["id"],
            "included_sample_ids": [sample["id"]],
            "acknowledged_warning_codes": [],
            "consent_confirmed": True,
            "consent_policy_version": "v1",
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["voice_profile_id"] == profile_id

    deleted = client.delete(f"/api/voice-profiles/{profile_id}")
    assert deleted.status_code == 204
    assert not final_path.exists()


def test_warning_requires_acknowledgement(client: TestClient) -> None:
    enrollment_id = _create(client).json()["id"]
    sample = _upload(client, enrollment_id, wav=_wav_bytes(value=0)).json()
    assert sample["quality"]["status"] == "WARNING"
    body = {
        "active_reference_sample_id": sample["id"],
        "included_sample_ids": [sample["id"]],
        "acknowledged_warning_codes": [],
        "consent_confirmed": True,
        "consent_policy_version": "v1",
    }
    blocked = client.post(
        f"/api/voice-enrollments/{enrollment_id}/submit",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert blocked.status_code == 422
    assert blocked.json()["error"]["code"] == "VOICE_WARNING_ACKNOWLEDGEMENT_REQUIRED"
    body["acknowledged_warning_codes"] = [
        {"sample_id": sample["id"], "codes": sample["quality"]["warnings"]}
    ]
    accepted = client.post(
        f"/api/voice-enrollments/{enrollment_id}/submit",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json=body,
    )
    assert accepted.status_code == 201


def test_delete_cancel_expiration_and_ffmpeg_unavailable(
    client: TestClient,
    app: FastAPI,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enrollment_id = _create(client).json()["id"]
    sample = _upload(client, enrollment_id).json()
    deleted = client.delete(
        f"/api/voice-enrollments/{enrollment_id}/samples/{sample['id']}"
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "CANCELLED"
    cancelled = client.post(f"/api/voice-enrollments/{enrollment_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["cleanup_status"] == "COMPLETED"

    expired_id = _create(client).json()["id"]
    with app.state.session_factory() as session:
        enrollment = session.get(VoiceEnrollment, expired_id)
        assert enrollment is not None
        enrollment.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    expired = client.get(f"/api/voice-enrollments/{expired_id}")
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "VOICE_ENROLLMENT_EXPIRED"

    absolute_id = _create(client).json()["id"]
    with app.state.session_factory() as session:
        enrollment = session.get(VoiceEnrollment, absolute_id)
        assert enrollment is not None
        enrollment.expires_at = datetime.now(UTC) + timedelta(hours=1)
        enrollment.absolute_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()
    absolute_expired = client.post(f"/api/voice-enrollments/{absolute_id}/cancel")
    assert absolute_expired.status_code == 410

    missing_ffmpeg = tmp_path / "missing FFmpeg" / "ffmpeg.exe"
    assert not missing_ffmpeg.exists()
    monkeypatch.setattr(
        app.state.voice_enrollment_service.normalizer,
        "ffmpeg_executable",
        str(missing_ffmpeg),
    )
    webm_id = _create(client).json()["id"]
    webm = client.post(
        f"/api/voice-enrollments/{webm_id}/samples",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        data={"source_type": "BROWSER_RECORDING", "category": "BASIC_SPEECH"},
        files={
            "file": (
                "voice.webm",
                b"\x1aE\xdf\xa3syntheticA_OPUSpayload",
                "audio/webm;codecs=opus",
            )
        },
    )
    assert webm.status_code == 503
    assert webm.json()["error"]["code"] == "VOICE_NORMALIZER_UNAVAILABLE"
    assert client.get("/health").status_code == 200


@pytest.mark.integration
@pytest.mark.skipif(
    _system_ffmpeg() is None,
    reason="system FFmpeg is required for the installed decoder API path",
)
def test_installed_ffmpeg_malformed_webm_returns_decode_failure(
    client: TestClient,
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = _system_ffmpeg()
    assert executable is not None
    monkeypatch.setattr(
        app.state.voice_enrollment_service.normalizer,
        "ffmpeg_executable",
        executable,
    )
    enrollment_id = _create(client).json()["id"]

    response = client.post(
        f"/api/voice-enrollments/{enrollment_id}/samples",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        data={"source_type": "BROWSER_RECORDING", "category": "BASIC_SPEECH"},
        files={
            "file": (
                "voice.webm",
                b"\x1aE\xdf\xa3truncatedA_OPUS",
                "audio/webm;codecs=opus",
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VOICE_SAMPLE_DECODE_FAILED"


def test_long_pcm16_wav_returns_duration_error_and_cleans_storage(
    client: TestClient, app: FastAPI
) -> None:
    enrollment_id = _create(client).json()["id"]

    response = _upload(
        client,
        enrollment_id,
        wav=_wav_bytes(duration=61, rate=48_000, channels=2),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VOICE_SAMPLE_DURATION_TOO_LONG"
    with app.state.session_factory() as session:
        samples = session.query(VoiceSample).filter_by(enrollment_id=enrollment_id).all()
        assert len(samples) == 1
        assert samples[0].failure_code == "VOICE_SAMPLE_DURATION_TOO_LONG"
        assert samples[0].original_storage_path is None
        assert samples[0].normalized_storage_path is None
    enrollment_directory = (
        app.state.settings.storage_root / "voices" / "enrollments" / enrollment_id
    )
    assert not enrollment_directory.exists() or not any(enrollment_directory.rglob("*"))


def test_unsupported_wav_retry_is_idempotent_and_cleans_storage(
    client: TestClient, app: FastAPI
) -> None:
    enrollment_id = _create(client).json()["id"]
    key = str(uuid.uuid4())
    pcm24 = _encoded_wav_bytes(
        format_tag=1,
        bit_depth=24,
        payload=b"\x00\x00\x00" * 48_000,
    )

    first = _upload(client, enrollment_id, key=key, wav=pcm24)
    same_key_retry = _upload(client, enrollment_id, key=key, wav=pcm24)
    new_key_retry = _upload(client, enrollment_id, wav=pcm24)

    for response in (first, same_key_retry, new_key_retry):
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VOICE_SAMPLE_UNSUPPORTED_CODEC"
    with app.state.session_factory() as session:
        samples = session.query(VoiceSample).filter_by(enrollment_id=enrollment_id).all()
        assert len(samples) == 3
        assert all(sample.status == "FAILED" for sample in samples)
        assert all(
            sample.failure_code == "VOICE_SAMPLE_UNSUPPORTED_CODEC"
            for sample in samples
        )
        assert all(sample.original_storage_path is None for sample in samples)
        assert all(sample.normalized_storage_path is None for sample in samples)
    enrollment_directory = (
        app.state.settings.storage_root / "voices" / "enrollments" / enrollment_id
    )
    assert not enrollment_directory.exists() or not any(enrollment_directory.rglob("*"))


@pytest.mark.parametrize(
    ("payload", "expected_code"),
    [
        (b"", "VOICE_SAMPLE_EMPTY_AUDIO"),
        (
            b"RIFF\x04\x00\x00\x00WAVE",
            "VOICE_SAMPLE_DECODE_FAILED",
        ),
    ],
    ids=["empty", "malformed"],
)
def test_empty_and_malformed_wav_fail_safely(
    client: TestClient, payload: bytes, expected_code: str
) -> None:
    enrollment_id = _create(client).json()["id"]

    response = _upload(client, enrollment_id, wav=payload)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == expected_code


def test_upload_limit_conflict_and_submit_rollback(
    client: TestClient, app: FastAPI, monkeypatch
) -> None:
    enrollment_id = _create(client).json()["id"]
    app.state.voice_enrollment_service.settings = app.state.settings.model_copy(
        update={"voice_enrollment_max_samples": 1}
    )
    key = str(uuid.uuid4())
    sample = _upload(client, enrollment_id, key=key).json()
    conflict = _upload(client, enrollment_id, key=key, wav=_wav_bytes(value=6000))
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    limited = _upload(client, enrollment_id)
    assert limited.status_code == 422
    assert limited.json()["error"]["code"] == "VOICE_SAMPLE_LIMIT_EXCEEDED"

    original_promote = app.state.voice_enrollment_service.storage.promote

    def fail_promotion(*_args) -> None:
        raise OSError("simulated")

    monkeypatch.setattr(
        app.state.voice_enrollment_service.storage, "promote", fail_promotion
    )
    failed = client.post(
        f"/api/voice-enrollments/{enrollment_id}/submit",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "active_reference_sample_id": sample["id"],
            "included_sample_ids": [sample["id"]],
            "acknowledged_warning_codes": [],
            "consent_confirmed": True,
            "consent_policy_version": "v1",
        },
    )
    assert failed.status_code == 500
    assert failed.json()["error"]["code"] == "VOICE_PROFILE_CREATION_FAILED"
    assert (
        client.get(f"/api/voice-enrollments/{enrollment_id}").json()["status"]
        == "READY_TO_SUBMIT"
    )
    monkeypatch.setattr(
        app.state.voice_enrollment_service.storage, "promote", original_promote
    )

    def fail_delete(_path) -> None:
        raise OSError("simulated")

    monkeypatch.setattr(
        app.state.voice_enrollment_service.storage, "delete_file", fail_delete
    )
    cleanup_failed = client.delete(
        f"/api/voice-enrollments/{enrollment_id}/samples/{sample['id']}"
    )
    assert cleanup_failed.status_code == 500
    assert cleanup_failed.json()["error"]["code"] == "VOICE_CLEANUP_FAILED"
    detail = client.get(
        f"/api/voice-enrollments/{enrollment_id}/samples/{sample['id']}"
    ).json()
    assert detail["status"] == "FAILED"
    assert detail["cleanup_status"] == "FAILED"


def test_openapi_contains_voice_enrollment_paths(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    expected = {
        "/api/voice-enrollments",
        "/api/voice-enrollments/{enrollment_id}",
        "/api/voice-enrollments/{enrollment_id}/samples",
        "/api/voice-enrollments/{enrollment_id}/samples/{sample_id}",
        "/api/voice-enrollments/{enrollment_id}/submit",
        "/api/voice-enrollments/{enrollment_id}/cancel",
    }
    assert expected <= set(paths)
    assert "/api/voice-profiles/upload" in paths
    upload = paths["/api/voice-enrollments/{enrollment_id}/samples"]["post"]
    unsupported = upload["responses"]["422"]["content"]["application/json"][
        "examples"
    ]["unsupported_wav_codec"]["value"]
    assert unsupported["error"]["code"] == "VOICE_SAMPLE_UNSUPPORTED_CODEC"
