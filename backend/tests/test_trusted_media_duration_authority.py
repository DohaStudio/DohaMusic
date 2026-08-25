"""Trusted media duration과 exactly-one Clip source authority 검증."""

from __future__ import annotations

import inspect
import io
import wave
from dataclasses import fields
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.models.workspace import Artifact
from backend.services.workspace.artifact_ingestion_service import (
    ArtifactIngestionRequest,
)
from backend.services.workspace.trusted_media_metadata_service import (
    TrustedMediaMetadataError,
    TrustedMediaMetadataErrorCode,
    TrustedMediaMetadataService,
)
from backend.storage.artifact_media import (
    ArtifactMediaValidationError,
    validate_artifact_media,
)


def _write(path: Path, payload: bytes) -> Path:
    path.write_bytes(payload)
    return path


def _wav_payload(*, sample_rate: int = 8_000, samples: int = 16) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as payload:
        payload.setnchannels(1)
        payload.setsampwidth(2)
        payload.setframerate(sample_rate)
        payload.writeframes(b"\x00\x00" * samples)
    return output.getvalue()


def _flac_payload(*, sample_rate: int = 8_000, samples: int = 16) -> bytes:
    streaminfo = bytearray(34)
    streaminfo[0:2] = (16).to_bytes(2, "big")
    streaminfo[2:4] = (16).to_bytes(2, "big")
    streaminfo[10:18] = ((sample_rate << 44) | samples).to_bytes(8, "big")
    return b"fLaC" + b"\x80\x00\x00\x22" + bytes(streaminfo) + b"\xff\xf8"


def _mp3_payload() -> bytes:
    return b"ID3\x04\x00\x00\x00\x00\x00\x00\xff\xfb\x90\x64Xing\x00\x00\x00\x00"


def _artifact(asset_version_id: UUID, *, duration_us: int | None, suffix: str = "wav") -> Artifact:
    media_type = {
        "wav": "audio/wav",
        "flac": "audio/flac",
        "mp3": "audio/mpeg",
    }[suffix]
    return Artifact(
        artifact_id=uuid4(),
        asset_version_id=asset_version_id,
        artifact_kind="audio",
        media_type=media_type,
        size_bytes=100,
        duration_us=duration_us,
        checksum_algorithm="sha256",
        artifact_checksum="a" * 64,
        producer_type="workspace",
        retention_status="active",
    )


class _Reader:
    def __init__(self, artifacts: list[Artifact]) -> None:
        self.artifacts = artifacts
        self.requests: list[UUID] = []

    def list_clip_source_artifact_candidates(self, asset_version_id: UUID) -> list[Artifact]:
        self.requests.append(asset_version_id)
        return self.artifacts


def test_wav_duration_is_positive_exact_and_deterministic(tmp_path: Path) -> None:
    path = _write(tmp_path / "source.wav", _wav_payload())
    first = validate_artifact_media(path, artifact_kind="audio", size_bytes=path.stat().st_size)
    second = validate_artifact_media(path, artifact_kind="audio", size_bytes=path.stat().st_size)
    assert first == second
    assert first.media_type == "audio/wav"
    assert first.duration_us == 2_000


@pytest.mark.parametrize("mutation", ["zero_rate", "truncated"])
def test_wav_invalid_metadata_and_truncation_fail_closed(tmp_path: Path, mutation: str) -> None:
    payload = bytearray(_wav_payload())
    if mutation == "zero_rate":
        payload[24:28] = b"\x00\x00\x00\x00"
    else:
        del payload[-1]
    path = _write(tmp_path / f"{mutation}.wav", bytes(payload))
    with pytest.raises(ArtifactMediaValidationError):
        validate_artifact_media(path, artifact_kind="audio", size_bytes=len(payload))


def test_flac_streaminfo_duration_and_malformed_metadata(tmp_path: Path) -> None:
    valid = _write(tmp_path / "valid.flac", _flac_payload())
    media = validate_artifact_media(valid, artifact_kind="audio", size_bytes=valid.stat().st_size)
    assert media.media_type == "audio/flac"
    assert media.duration_us == 2_000

    malformed = _write(tmp_path / "malformed.flac", _flac_payload()[:-20])
    with pytest.raises(ArtifactMediaValidationError):
        validate_artifact_media(
            malformed,
            artifact_kind="audio",
            size_bytes=malformed.stat().st_size,
        )

    streaminfo_not_first = _write(
        tmp_path / "streaminfo-not-first.flac",
        b"fLaC" + b"\x84\x00\x00\x00" + _flac_payload()[4:],
    )
    with pytest.raises(ArtifactMediaValidationError):
        validate_artifact_media(
            streaminfo_not_first,
            artifact_kind="audio",
            size_bytes=streaminfo_not_first.stat().st_size,
        )


def test_mp3_is_format_valid_but_duration_unavailable_without_estimation(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path / "vbr.mp3", _mp3_payload())
    media = validate_artifact_media(path, artifact_kind="audio", size_bytes=path.stat().st_size)
    assert media.media_type == "audio/mpeg"
    assert media.duration_us is None

    truncated = _write(tmp_path / "truncated.mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00")
    with pytest.raises(ArtifactMediaValidationError):
        validate_artifact_media(
            truncated,
            artifact_kind="audio",
            size_bytes=truncated.stat().st_size,
        )


def test_unsupported_audio_fails_closed(tmp_path: Path) -> None:
    path = _write(tmp_path / "unknown.bin", b"not-audio")
    with pytest.raises(ArtifactMediaValidationError):
        validate_artifact_media(path, artifact_kind="audio", size_bytes=9)


def test_exactly_one_trusted_duration_is_resolved_without_paths() -> None:
    version_id = uuid4()
    artifact = _artifact(version_id, duration_us=2_000)
    reader = _Reader([artifact])
    metadata = TrustedMediaMetadataService(reader).resolve_clip_source(version_id)
    assert metadata.asset_version_id == version_id
    assert metadata.artifact_id == artifact.artifact_id
    assert metadata.duration_us == 2_000
    assert reader.requests == [version_id]
    assert "path" not in {field.name for field in fields(metadata)}


@pytest.mark.parametrize(
    ("artifacts", "code"),
    [
        ([], TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_NOT_FOUND),
        (
            [
                _artifact(uuid4(), duration_us=2_000),
                _artifact(uuid4(), duration_us=2_000),
            ],
            TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_AMBIGUOUS,
        ),
        (
            [_artifact(uuid4(), duration_us=None, suffix="mp3")],
            TrustedMediaMetadataErrorCode.SOURCE_DURATION_UNAVAILABLE,
        ),
    ],
)
def test_missing_ambiguous_and_unvalidated_sources_fail_closed(
    artifacts: list[Artifact], code: TrustedMediaMetadataErrorCode
) -> None:
    with pytest.raises(TrustedMediaMetadataError) as caught:
        TrustedMediaMetadataService(_Reader(artifacts)).resolve_clip_source(uuid4())
    assert caught.value.code is code
    message = str(caught.value).lower()
    assert not any(token in message for token in ("\\", ":/", "storage", "locator"))


def test_caller_and_provider_cannot_supply_duration_authority() -> None:
    request_fields = {field.name for field in fields(ArtifactIngestionRequest)}
    assert "duration_us" not in request_fields
    assert "source_duration" not in request_fields
    source = inspect.getsource(TrustedMediaMetadataService)
    assert "provider" not in source.lower()
    assert "filesystem" not in source.lower()
