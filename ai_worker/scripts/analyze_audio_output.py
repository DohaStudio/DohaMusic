"""Report objective audio signal checks without claiming perceptual quality."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import soundfile


def analyze(path: Path) -> dict[str, float | int | str | bool]:
    audio, sample_rate = soundfile.read(path, always_2d=True, dtype="float32")
    absolute = np.abs(audio)
    peak = float(absolute.max(initial=0.0))
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    return {
        "path": path.name,
        "sample_rate": sample_rate,
        "channels": int(audio.shape[1]),
        "duration_seconds": round(len(audio) / sample_rate, 3),
        "peak_amplitude": round(peak, 6),
        "rms_dbfs": round(20 * math.log10(max(rms, 1e-12)), 3),
        "near_silence_ratio": round(float(np.mean(absolute < 1e-4)), 6),
        "clipped_sample_ratio": round(float(np.mean(absolute >= 0.999)), 6),
        "non_silent": bool(rms > 1e-4),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path)
    args = parser.parse_args()
    if not args.audio.is_file():
        parser.error("audio file does not exist")
    print(json.dumps(analyze(args.audio), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
