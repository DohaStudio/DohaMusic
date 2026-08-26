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
    duration_us: int | None = None


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
                channels = payload.getnchannels()
                sample_width = payload.getsampwidth()
                sample_rate = payload.getframerate()
                total_samples = payload.getnframes()
                if channels < 1 or sample_width < 1 or sample_rate < 1 or total_samples < 1:
                    raise ArtifactMediaValidationError("유효하지 않은 WAV입니다.")
                frame_width = channels * sample_width
                remaining_samples = total_samples
                actual_samples = 0
                while remaining_samples:
                    requested_samples = min(remaining_samples, 65_536)
                    frames = payload.readframes(requested_samples)
                    if not frames or len(frames) % frame_width:
                        break
                    read_samples = len(frames) // frame_width
                    actual_samples += read_samples
                    remaining_samples -= read_samples
                    if read_samples < requested_samples:
                        break
                if actual_samples != total_samples:
                    raise ArtifactMediaValidationError("잘린 WAV입니다.")
        except (EOFError, OSError, wave.Error):
            raise ArtifactMediaValidationError("유효하지 않은 WAV입니다.") from None
        return ValidatedArtifactMedia(
            "audio/wav",
            "wav",
            _duration_us(total_samples=total_samples, sample_rate=sample_rate),
        )

    if header.startswith(b"fLaC"):
        return ValidatedArtifactMedia("audio/flac", "flac", _flac_duration_us(path))
    if header.startswith(b"ID3") or (
        len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0 == 0xE0
    ):
        _validate_mp3_header(path, header)
        # 현재 dependency에는 frame/VBR metadata를 완전 검증하는 MP3 parser가 없다.
        # size/bitrate 추정은 금지하며 Artifact는 유지하되 Clip source로는 fail closed한다.
        return ValidatedArtifactMedia("audio/mpeg", "mp3")
    raise ArtifactMediaValidationError("지원하지 않거나 손상된 Audio입니다.")


def _validate_mp3_header(path: Path, header: bytes) -> None:
    """추정 duration 없이 ID3 경계와 첫 MPEG audio frame header만 검증한다."""

    try:
        with path.open("rb") as stream:
            if header.startswith(b"ID3"):
                id3_header = stream.read(10)
                if len(id3_header) != 10 or any(byte & 0x80 for byte in id3_header[6:10]):
                    raise ArtifactMediaValidationError("유효하지 않은 MP3 ID3입니다.")
                tag_size = (
                    (id3_header[6] << 21)
                    | (id3_header[7] << 14)
                    | (id3_header[8] << 7)
                    | id3_header[9]
                )
                stream.seek(10 + tag_size)
            frame_header = stream.read(4)
    except OSError:
        raise ArtifactMediaValidationError("유효하지 않은 MP3입니다.") from None
    if len(frame_header) != 4 or not _is_mp3_frame_header(frame_header):
        raise ArtifactMediaValidationError("잘리거나 손상된 MP3입니다.")


def _is_mp3_frame_header(header: bytes) -> bool:
    value = int.from_bytes(header, "big")
    sync = (value >> 21) & 0x7FF
    version = (value >> 19) & 0x3
    layer = (value >> 17) & 0x3
    bitrate_index = (value >> 12) & 0xF
    sample_rate_index = (value >> 10) & 0x3
    return (
        sync == 0x7FF
        and version != 0x1
        and layer != 0
        and bitrate_index not in {0, 0xF}
        and sample_rate_index != 0x3
    )


def _duration_us(*, total_samples: int, sample_rate: int) -> int:
    """sample authority를 가장 가까운 microsecond로 deterministic half-up 변환한다."""

    if total_samples < 1 or sample_rate < 1:
        raise ArtifactMediaValidationError("Audio duration metadata가 유효하지 않습니다.")
    duration_us = (total_samples * 1_000_000 + sample_rate // 2) // sample_rate
    if duration_us < 1:
        raise ArtifactMediaValidationError("Audio duration이 유효하지 않습니다.")
    return duration_us


def _flac_duration_us(path: Path) -> int:
    """FLAC STREAMINFO의 sample rate와 total samples만 duration authority로 사용한다."""

    try:
        with path.open("rb") as stream:
            if stream.read(4) != b"fLaC":
                raise ArtifactMediaValidationError("유효하지 않은 FLAC입니다.")
            streaminfo: bytes | None = None
            saw_last_block = False
            first_block = True
            while not saw_last_block:
                block_header = stream.read(4)
                if len(block_header) != 4:
                    raise ArtifactMediaValidationError("잘린 FLAC metadata입니다.")
                saw_last_block = bool(block_header[0] & 0x80)
                block_type = block_header[0] & 0x7F
                block_length = int.from_bytes(block_header[1:4], "big")
                block = stream.read(block_length)
                if len(block) != block_length:
                    raise ArtifactMediaValidationError("잘린 FLAC metadata입니다.")
                if first_block and block_type != 0:
                    raise ArtifactMediaValidationError(
                        "FLAC STREAMINFO가 첫 metadata block이 아닙니다."
                    )
                if block_type == 0:
                    if streaminfo is not None or block_length != 34:
                        raise ArtifactMediaValidationError("FLAC STREAMINFO가 유효하지 않습니다.")
                    streaminfo = block
                first_block = False
            if streaminfo is None or not stream.read(1):
                raise ArtifactMediaValidationError("FLAC audio frame이 없습니다.")
    except OSError:
        raise ArtifactMediaValidationError("유효하지 않은 FLAC입니다.") from None

    packed = int.from_bytes(streaminfo[10:18], "big")
    sample_rate = (packed >> 44) & 0xFFFFF
    total_samples = packed & ((1 << 36) - 1)
    return _duration_us(total_samples=total_samples, sample_rate=sample_rate)


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
        raise ArtifactMediaValidationError("구조화 Artifact의 검증 크기 상한을 초과했습니다.")
    try:
        with path.open("r", encoding="utf-8") as stream:
            json.load(stream)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ArtifactMediaValidationError("유효한 UTF-8 JSON이 아닙니다.") from None
