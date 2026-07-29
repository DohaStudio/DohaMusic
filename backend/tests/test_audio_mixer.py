from __future__ import annotations

import json
import math

import numpy as np
import pytest
from scipy.io import wavfile

from backend.audio.config import AudioMixerConfig
from backend.audio.default_mixer import DefaultAudioMixer
from backend.audio.factory import create_audio_mixer
from backend.audio.interfaces import AudioMixInput
from backend.audio.mock_mixer import MockAudioMixer
from backend.core.config import Settings


def write_audio(path, data: np.ndarray, sample_rate: int = 48_000) -> None:
    wavfile.write(path, sample_rate, data)


def build_mixer(tmp_path, **overrides) -> DefaultAudioMixer:
    values = {
        "output_root": str(tmp_path / "outputs"),
        "vocal_gain_db": 0.0,
        "instrumental_gain_db": 0.0,
        "headroom_db": 1.0,
        "normalization": "peak",
        "limiter": "soft",
        "fade_in_ms": 10.0,
        "fade_out_ms": 10.0,
    }
    values.update(overrides)
    return DefaultAudioMixer(AudioMixerConfig(**values))


def mix(
    mixer, tmp_path, vocals, instrumental, vocal_rate=48_000, instrumental_rate=48_000
):
    vocal_path = tmp_path / "vocals.wav"
    instrumental_path = tmp_path / "instrumental.wav"
    write_audio(vocal_path, vocals, vocal_rate)
    write_audio(instrumental_path, instrumental, instrumental_rate)
    return mixer.mix(AudioMixInput("job", vocal_path, instrumental_path))


def test_gain_and_volume_balance_are_applied(tmp_path) -> None:
    frames = np.full((4_800, 2), 0.1, dtype=np.float32)
    mixer = build_mixer(
        tmp_path,
        vocal_gain_db=6.020599913,
        normalization="off",
        limiter="bypass",
        fade_in_ms=0.0,
        fade_out_ms=0.0,
    )
    result = mix(mixer, tmp_path, frames, frames)
    _, output = wavfile.read(result.audio_path)
    assert np.max(output / 32_767.0) == pytest.approx(0.3, abs=1e-3)
    assert result.metadata["gain"]["vocals_db"] == pytest.approx(6.020599913)


def test_peak_normalization_meets_configured_headroom(tmp_path) -> None:
    frames = np.full((4_800, 2), 0.8, dtype=np.float32)
    result = mix(build_mixer(tmp_path), tmp_path, frames, frames)
    expected_peak = 10 ** (-1.0 / 20.0)
    assert result.metadata["peak"] == pytest.approx(expected_peak, abs=1e-6)
    assert result.metadata["headroom_actual_db"] == pytest.approx(1.0, abs=1e-5)
    assert result.metadata["clipping"]["pre_processing_peak"] > 1.0
    assert result.metadata["clipping"]["detected"] is False


def test_bypass_records_clipping_and_over_range(tmp_path) -> None:
    frames = np.full((4_800, 2), 0.8, dtype=np.float32)
    mixer = build_mixer(
        tmp_path,
        normalization="off",
        limiter="bypass",
        fade_in_ms=0.0,
        fade_out_ms=0.0,
    )
    result = mix(mixer, tmp_path, frames, frames)
    assert result.metadata["clipping"]["detected"] is True
    assert result.metadata["clipping"]["over_range"] is True
    assert result.metadata["clipping"]["ratio"] == pytest.approx(1.0)


def test_fade_in_and_out_reach_zero(tmp_path) -> None:
    frames = np.full((4_800, 2), 0.1, dtype=np.float32)
    mixer = build_mixer(tmp_path, normalization="off", limiter="bypass")
    result = mix(mixer, tmp_path, frames, frames)
    _, output = wavfile.read(result.audio_path)
    assert np.all(output[0] == 0)
    assert np.all(output[-1] == 0)
    assert np.max(np.abs(output[2_400])) > 0


def test_sample_rate_channel_and_length_are_synchronized(tmp_path) -> None:
    vocals = np.full(2_400, 0.1, dtype=np.float32)
    instrumental = np.full((9_600, 2), 0.1, dtype=np.float32)
    result = mix(
        build_mixer(tmp_path),
        tmp_path,
        vocals,
        instrumental,
        vocal_rate=24_000,
        instrumental_rate=48_000,
    )
    sample_rate, output = wavfile.read(result.audio_path)
    assert sample_rate == 48_000
    assert output.shape == (9_600, 2)
    assert result.metadata["duration_seconds"] == pytest.approx(0.2)


def test_metadata_contains_quality_and_resource_measurements(tmp_path) -> None:
    time_axis = np.arange(4_800) / 48_000
    tone = (0.2 * np.sin(2 * math.pi * 440 * time_axis)).astype(np.float32)
    result = mix(build_mixer(tmp_path), tmp_path, tone, tone)
    assert {
        "peak",
        "rms",
        "headroom_actual_db",
        "gain",
        "duration_seconds",
        "sample_rate",
        "channels",
        "clipping",
        "limiter",
        "normalization",
        "output_size_bytes",
        "cpu_time_seconds",
        "memory_rss_delta_mb",
    }.issubset(result.metadata)
    assert result.metadata["clipping"]["true_peak_supported"] is False
    assert result.metadata["silence"] is False


def test_silence_metadata_is_valid_json(tmp_path) -> None:
    silence = np.zeros((4_800, 2), dtype=np.float32)
    result = mix(build_mixer(tmp_path), tmp_path, silence, silence)
    assert result.metadata["silence"] is True
    assert result.metadata["peak_dbfs"] is None
    assert result.metadata["rms_dbfs"] is None
    assert result.metadata["headroom_actual_db"] is None
    json.dumps(result.metadata, allow_nan=False)


def test_factory_keeps_mock_and_defaults_to_real_mixer(tmp_path) -> None:
    assert isinstance(create_audio_mixer(Settings(), tmp_path), DefaultAudioMixer)
    assert isinstance(
        create_audio_mixer(Settings(audio_mixer="mock"), tmp_path), MockAudioMixer
    )
