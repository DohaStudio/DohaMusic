"""Deterministic NumPy/SciPy audio mixing and quality analysis."""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import psutil
from scipy.io import wavfile
from scipy.signal import resample_poly

from backend.audio.config import AudioMixerConfig
from backend.audio.interfaces import AudioMixInput, AudioMixResult


class DefaultAudioMixer:
    provider = "default"

    def __init__(self, config: AudioMixerConfig) -> None:
        self.config = config
        self.output_root = Path(config.output_root)

    def mix(self, request: AudioMixInput) -> AudioMixResult:
        started_at = time.perf_counter()
        cpu_started_at = time.process_time()
        process = psutil.Process()
        rss_before = process.memory_info().rss
        if not request.vocals_path.is_file() or not request.instrumental_path.is_file():
            raise FileNotFoundError("Mixer input is unavailable")

        vocal_rate, vocals = _read_audio(request.vocals_path)
        instrumental_rate, instrumental = _read_audio(request.instrumental_path)
        vocals = _synchronize(vocals, vocal_rate, self.config)
        instrumental = _synchronize(instrumental, instrumental_rate, self.config)
        vocals, instrumental = _match_length(vocals, instrumental)

        vocal_gain = _db_to_linear(self.config.vocal_gain_db)
        instrumental_gain = _db_to_linear(self.config.instrumental_gain_db)
        mixed = vocals * vocal_gain + instrumental * instrumental_gain
        raw_quality = _quality(mixed)

        if self.config.limiter == "soft":
            mixed = _soft_limit(mixed)

        normalization_gain = 1.0
        if self.config.normalization == "peak":
            peak = float(np.max(np.abs(mixed), initial=0.0))
            if peak > 0:
                target_peak = _db_to_linear(-self.config.headroom_db)
                normalization_gain = target_peak / peak
                mixed *= normalization_gain

        _apply_fades(
            mixed,
            self.config.sample_rate,
            self.config.fade_in_ms,
            self.config.fade_out_ms,
        )
        processed_quality = _quality(mixed)
        rendered = np.clip(mixed, -1.0, 1.0)
        output_quality = _quality(rendered)
        pcm = np.rint(rendered * 32_767.0).astype(np.int16)

        output = self.output_root / request.job_id / "mixed.wav"
        output.parent.mkdir(parents=True, exist_ok=True)
        wavfile.write(output, self.config.sample_rate, pcm)

        elapsed = time.perf_counter() - started_at
        cpu_time = time.process_time() - cpu_started_at
        rss_after = process.memory_info().rss
        duration = len(pcm) / self.config.sample_rate
        metadata: dict[str, Any] = {
            "provider": self.provider,
            "mixing_time_seconds": elapsed,
            "cpu_time_seconds": cpu_time,
            "memory_rss_before_mb": rss_before / (1024 * 1024),
            "memory_rss_after_mb": rss_after / (1024 * 1024),
            "memory_rss_delta_mb": (rss_after - rss_before) / (1024 * 1024),
            "output_size_bytes": output.stat().st_size,
            "duration_seconds": duration,
            "sample_rate": self.config.sample_rate,
            "channels": self.config.channels,
            "gain": {
                "vocals_db": self.config.vocal_gain_db,
                "instrumental_db": self.config.instrumental_gain_db,
                "normalization_db": _linear_to_db(normalization_gain),
            },
            "headroom_target_db": self.config.headroom_db,
            "headroom_actual_db": output_quality["headroom_db"],
            "normalization": self.config.normalization,
            "limiter": self.config.limiter,
            "fade_in_ms": self.config.fade_in_ms,
            "fade_out_ms": self.config.fade_out_ms,
            "peak": output_quality["peak"],
            "peak_dbfs": output_quality["peak_dbfs"],
            "rms": output_quality["rms"],
            "rms_dbfs": output_quality["rms_dbfs"],
            "silence": output_quality["silence"],
            "clipping": {
                "detected": processed_quality["clipping_ratio"] > 0,
                "ratio": processed_quality["clipping_ratio"],
                "over_range": processed_quality["over_range"],
                "pre_processing_peak": raw_quality["peak"],
                "pre_processing_clipping_ratio": raw_quality["clipping_ratio"],
                "pre_processing_over_range": raw_quality["over_range"],
                "rendered_peak": output_quality["peak"],
                "true_peak_supported": False,
                "true_peak_dbfs": None,
            },
        }
        return AudioMixResult(
            audio_path=output,
            provider=self.provider,
            mixing_time_seconds=elapsed,
            metadata=metadata,
        )


def _read_audio(path: Path) -> tuple[int, np.ndarray]:
    sample_rate, data = wavfile.read(path)
    if data.size == 0:
        raise ValueError("Audio input is empty")
    if np.issubdtype(data.dtype, np.integer):
        if np.issubdtype(data.dtype, np.unsignedinteger):
            midpoint = (np.iinfo(data.dtype).max + 1) / 2
            audio = (data.astype(np.float64) - midpoint) / midpoint
        else:
            scale = float(max(abs(np.iinfo(data.dtype).min), np.iinfo(data.dtype).max))
            audio = data.astype(np.float64) / scale
    elif np.issubdtype(data.dtype, np.floating):
        audio = data.astype(np.float64)
    else:
        raise ValueError(f"Unsupported WAV dtype: {data.dtype}")
    if not np.all(np.isfinite(audio)):
        raise ValueError("Audio input contains non-finite samples")
    if audio.ndim == 1:
        audio = audio[:, np.newaxis]
    if audio.ndim != 2 or audio.shape[1] not in {1, 2}:
        raise ValueError("Only mono or stereo WAV input is supported")
    return sample_rate, audio


def _synchronize(
    audio: np.ndarray, sample_rate: int, config: AudioMixerConfig
) -> np.ndarray:
    if audio.shape[1] == 1 and config.channels == 2:
        audio = np.repeat(audio, 2, axis=1)
    if audio.shape[1] != config.channels:
        raise ValueError("Audio channel synchronization failed")
    if sample_rate != config.sample_rate:
        divisor = math.gcd(sample_rate, config.sample_rate)
        audio = resample_poly(
            audio,
            config.sample_rate // divisor,
            sample_rate // divisor,
            axis=0,
        )
    return np.asarray(audio, dtype=np.float64)


def _match_length(
    vocals: np.ndarray, instrumental: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    target_length = max(len(vocals), len(instrumental))
    return _pad(vocals, target_length), _pad(instrumental, target_length)


def _pad(audio: np.ndarray, target_length: int) -> np.ndarray:
    if len(audio) == target_length:
        return audio
    return np.pad(audio, ((0, target_length - len(audio)), (0, 0)))


def _soft_limit(audio: np.ndarray) -> np.ndarray:
    knee = _db_to_linear(-3.0)
    magnitude = np.abs(audio)
    limited = audio.copy()
    mask = magnitude > knee
    distance = (magnitude[mask] - knee) / (1.0 - knee)
    compressed = knee + (1.0 - knee) * np.tanh(distance)
    limited[mask] = np.sign(audio[mask]) * compressed
    return limited


def _apply_fades(
    audio: np.ndarray, sample_rate: int, fade_in_ms: float, fade_out_ms: float
) -> None:
    fade_in_frames = min(len(audio), round(sample_rate * fade_in_ms / 1_000))
    fade_out_frames = min(len(audio), round(sample_rate * fade_out_ms / 1_000))
    if fade_in_frames > 0:
        audio[:fade_in_frames] *= np.linspace(0.0, 1.0, fade_in_frames)[:, None]
    if fade_out_frames > 0:
        audio[-fade_out_frames:] *= np.linspace(1.0, 0.0, fade_out_frames)[:, None]


def _quality(audio: np.ndarray) -> dict[str, float | bool | None]:
    peak = float(np.max(np.abs(audio), initial=0.0))
    rms = float(np.sqrt(np.mean(np.square(audio))))
    clipping_ratio = float(np.mean(np.abs(audio) > 1.0))
    return {
        "peak": peak,
        "peak_dbfs": _linear_to_db(peak),
        "rms": rms,
        "rms_dbfs": _linear_to_db(rms),
        "headroom_db": -_linear_to_db(peak) if peak > 0 else None,
        "clipping_ratio": clipping_ratio,
        "over_range": peak > 1.0,
        "silence": rms < 1e-5,
    }


def _db_to_linear(value: float) -> float:
    return 10.0 ** (value / 20.0)


def _linear_to_db(value: float) -> float | None:
    return 20.0 * math.log10(value) if value > 0 else None
