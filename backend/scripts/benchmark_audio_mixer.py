"""Run a deterministic synthetic benchmark for the default audio mixer."""

from __future__ import annotations

import json
import math
import tempfile
from pathlib import Path

import numpy as np
from scipy.io import wavfile

from backend.audio.config import AudioMixerConfig
from backend.audio.default_mixer import DefaultAudioMixer
from backend.audio.interfaces import AudioMixInput
from backend.scripts.benchmark_pipeline import run_benchmark as run_pipeline_benchmark


def _tone(frequency: float, duration_seconds: float, amplitude: float) -> np.ndarray:
    sample_rate = 48_000
    time_axis = np.arange(round(sample_rate * duration_seconds)) / sample_rate
    mono = amplitude * np.sin(2 * math.pi * frequency * time_axis)
    return np.column_stack((mono, mono)).astype(np.float32)


def run_benchmark() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="dohamusic-mixer-") as temp_dir:
        root = Path(temp_dir)
        vocals = root / "vocals.wav"
        instrumental = root / "instrumental.wav"
        wavfile.write(vocals, 48_000, _tone(440.0, 10.0, 0.4))
        wavfile.write(instrumental, 48_000, _tone(220.0, 10.0, 0.5))
        mixer = DefaultAudioMixer(
            AudioMixerConfig(
                output_root=str(root / "outputs"),
                vocal_gain_db=0.0,
                instrumental_gain_db=0.0,
                headroom_db=1.0,
                normalization="peak",
                limiter="soft",
                fade_in_ms=10.0,
                fade_out_ms=10.0,
            )
        )
        result = mixer.mix(
            AudioMixInput(
                job_id="EXP-006",
                vocals_path=vocals,
                instrumental_path=instrumental,
            )
        )
        pipeline = run_pipeline_benchmark(audio_mixer="default")
        return {
            "mixer": result.metadata,
            "pipeline": {
                "execution_time_seconds": pipeline["execution_time_seconds"],
                "mixer_step": next(
                    item for item in pipeline["step_execution"] if item["step"] == "mixer"
                ),
                "success": pipeline["success"],
            },
        }


def main() -> int:
    print(json.dumps(run_benchmark(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
