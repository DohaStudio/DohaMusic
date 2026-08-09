"""Trusted ingestion에서 사용하는 fail-closed Artifact media 검증."""

from __future__ import annotations

import codecs
import json
import wave
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_ARTIFACT_KINDS = frozenset(
    {"lyrics_text", "audio", "stem", "manifest", "evaluation", "snapshot"}
)
STRUCTURED_ARTIFACT_KINDS = frozenset({"manifest", "evaluation", "snapshot"})
AUDIO_ARTIFACT_KINDS = frozenset({"audio", "stem"})
MAX_STRUCTURED_PAYLOAD_BYTES = 16 * 1024 * 1024


class ArtifactMediaValidationError(ValueError):
    """Payload가 kind별 authoritative media 계약을 충족하지 못했다."""


@dataclass(frozen=True, slots=True)
class ValidatedArtifactMedia:
    media_type: str
    extension: str


def validate_artifact_media(
    path: Path,
    *,
    artifact_kind: str,
    size_bytes: int,
) -> ValidatedArtifactMedia:
    """파일명 대신 실제 bytes와 parser로 kind별 media type을 확정한다."""

    if artifact_kind not in SUPPORTED_ARTIFACT_KINDS:
        raise ArtifactMediaValidationError("지원하지 않는 Artifact kind입니다.")
    if artifact_kind in AUDIO_ARTIFACT_KINDS:
        return _validate_audio(path)
    if artifact_kind == "lyrics_text":
        _validate_utf8_text(path)
        return ValidatedArtifactMedia("text/plain", "txt")
    if artifact_kind in STRUCTURED_ARTIFACT_KINDS:
        _validate_json(path, size_bytes=size_bytes)
        return ValidatedArtifactMedia("application/json", "json")
    raise ArtifactMediaValidationError("검증 가능한 media 계약이 없습니다.")


def _validate_audio(path: Path) -> ValidatedArtifactMedia:
    with path.open("rb") as stream:
        header = stream.read(16)

    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        try:
            with wave.open(str(path), "rb") as payload:
                if payload.getnchannels() < 1 or payload.getframerate() < 1:
                    raise ArtifactMediaValidationError("유효하지 않은 WAV입니다.")
                payload.readframes(1)
        except (EOFError, wave.Error):
            raise ArtifactMediaValidationError("유효하지 않은 WAV입니다.") from None
        return ValidatedArtifactMedia("audio/wav", "wav")

    if header.startswith(b"fLaC"):
        return ValidatedArtifactMedia("audio/flac", "flac")
    if header.startswith(b"ID3") or (
        len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
    ):
        return ValidatedArtifactMedia("audio/mpeg", "mp3")
    raise ArtifactMediaValidationError("지원하지 않거나 손상된 Audio입니다.")


def _validate_utf8_text(path: Path) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        raise ArtifactMediaValidationError("UTF-8 text가 아닙니다.") from None


def _validate_json(path: Path, *, size_bytes: int) -> None:
    if size_bytes > MAX_STRUCTURED_PAYLOAD_BYTES:
        raise ArtifactMediaValidationError(
            "구조화 Artifact의 검증 크기 상한을 초과했습니다."
        )
    try:
        with path.open("r", encoding="utf-8") as stream:
            json.load(stream)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ArtifactMediaValidationError("유효한 UTF-8 JSON이 아닙니다.") from None
