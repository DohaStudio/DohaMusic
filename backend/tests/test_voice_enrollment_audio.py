from __future__ import annotations

import io
import math
import os
import shutil
import struct
import subprocess
import uuid
import wave
from array import array
from pathlib import Path

import pytest

from backend.storage.service import StorageService
from backend.voice_enrollment.contracts import VoiceAudioProcessingError, VoiceContainer
from backend.voice_enrollment.media import validate_media
from backend.voice_enrollment.normalizer import HybridVoiceAudioNormalizer
from backend.voice_enrollment.storage import VoiceEnrollmentStorage
from backend.voice_enrollment.validator import VoiceAudioValidator


def _wav_bytes(
    *, duration: float = 1.0, rate: int = 16_000, channels: int = 2, value: int = 5000
) -> bytes:
    output = io.BytesIO()
    samples = array("h", [value] * int(duration * rate) * channels)
    with wave.open(output, "wb") as target:
        target.setnchannels(channels)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def _sine_wav_bytes(*, duration: float = 1.0, rate: int = 48_000) -> bytes:
    output = io.BytesIO()
    samples = array(
        "h",
        (
            int(6_000 * math.sin(2 * math.pi * 220 * index / rate))
            for index in range(int(duration * rate))
        ),
    )
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(samples.tobytes())
    return output.getvalue()


def _encoded_wav_bytes(
    *,
    format_tag: int,
    bit_depth: int,
    payload: bytes,
    rate: int = 48_000,
    channels: int = 1,
    extra: bytes = b"",
) -> bytes:
    block_align = channels * ((bit_depth + 7) // 8)
    byte_rate = rate * block_align
    fmt = (
        struct.pack(
            "<HHIIHH", format_tag, channels, rate, byte_rate, block_align, bit_depth
        )
        + extra
    )
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    chunks += b"data" + struct.pack("<I", len(payload)) + payload
    return b"RIFF" + struct.pack("<I", len(chunks) + 4) + b"WAVE" + chunks


def _extensible_pcm16_wav_bytes() -> bytes:
    pcm_subformat = bytes.fromhex("0100000000001000800000aa00389b71")
    extra = struct.pack("<H", 22) + struct.pack("<HI", 16, 0) + pcm_subformat
    return _encoded_wav_bytes(
        format_tag=0xFFFE,
        bit_depth=16,
        payload=b"\x00\x00" * 48_000,
        extra=extra,
    )


def _system_ffmpeg() -> str | None:
    configured = os.getenv("DOHAMUSIC_VOICE_FFMPEG_EXECUTABLE", "ffmpeg")
    candidate = Path(configured)
    if candidate.is_absolute():
        return str(candidate) if candidate.is_file() else None
    return shutil.which(configured)


@pytest.mark.parametrize(
    ("rate", "channels"),
    [(48_000, 1), (48_000, 2), (16_000, 1)],
    ids=["pcm16-mono", "pcm16-stereo", "pcm16-16khz-resample"],
)
def test_wav_normalizer_outputs_pcm16_48khz_mono(
    tmp_path: Path, rate: int, channels: int
) -> None:
    source = tmp_path / "source with spaces.wav"
    output = tmp_path / "output.wav"
    source.write_bytes(_wav_bytes(rate=rate, channels=channels))
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable="missing", timeout_seconds=1, max_output_bytes=200_000
    )

    result = normalizer.normalize(source, output, VoiceContainer.WAV)

    assert result.path == output
    with wave.open(str(output), "rb") as normalized:
        assert normalized.getnchannels() == 1
        assert normalized.getsampwidth() == 2
        assert normalized.getframerate() == 48_000
        assert normalized.getnframes() == pytest.approx(48_000, abs=2)


@pytest.mark.parametrize(
    "payload",
    [
        _encoded_wav_bytes(
            format_tag=1,
            bit_depth=24,
            payload=b"\x00\x00\x00" * 48_000,
        ),
        _encoded_wav_bytes(
            format_tag=3,
            bit_depth=32,
            payload=b"\x00\x00\x00\x00" * 48_000,
        ),
        _encoded_wav_bytes(
            format_tag=2,
            bit_depth=4,
            payload=b"\x00" * 24_000,
        ),
        _extensible_pcm16_wav_bytes(),
    ],
    ids=["pcm24", "float32", "adpcm", "wave-format-extensible"],
)
def test_wav_normalizer_rejects_unsupported_codec(
    tmp_path: Path, payload: bytes
) -> None:
    source = tmp_path / "unsupported.wav"
    output = tmp_path / "output.wav"
    source.write_bytes(payload)
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable="missing", timeout_seconds=1, max_output_bytes=200_000
    )

    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_UNSUPPORTED_CODEC"
    ):
        normalizer.normalize(source, output, VoiceContainer.WAV)

    assert not output.exists()
    assert not output.with_suffix(".normalizing").exists()


@pytest.mark.parametrize("payload", [b"", b"RIFF\x04\x00\x00\x00WAVE"])
def test_wav_normalizer_rejects_empty_or_malformed_and_cleans_output(
    tmp_path: Path, payload: bytes
) -> None:
    source = tmp_path / "invalid.wav"
    output = tmp_path / "output.wav"
    source.write_bytes(payload)
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable="missing", timeout_seconds=1, max_output_bytes=200_000
    )

    with pytest.raises(VoiceAudioProcessingError, match="VOICE_SAMPLE_DECODE_FAILED"):
        normalizer.normalize(source, output, VoiceContainer.WAV)

    assert not output.exists()
    assert not output.with_suffix(".normalizing").exists()


def test_wav_normalizer_classifies_output_limit_as_duration_failure(
    tmp_path: Path,
) -> None:
    source = tmp_path / "long.wav"
    output = tmp_path / "output.wav"
    source.write_bytes(_wav_bytes(duration=1.1, rate=48_000, channels=1))
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable="missing", timeout_seconds=1, max_output_bytes=96_044
    )

    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_DURATION_TOO_LONG"
    ):
        normalizer.normalize(source, output, VoiceContainer.WAV)

    assert not output.exists()
    assert not output.with_suffix(".normalizing").exists()


def test_wav_normalizer_cleans_partial_output_after_os_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.wav"
    output = tmp_path / "output.wav"
    source.write_bytes(_wav_bytes())
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable="missing", timeout_seconds=1, max_output_bytes=200_000
    )

    def fail_after_partial(_source: Path, partial: Path) -> None:
        partial.write_bytes(b"partial")
        raise OSError("simulated atomic write failure")

    monkeypatch.setattr(normalizer, "_normalize_wav", fail_after_partial)
    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_NORMALIZATION_FAILED"
    ):
        normalizer.normalize(source, output, VoiceContainer.WAV)

    assert not output.exists()
    assert not output.with_suffix(".normalizing").exists()


@pytest.mark.integration
@pytest.mark.skipif(
    _system_ffmpeg() is None,
    reason="system FFmpeg is not installed; fake and unavailable paths remain tested",
)
@pytest.mark.parametrize(
    ("extension", "container"),
    [("webm", VoiceContainer.WEBM), ("ogg", VoiceContainer.OGG)],
)
def test_system_ffmpeg_opus_normalization(
    tmp_path: Path, extension: str, container: VoiceContainer
) -> None:
    executable = _system_ffmpeg()
    assert executable is not None
    working = tmp_path / "합성 오디오 with spaces"
    working.mkdir()
    wav_source = working / "synthetic source.wav"
    encoded = working / f"synthetic input.{extension}"
    output = working / f"normalized output-{extension}.wav"
    wav_source.write_bytes(_sine_wav_bytes())
    subprocess.run(
        [
            executable,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-y",
            "-i",
            str(wav_source),
            "-c:a",
            "libopus",
            str(encoded),
        ],
        check=True,
        timeout=10,
        shell=False,
    )
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable=executable,
        timeout_seconds=10,
        max_output_bytes=200_000,
    )

    normalizer.normalize(encoded, output, container)

    validated = VoiceAudioValidator(
        min_duration_seconds=0.5, max_duration_seconds=2
    ).validate(output)
    assert validated.sample_rate == 48_000
    assert validated.channels == 1
    assert validated.bit_depth == 16
    assert validated.duration_seconds == pytest.approx(1, abs=0.05)
    assert validated.metrics.peak > 0
    assert output.stat().st_size > 44


@pytest.mark.integration
@pytest.mark.skipif(
    _system_ffmpeg() is None,
    reason="system FFmpeg is not installed; fake and unavailable paths remain tested",
)
@pytest.mark.parametrize(
    ("extension", "container", "payload"),
    [
        ("webm", VoiceContainer.WEBM, b"\x1aE\xdf\xa3truncatedA_OPUS"),
        ("ogg", VoiceContainer.OGG, b"OggStruncatedOpusHead"),
    ],
)
def test_system_ffmpeg_rejects_truncated_opus_and_cleans_partial_output(
    tmp_path: Path,
    extension: str,
    container: VoiceContainer,
    payload: bytes,
) -> None:
    executable = _system_ffmpeg()
    assert executable is not None
    source = tmp_path / f"truncated input.{extension}"
    output = tmp_path / "normalized output.wav"
    source.write_bytes(payload)
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable=executable,
        timeout_seconds=10,
        max_output_bytes=200_000,
    )

    with pytest.raises(VoiceAudioProcessingError, match="VOICE_SAMPLE_DECODE_FAILED"):
        normalizer.normalize(source, output, container)

    assert not output.exists()
    assert not output.with_suffix(".normalizing").exists()


@pytest.mark.parametrize(
    ("filename", "mime", "header", "container"),
    [
        ("sample.wav", "audio/wav", _wav_bytes(), VoiceContainer.WAV),
        (
            "sample.webm",
            "audio/webm;codecs=opus",
            b"\x1aE\xdf\xa3xxA_OPUS",
            VoiceContainer.WEBM,
        ),
        (
            "sample.ogg",
            "audio/ogg;codecs=opus",
            b"OggSxxxxOpusHead",
            VoiceContainer.OGG,
        ),
    ],
    ids=["wav", "webm", "ogg"],
)
def test_media_validation_matches_extension_mime_and_signature(
    filename: str, mime: str, header: bytes, container: VoiceContainer
) -> None:
    assert validate_media(filename, mime, header) == container


def test_media_validation_rejects_mismatch_and_filename_path() -> None:
    with pytest.raises(VoiceAudioProcessingError):
        validate_media("sample.wav", "audio/ogg", b"OggSxxxxOpusHead")
    with pytest.raises(VoiceAudioProcessingError):
        validate_media("../sample.wav", "audio/wav", _wav_bytes())
    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE"
    ):
        validate_media(
            "sample.wav",
            "audio/wav",
            b"RF64\xff\xff\xff\xffWAVE" + b"\x00" * 64,
        )


def test_ffmpeg_missing_timeout_nonzero_and_argument_list(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "unsafe ; name.webm"
    output = tmp_path / "normalized.wav"
    source.write_bytes(b"\x1aE\xdf\xa3xxA_OPUS")
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable="ffmpeg", timeout_seconds=1, max_output_bytes=200_000
    )
    monkeypatch.setattr(
        "backend.voice_enrollment.normalizer.shutil.which", lambda _: None
    )
    with pytest.raises(VoiceAudioProcessingError, match="VOICE_NORMALIZER_UNAVAILABLE"):
        normalizer.normalize(source, output, VoiceContainer.WEBM)

    executable = tmp_path / "FFmpeg Tools" / "ffmpeg.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"fake executable")
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable=str(executable), timeout_seconds=1, max_output_bytes=200_000
    )

    def timeout(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        assert isinstance(command, list)
        assert kwargs["shell"] is False
        if command[1:] == ["-version"]:
            return subprocess.CompletedProcess(
                command, 0, stdout="ffmpeg version test-build\n"
            )
        assert command[0] == str(executable)
        assert str(source) in command
        raise subprocess.TimeoutExpired(command, 1)

    monkeypatch.setattr("backend.voice_enrollment.normalizer.subprocess.run", timeout)
    with pytest.raises(VoiceAudioProcessingError, match="VOICE_SAMPLE_DECODE_TIMEOUT"):
        normalizer.normalize(source, output, VoiceContainer.WEBM)

    def nonzero(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[1:] == ["-version"]:
            return subprocess.CompletedProcess(
                command, 0, stdout="ffmpeg version test-build\n"
            )
        output.with_suffix(".normalizing").write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr("backend.voice_enrollment.normalizer.subprocess.run", nonzero)
    with pytest.raises(VoiceAudioProcessingError, match="VOICE_SAMPLE_DECODE_FAILED"):
        normalizer.normalize(source, output, VoiceContainer.WEBM)
    assert not output.exists()
    assert not output.with_suffix(".normalizing").exists()

    def no_output(
        command: list[str], **kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        if command[1:] == ["-version"]:
            return subprocess.CompletedProcess(
                command, 0, stdout="ffmpeg version test-build\n"
            )
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("backend.voice_enrollment.normalizer.subprocess.run", no_output)
    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_NORMALIZATION_FAILED"
    ):
        normalizer.normalize(source, output, VoiceContainer.OGG)


def test_ffmpeg_rejects_invalid_absolute_path_and_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.webm"
    output = tmp_path / "output.wav"
    source.write_bytes(b"\x1aE\xdf\xa3xxA_OPUS")
    directory = tmp_path / "not-an-executable"
    directory.mkdir()
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable=str(directory), timeout_seconds=1, max_output_bytes=200_000
    )
    with pytest.raises(VoiceAudioProcessingError, match="VOICE_NORMALIZER_UNAVAILABLE"):
        normalizer.normalize(source, output, VoiceContainer.WEBM)

    invalid = tmp_path / "invalid ffmpeg.exe"
    invalid.write_text("not ffmpeg", encoding="utf-8")
    normalizer = HybridVoiceAudioNormalizer(
        ffmpeg_executable=str(invalid), timeout_seconds=1, max_output_bytes=200_000
    )
    monkeypatch.setattr(
        "backend.voice_enrollment.normalizer.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="different tool\n"
        ),
    )
    with pytest.raises(VoiceAudioProcessingError, match="VOICE_NORMALIZER_UNAVAILABLE"):
        normalizer.normalize(source, output, VoiceContainer.WEBM)
    assert not output.exists()


def test_validator_pass_warnings_and_failures(tmp_path: Path) -> None:
    validator = VoiceAudioValidator(min_duration_seconds=0.5, max_duration_seconds=2)
    passing = tmp_path / "pass.wav"
    passing.write_bytes(_wav_bytes(duration=1, rate=48_000, channels=1, value=5000))
    result = validator.validate(passing)
    assert result.quality_status == "PASS"
    assert result.sample_rate == 48_000
    assert result.channels == 1
    assert result.bit_depth == 16

    silent = tmp_path / "silent.wav"
    silent.write_bytes(_wav_bytes(duration=1, rate=48_000, channels=1, value=0))
    warning = validator.validate(silent)
    assert warning.quality_status == "WARNING"
    assert {"LOW_VOLUME", "HIGH_SILENCE_RATIO"} <= set(warning.quality_warnings)

    clipping = tmp_path / "clipping.wav"
    clipping.write_bytes(_wav_bytes(duration=1, rate=48_000, channels=1, value=32_767))
    clipped = validator.validate(clipping)
    assert "POSSIBLE_CLIPPING" in clipped.quality_warnings

    short = tmp_path / "short.wav"
    short.write_bytes(_wav_bytes(duration=0.1, rate=48_000, channels=1))
    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_DURATION_TOO_SHORT"
    ):
        validator.validate(short)
    long = tmp_path / "long.wav"
    long.write_bytes(_wav_bytes(duration=2.1, rate=48_000, channels=1))
    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_DURATION_TOO_LONG"
    ):
        validator.validate(long)
    corrupt = tmp_path / "corrupt.wav"
    corrupt.write_bytes(b"not-wave")
    with pytest.raises(
        VoiceAudioProcessingError, match="VOICE_SAMPLE_INVALID_WAV_OUTPUT"
    ):
        validator.validate(corrupt)


def test_voice_enrollment_storage_promotes_and_cleans_safely(tmp_path: Path) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.ensure_layout()
    voice_storage = VoiceEnrollmentStorage(storage)
    enrollment_id = str(uuid.uuid4())
    sample_id = str(uuid.uuid4())
    profile_id = str(uuid.uuid4())
    paths = voice_storage.sample_paths(enrollment_id, sample_id, VoiceContainer.WAV)
    voice_storage.create_sample_directory(paths)
    paths.normalized.write_bytes(_wav_bytes())
    destination = voice_storage.promoted_path(profile_id, sample_id)

    voice_storage.promote(paths.normalized, destination)

    assert destination.is_file()
    assert not paths.normalized.exists()
    with pytest.raises(FileExistsError):
        paths.normalized.write_bytes(b"new")
        voice_storage.promote(paths.normalized, destination)
    voice_storage.delete_file(storage.relative_path(destination))
    assert not destination.exists()
    voice_storage.remove_sample_directory(paths.directory)
    with pytest.raises(ValueError):
        voice_storage.delete_file("../outside.wav")
    with pytest.raises(ValueError):
        voice_storage.sample_paths("not-a-uuid", sample_id, VoiceContainer.WAV)
