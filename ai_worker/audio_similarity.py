"""PCM16 and IEEE-float WAV similarity without third-party dependencies."""

from __future__ import annotations

import hashlib
import math
import struct
import sys
from array import array
from pathlib import Path
from typing import Any


def read_wav_samples(path: Path) -> tuple[array[Any], dict[str, int | str]]:
    with path.open("rb") as wav_file:
        if wav_file.read(4) != b"RIFF":
            raise ValueError("File is not a RIFF container")
        wav_file.read(4)
        if wav_file.read(4) != b"WAVE":
            raise ValueError("RIFF container is not WAVE")
        format_info: tuple[int, int, int, int] | None = None
        data = b""
        while chunk_header := wav_file.read(8):
            if len(chunk_header) != 8:
                raise ValueError("WAV chunk header is truncated")
            chunk_id, chunk_size = struct.unpack("<4sI", chunk_header)
            chunk = wav_file.read(chunk_size)
            if len(chunk) != chunk_size:
                raise ValueError("WAV chunk is truncated")
            if chunk_size % 2:
                wav_file.read(1)
            if chunk_id == b"fmt ":
                if len(chunk) < 16:
                    raise ValueError("WAV fmt chunk is invalid")
                audio_format, channels, sample_rate, _, _, bits = struct.unpack(
                    "<HHIIHH", chunk[:16]
                )
                format_info = (audio_format, channels, sample_rate, bits)
            elif chunk_id == b"data":
                data = chunk
        if format_info is None or not data:
            raise ValueError("WAV fmt or data chunk is missing")

    audio_format, channels, sample_rate, bits = format_info
    if audio_format == 1 and bits == 16:
        samples: array[Any] = array("h")
        normalization = 32768.0
        format_name = "pcm16"
    elif audio_format == 3 and bits == 32:
        samples = array("f")
        normalization = 1.0
        format_name = "float32"
    else:
        raise ValueError(f"Unsupported WAV format tag={audio_format}, bits={bits}")
    samples.frombytes(data)
    if sys.byteorder != "little":
        samples.byteswap()
    if len(samples) % channels:
        raise ValueError("WAV sample count is not aligned to channels")
    return samples, {
        "sample_format": format_name,
        "sample_rate": sample_rate,
        "channels": channels,
        "frame_count": len(samples) // channels,
        "normalization": normalization,
    }


def sample_hash(samples: array[Any]) -> str:
    return hashlib.sha256(samples.tobytes()).hexdigest()


def compare_wav(reference: Path, candidate: Path) -> dict[str, Any]:
    reference_samples, reference_info = read_wav_samples(reference)
    candidate_samples, candidate_info = read_wav_samples(candidate)
    if reference_info != candidate_info or len(reference_samples) != len(
        candidate_samples
    ):
        raise ValueError("WAV shape or format does not match")

    count = len(reference_samples)
    if count == 0:
        raise ValueError("WAV contains no samples")
    sum_squared_error = 0.0
    max_absolute_difference = 0.0
    reference_sum = 0.0
    candidate_sum = 0.0
    for reference_value, candidate_value in zip(
        reference_samples, candidate_samples, strict=True
    ):
        difference = float(reference_value) - float(candidate_value)
        sum_squared_error += difference * difference
        max_absolute_difference = max(max_absolute_difference, abs(difference))
        reference_sum += float(reference_value)
        candidate_sum += float(candidate_value)

    reference_mean = reference_sum / count
    candidate_mean = candidate_sum / count
    covariance = 0.0
    reference_variance = 0.0
    candidate_variance = 0.0
    for reference_value, candidate_value in zip(
        reference_samples, candidate_samples, strict=True
    ):
        reference_centered = float(reference_value) - reference_mean
        candidate_centered = float(candidate_value) - candidate_mean
        covariance += reference_centered * candidate_centered
        reference_variance += reference_centered * reference_centered
        candidate_variance += candidate_centered * candidate_centered

    samples_identical = reference_samples == candidate_samples
    denominator = math.sqrt(reference_variance * candidate_variance)
    correlation = covariance / denominator if denominator else float(samples_identical)
    normalization = float(reference_info.pop("normalization"))
    rmse = math.sqrt(sum_squared_error / count)
    return {
        **reference_info,
        "sample_count": count,
        "reference_sample_sha256": sample_hash(reference_samples),
        "candidate_sample_sha256": sample_hash(candidate_samples),
        "samples_identical": samples_identical,
        "rmse_native": round(rmse, 9),
        "normalized_rmse": round(rmse / normalization, 9),
        "max_absolute_difference_native": round(max_absolute_difference, 9),
        "normalized_max_absolute_difference": round(
            max_absolute_difference / normalization, 9
        ),
        "correlation": round(correlation, 9),
    }
