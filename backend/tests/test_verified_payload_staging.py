from __future__ import annotations

import hashlib
import io
import json
import wave
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from backend.storage import ArtifactStorageRoots
from backend.storage.verified_payload_staging import (
    ExpectedPayloadFacts,
    LocalFilesystemStagingAdapter,
    VerifiedPayloadStagingError,
    VerifiedPayloadStagingErrorCode,
    VerifiedStagedPayload,
)


def _wav_bytes() -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(8_000)
        payload.writeframes(b"\x00\x00" * 80)
    return output.getvalue()


def _facts(content: bytes, media_type: str = "audio/wav") -> ExpectedPayloadFacts:
    return ExpectedPayloadFacts(
        checksum_algorithm="sha256",
        payload_checksum=hashlib.sha256(content).hexdigest(),
        size_bytes=len(content),
        media_type=media_type,
    )


def _flac_bytes() -> bytes:
    streaminfo = bytearray(34)
    streaminfo[10:18] = ((44_100 << 44) | 100).to_bytes(8, "big")
    return b"fLaC" + b"\x80\x00\x00\x22" + bytes(streaminfo) + b"\xff"


def _adapter(tmp_path: Path) -> LocalFilesystemStagingAdapter:
    root = tmp_path / "staging"
    root.mkdir()
    return LocalFilesystemStagingAdapter(root)


def test_streams_verifies_publishes_and_opens_wav(tmp_path: Path) -> None:
    content = _wav_bytes()
    locator_uuid = uuid4()
    adapter = _adapter(tmp_path)

    staged = adapter.stage_verified(locator_uuid, [content[:17], content[17:]], _facts(content))

    assert staged.staging_key == (f"payload-staging/v1/{locator_uuid.hex[:2]}/{locator_uuid}.wav")
    with adapter.open_verified(staged) as payload:
        assert payload.read() == content
    assert not any((tmp_path / "staging" / ".partial").rglob("*.partial"))


def test_validates_strict_json_and_rejects_media_mismatch(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    content = json.dumps({"ok": True}, separators=(",", ":")).encode()
    staged = adapter.stage_verified(uuid4(), [content], _facts(content, "application/json"))
    assert staged.media_type == "application/json"

    invalid = b'{"unterminated":'
    with pytest.raises(VerifiedPayloadStagingError) as raised:
        adapter.stage_verified(uuid4(), [invalid], _facts(invalid, "application/json"))
    assert raised.value.code is VerifiedPayloadStagingErrorCode.MEDIA_MISMATCH


def test_validates_flac_structure(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    content = _flac_bytes()
    staged = adapter.stage_verified(uuid4(), [content], _facts(content, "audio/flac"))
    assert staged.media_type == "audio/flac"
    assert staged.staging_key.endswith(".flac")


def test_rejects_size_and_checksum_mismatch_and_cleans_partial(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    content = _wav_bytes()
    expected = _facts(content)

    with pytest.raises(VerifiedPayloadStagingError) as oversized:
        adapter.stage_verified(uuid4(), [content, b"extra"], expected)
    assert oversized.value.code is VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH

    wrong = ExpectedPayloadFacts("sha256", "0" * 64, len(content), "audio/wav")
    with pytest.raises(VerifiedPayloadStagingError) as checksum:
        adapter.stage_verified(uuid4(), [content], wrong)
    assert checksum.value.code is VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH
    assert not any((tmp_path / "staging" / ".partial").rglob("*.partial"))


def test_restart_adopts_existing_verified_object(tmp_path: Path) -> None:
    content = _wav_bytes()
    locator_uuid = uuid4()
    root = tmp_path / "staging"
    root.mkdir()
    first = LocalFilesystemStagingAdapter(root).stage_verified(
        locator_uuid, [content], _facts(content)
    )

    restarted = LocalFilesystemStagingAdapter(root)
    adopted = restarted.recover_published(locator_uuid, _facts(content))

    assert adopted is not None
    assert adopted.staging_key == first.staging_key
    assert adopted.payload_checksum == first.payload_checksum


def test_existing_final_with_conflicting_expected_bytes_is_rejected(tmp_path: Path) -> None:
    first_content = _wav_bytes()
    second_content = first_content + b"trailing"
    locator_uuid = uuid4()
    adapter = _adapter(tmp_path)
    adapter.stage_verified(locator_uuid, [first_content], _facts(first_content))

    with pytest.raises(VerifiedPayloadStagingError) as conflict:
        adapter.stage_verified(locator_uuid, [second_content], _facts(second_content))

    assert conflict.value.code is VerifiedPayloadStagingErrorCode.PUBLISH_CONFLICT


def test_crash_partial_is_not_authority_and_has_identity_safe_cleanup(tmp_path: Path) -> None:
    content = _wav_bytes()
    locator_uuid = uuid4()
    adapter = _adapter(tmp_path)
    partial_key = f".partial/v1/{locator_uuid.hex[:2]}/{locator_uuid}.{uuid4().hex}.partial"
    partial_path = tmp_path / "staging" / Path(partial_key)
    partial_path.parent.mkdir(parents=True)
    partial_path.write_bytes(b"interrupted")

    assert adapter.recover_published(locator_uuid, _facts(content)) is None
    assert adapter.cleanup_partial(partial_key) is True
    assert adapter.cleanup_partial(partial_key) is False

    staged = adapter.stage_verified(locator_uuid, [content], _facts(content))
    assert staged.payload_checksum == hashlib.sha256(content).hexdigest()


def test_concurrent_same_locator_converges_on_one_final_object(tmp_path: Path) -> None:
    content = _wav_bytes()
    locator_uuid = uuid4()
    adapter = _adapter(tmp_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(
                lambda _: adapter.stage_verified(locator_uuid, [content], _facts(content)),
                range(2),
            )
        )

    assert results[0].staging_key == results[1].staging_key
    assert len(tuple((tmp_path / "staging" / "payload-staging").rglob("*.wav"))) == 1
    assert not any((tmp_path / "staging" / ".partial").rglob("*.partial"))


def test_existing_conflict_tamper_missing_and_idempotent_delete(tmp_path: Path) -> None:
    content = _wav_bytes()
    locator_uuid = uuid4()
    adapter = _adapter(tmp_path)
    staged = adapter.stage_verified(locator_uuid, [content], _facts(content))
    path = tmp_path / "staging" / Path(staged.staging_key)
    path.write_bytes(content[:-2] + b"XX")

    with pytest.raises(VerifiedPayloadStagingError) as tampered, adapter.open_verified(staged):
        pass
    assert tampered.value.code is VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
    with pytest.raises(VerifiedPayloadStagingError):
        adapter.delete_verified(staged)

    path.unlink()
    with pytest.raises(VerifiedPayloadStagingError) as missing, adapter.open_verified(staged):
        pass
    assert missing.value.code is VerifiedPayloadStagingErrorCode.CONTENT_MISSING
    assert adapter.delete_verified(staged) is False


def test_delete_is_verified_and_idempotent(tmp_path: Path) -> None:
    content = _wav_bytes()
    adapter = _adapter(tmp_path)
    staged = adapter.stage_verified(uuid4(), [content], _facts(content))

    assert adapter.delete_verified(staged) is True
    assert adapter.delete_verified(staged) is False


def test_configuration_rejects_missing_or_overlapping_root(tmp_path: Path) -> None:
    with pytest.raises(VerifiedPayloadStagingError) as missing:
        LocalFilesystemStagingAdapter(tmp_path / "missing")
    assert missing.value.code is VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR

    artifact_base = tmp_path / "artifact"
    for domain in ("lm", "audio", "vocal", "music"):
        (artifact_base / domain).mkdir(parents=True)
    roots = ArtifactStorageRoots.from_base_root(artifact_base)
    with pytest.raises(VerifiedPayloadStagingError) as overlap:
        LocalFilesystemStagingAdapter(artifact_base / "audio", artifact_roots=roots)
    assert overlap.value.code is VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR


@pytest.mark.parametrize(
    "key",
    (
        "payload-staging/v1/aa/%2e%2e.wav",
        "payload-staging/v1/CON/file.wav",
    ),
)
def test_local_open_rejects_stricter_unsafe_keys(tmp_path: Path, key: str) -> None:
    adapter = _adapter(tmp_path)
    content = _wav_bytes()
    staged = VerifiedStagedPayload(
        "local",
        key,
        "sha256",
        hashlib.sha256(content).hexdigest(),
        len(content),
        "audio/wav",
        datetime.now(UTC),
    )
    with pytest.raises(VerifiedPayloadStagingError) as unsafe, adapter.open_verified(staged):
        pass
    assert unsafe.value.code is VerifiedPayloadStagingErrorCode.INVALID_KEY


@pytest.mark.skipif(not hasattr(Path, "symlink_to"), reason="symlink is unavailable")
def test_rejects_symlink_escape_when_platform_allows_it(tmp_path: Path) -> None:
    root = tmp_path / "staging"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    adapter = LocalFilesystemStagingAdapter(root)
    try:
        (root / "payload-staging").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not permitted")

    content = _wav_bytes()
    with pytest.raises(VerifiedPayloadStagingError):
        adapter.stage_verified(uuid4(), [content], _facts(content))
