from __future__ import annotations

import wave
from array import array
from pathlib import Path
from struct import pack

import pytest

from ai_worker.audio_similarity import compare_wav


def write_wav(path: Path, samples: list[int]) -> None:
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(48_000)
        wav_file.writeframes(array("h", samples).tobytes())


def write_float32_wav(path: Path, samples: list[float]) -> None:
    data = pack(f"<{len(samples)}f", *samples)
    path.write_bytes(
        b"RIFF"
        + pack("<I", 36 + len(data))
        + b"WAVEfmt "
        + pack("<IHHIIHH", 16, 3, 1, 48_000, 192_000, 4, 32)
        + b"data"
        + pack("<I", len(data))
        + data
    )


def test_identical_pcm_is_fully_reproducible(tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    candidate = tmp_path / "candidate.wav"
    write_wav(reference, [0, 100, -100, 200])
    write_wav(candidate, [0, 100, -100, 200])

    result = compare_wav(reference, candidate)

    assert result["samples_identical"] is True
    assert result["rmse_native"] == 0
    assert result["correlation"] == 1


def test_different_pcm_reports_distance_and_correlation(tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    candidate = tmp_path / "candidate.wav"
    write_wav(reference, [0, 100, -100, 200])
    write_wav(candidate, [0, 101, -99, 198])

    result = compare_wav(reference, candidate)

    assert result["samples_identical"] is False
    assert result["max_absolute_difference_native"] == 2
    assert result["normalized_rmse"] > 0
    assert result["correlation"] > 0.99


def test_mismatched_wav_shape_is_rejected(tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    candidate = tmp_path / "candidate.wav"
    write_wav(reference, [0, 100])
    write_wav(candidate, [0, 100, 200])

    with pytest.raises(ValueError, match="shape"):
        compare_wav(reference, candidate)


def test_float32_wav_is_supported(tmp_path: Path) -> None:
    reference = tmp_path / "reference.wav"
    candidate = tmp_path / "candidate.wav"
    write_float32_wav(reference, [0.0, 0.25, -0.25])
    write_float32_wav(candidate, [0.0, 0.25, -0.25])

    result = compare_wav(reference, candidate)

    assert result["sample_format"] == "float32"
    assert result["samples_identical"] is True
