"""Validated DSP policy passed to the default mixer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

NormalizationMode = Literal["off", "peak"]
LimiterMode = Literal["bypass", "soft"]


@dataclass(frozen=True, slots=True)
class AudioMixerConfig:
    output_root: str
    vocal_gain_db: float
    instrumental_gain_db: float
    headroom_db: float
    normalization: NormalizationMode
    limiter: LimiterMode
    fade_in_ms: float
    fade_out_ms: float
    sample_rate: int = 48_000
    channels: int = 2
