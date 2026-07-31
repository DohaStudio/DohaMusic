from __future__ import annotations

import json
import wave
from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from backend.audio_analysis import (
    AudioAnalysisStatus,
    DefaultAudioQualityAnalyzer,
    sanitize_result_metadata,
)

SAMPLE_RATE = 48_000


def write_pcm16(path: Path, samples: np.ndarray) -> Path:
    wavfile.write(path, SAMPLE_RATE, samples.astype(np.int16))
    return path


def write_pcm24(path: Path, samples: list[int]) -> Path:
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(3)
        audio.setframerate(SAMPLE_RATE)
        audio.writeframes(
            b"".join(value.to_bytes(3, "little", signed=True) for value in samples)
        )
    return path


@pytest.mark.parametrize("channels", [1, 2])
def test_analyzer_reads_mono_and_stereo_sine_with_bs1770_lufs(
    tmp_path: Path, channels: int
) -> None:
    time_axis = np.arange(SAMPLE_RATE * 3) / SAMPLE_RATE
    signal = 0.1 * np.sin(2 * np.pi * 1_000 * time_axis)
    samples = np.round(signal * 32_767)
    if channels == 2:
        samples = np.column_stack((samples, samples))

    result = DefaultAudioQualityAnalyzer().analyze(
        write_pcm16(tmp_path / f"sine-{channels}.wav", samples)
    )

    assert result.analysis_status == AudioAnalysisStatus.COMPLETED
    assert result.quality is not None
    assert result.quality.duration_seconds == 3.0
    assert result.quality.sample_rate == SAMPLE_RATE
    assert result.quality.channels == channels
    assert result.quality.sample_peak_dbfs == pytest.approx(-20.0, abs=0.01)
    # A 1 kHz, -20 dBFS sine is approximately -23.05 LUFS mono. Identical
    # stereo channels add 3.01 LU within the BS.1770 channel summation.
    expected_lufs = -23.05 if channels == 1 else -20.04
    assert result.quality.integrated_lufs == pytest.approx(expected_lufs, abs=0.1)


def test_analyzer_counts_scalar_clipped_samples_and_ratio(tmp_path: Path) -> None:
    samples = np.array([[32_767, 0], [-32_768, 16_000], [0, 0]], dtype=np.int16)
    result = DefaultAudioQualityAnalyzer().analyze(
        write_pcm16(tmp_path / "clipped.wav", samples)
    )

    assert result.quality is not None
    assert result.quality.clipping_detected is True
    assert result.quality.clipping_sample_count == 2
    assert result.quality.clipping_ratio == pytest.approx(2 / 6)
    assert {warning.code for warning in result.warnings} == {
        "CLIPPING_DETECTED",
        "LUFS_UNAVAILABLE",
    }


@pytest.mark.parametrize("bit_depth", [24, 32])
def test_analyzer_normalizes_common_high_bit_depth_pcm(
    tmp_path: Path, bit_depth: int
) -> None:
    if bit_depth == 24:
        path = write_pcm24(tmp_path / "pcm24.wav", [8_388_607, -8_388_608, 0])
    else:
        path = tmp_path / "pcm32.wav"
        wavfile.write(
            path,
            SAMPLE_RATE,
            np.array([2_147_483_647, -2_147_483_648, 0], dtype=np.int32),
        )

    result = DefaultAudioQualityAnalyzer().analyze(path)

    assert result.quality is not None
    assert result.quality.sample_peak_dbfs == 0.0
    assert result.quality.clipping_sample_count == 2
    assert result.quality.clipping_ratio == pytest.approx(2 / 3)


def test_silence_and_short_audio_are_partial_without_non_finite_json(
    tmp_path: Path,
) -> None:
    silence = np.zeros((SAMPLE_RATE, 2), dtype=np.int16)
    silent_result = DefaultAudioQualityAnalyzer().analyze(
        write_pcm16(tmp_path / "silence.wav", silence)
    )
    short = np.ones((SAMPLE_RATE // 10,), dtype=np.int16)
    short_result = DefaultAudioQualityAnalyzer().analyze(
        write_pcm16(tmp_path / "short.wav", short)
    )

    assert silent_result.analysis_status == AudioAnalysisStatus.PARTIAL
    assert silent_result.quality is not None
    assert silent_result.quality.sample_peak_dbfs is None
    assert silent_result.quality.integrated_lufs is None
    assert {warning.code for warning in silent_result.warnings} == {
        "SILENT_AUDIO",
        "LUFS_UNAVAILABLE",
    }
    assert short_result.analysis_status == AudioAnalysisStatus.PARTIAL
    json.dumps(silent_result.model_dump(mode="json"), allow_nan=False)
    json.dumps(short_result.model_dump(mode="json"), allow_nan=False)


@pytest.mark.parametrize("kind", ["missing", "empty", "invalid"])
def test_missing_empty_and_invalid_wav_fail_safely(tmp_path: Path, kind: str) -> None:
    path = tmp_path / f"{kind}.wav"
    if kind == "empty":
        path.touch()
    elif kind == "invalid":
        path.write_bytes(b"not a wav")

    result = DefaultAudioQualityAnalyzer().analyze(path)

    assert result.analysis_status == AudioAnalysisStatus.FAILED
    assert result.quality is None
    assert result.warnings[0].code == "AUDIO_DECODE_FAILED"
    assert str(path) not in result.warnings[0].message


def test_unsupported_extension_and_channel_count_are_explicit(tmp_path: Path) -> None:
    wrong_extension = tmp_path / "audio.raw"
    wrong_extension.write_bytes(b"audio")
    multichannel = np.zeros((SAMPLE_RATE, 3), dtype=np.int16)
    multichannel_path = write_pcm16(tmp_path / "three-channel.wav", multichannel)

    analyzer = DefaultAudioQualityAnalyzer()
    assert (
        analyzer.analyze(wrong_extension).analysis_status
        == AudioAnalysisStatus.UNSUPPORTED
    )
    result = analyzer.analyze(multichannel_path)
    assert result.analysis_status == AudioAnalysisStatus.UNSUPPORTED
    assert result.warnings[0].code == "UNSUPPORTED_CHANNELS"


def test_non_finite_float_wav_is_invalid(tmp_path: Path) -> None:
    samples = np.zeros((SAMPLE_RATE,), dtype=np.float32)
    samples[100] = np.nan
    path = tmp_path / "nan.wav"
    wavfile.write(path, SAMPLE_RATE, samples)

    result = DefaultAudioQualityAnalyzer().analyze(path)

    assert result.analysis_status == AudioAnalysisStatus.FAILED
    assert result.warnings[0].code == "INVALID_AUDIO_DATA"


def test_public_metadata_allowlist_removes_analysis_internals() -> None:
    metadata = {
        "success": True,
        "audio_analysis": {
            "audio_analysis_version": "1.0",
            "analysis_status": "FAILED",
            "source_file_role": "final_mix",
            "source_path": "D:/private/final.wav",
            "analyzer_command": "private command",
            "stack_trace": "private stack",
            "quality": None,
            "warnings": [
                {"code": "AUDIO_DECODE_FAILED", "message": "조작된 비공개 안내"}
            ],
        },
    }

    public = sanitize_result_metadata(metadata)

    assert public["success"] is True
    assert public["audio_analysis"] == {
        "audio_analysis_version": "1.0",
        "analysis_status": "FAILED",
        "quality": None,
        "warnings": ["오디오 파일을 읽지 못해 품질을 분석하지 못했습니다."],
    }
    assert "private" not in json.dumps(public, ensure_ascii=False)
    assert "조작된" not in json.dumps(public, ensure_ascii=False)
