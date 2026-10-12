"""Deterministic final-WAV preview rendering without modifying the source."""

from pathlib import Path

import numpy as np
from scipy.io import wavfile

from backend.audio_analysis.contracts import HookAnalysisResult

PREVIEW_VERSION = "1.0"


def render_preview(source: Path, destination: Path, hook: object = None) -> dict:
    if source.resolve() == destination.resolve():
        raise ValueError("Preview must not overwrite source")
    rate, raw = wavfile.read(source)
    if rate <= 0 or raw.ndim not in (1, 2) or raw.size == 0:
        raise ValueError("Invalid WAV")
    if raw.dtype.kind == "i":
        samples = raw.astype(np.float64) / (2 ** (raw.dtype.itemsize * 8 - 1))
    elif raw.dtype == np.uint8:
        samples = (raw.astype(np.float64) - 128) / 128
    elif raw.dtype.kind == "f":
        samples = raw.astype(np.float64)
    else:
        raise ValueError("Unsupported WAV samples")
    if not np.isfinite(samples).all():
        raise ValueError("Nonfinite WAV")
    count = min(len(raw), 15 * rate)
    start = (len(raw) - count) // 2
    strategy = "fallback_middle"
    try:
        candidate_result = HookAnalysisResult.model_validate(hook)
        candidate = candidate_result.candidate
        if (
            candidate_result.hook_analysis_version == "1.0"
            and candidate_result.status.value in {"COMPLETED", "PARTIAL"}
            and candidate is not None
            and candidate.confidence >= 0.50
            and candidate.end_seconds <= len(raw) / rate
            and candidate.duration_seconds >= count / rate
        ):
            proposed = round(candidate.start_seconds * rate)
            if proposed + count <= len(raw):
                start = proposed
                strategy = "hook_candidate"
    except (ValueError, TypeError):
        pass
    segment = samples[start : start + count].copy()
    fade = min(round(rate * 0.020), count // 2)
    if fade:
        ramp = np.linspace(0, 1, fade)
        if segment.ndim == 2:
            ramp = ramp[:, None]
        segment[:fade] *= ramp
        segment[-fade:] *= ramp[::-1]
    pcm = np.clip(np.rint(segment * 32768), -32768, 32767).astype(np.int16)
    wavfile.write(destination, rate, pcm)
    return {
        "version": PREVIEW_VERSION,
        "status": "ready",
        "start_seconds": start / rate,
        "duration_seconds": count / rate,
        "selection_strategy": strategy,
        "sample_rate": rate,
        "channels": 1 if raw.ndim == 1 else raw.shape[1],
    }
