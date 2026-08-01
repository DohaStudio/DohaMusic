"""Declared MIME, extension, and container-signature validation."""

from __future__ import annotations

from pathlib import Path

from backend.voice_enrollment.contracts import VoiceAudioProcessingError, VoiceContainer

MIME_CONTAINERS = {
    "audio/wav": VoiceContainer.WAV,
    "audio/x-wav": VoiceContainer.WAV,
    "audio/webm": VoiceContainer.WEBM,
    "audio/ogg": VoiceContainer.OGG,
}
EXTENSION_CONTAINERS = {
    ".wav": VoiceContainer.WAV,
    ".webm": VoiceContainer.WEBM,
    ".ogg": VoiceContainer.OGG,
}


def validate_media(
    filename: str, content_type: str | None, header: bytes
) -> VoiceContainer:
    if not filename or any(character in filename for character in ("/", "\\", "\x00")):
        raise VoiceAudioProcessingError("VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE")
    extension_container = EXTENSION_CONTAINERS.get(Path(filename).suffix.lower())
    normalized_mime = (content_type or "").split(";", 1)[0].strip().lower()
    mime_container = MIME_CONTAINERS.get(normalized_mime)
    signature_container = detect_container(header)
    if (
        extension_container is None
        or mime_container is None
        or signature_container is None
        or len({extension_container, mime_container, signature_container}) != 1
    ):
        raise VoiceAudioProcessingError("VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE")
    if signature_container == VoiceContainer.OGG and b"OpusHead" not in header:
        raise VoiceAudioProcessingError("VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE")
    if signature_container == VoiceContainer.WEBM and b"A_OPUS" not in header:
        raise VoiceAudioProcessingError("VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE")
    return signature_container


def detect_container(header: bytes) -> VoiceContainer | None:
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return VoiceContainer.WAV
    if header.startswith(b"\x1aE\xdf\xa3"):
        return VoiceContainer.WEBM
    if header.startswith(b"OggS"):
        return VoiceContainer.OGG
    return None
