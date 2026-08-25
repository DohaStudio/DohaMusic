from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from backend.audio_analysis import AudioAnalysisStatus, DefaultTempoAnalyzer


def _write_click_track(
    path: Path,
    bpm: float,
    *,
    duration_seconds: float = 16.0,
    sample_rate: int = 22_050,
) -> Path:
    samples = np.zeros(round(duration_seconds * sample_rate), dtype=np.float64)
    click_length = max(8, round(sample_rate * 0.012))
    click = np.hanning(click_length * 2)[:click_length]
    interval = 60.0 * sample_rate / bpm
    for beat in np.arange(0.25 * sample_rate, samples.size - click_length, interval):
        start = round(float(beat))
        samples[start : start + click_length] += click
    wavfile.write(path, sample_rate, np.int16(np.clip(samples, -1, 1) * 32_767))
    return path


@pytest.mark.parametrize("bpm", [60, 80, 100, 120, 140, 160])
def test_estimates_fixed_bpm_without_using_requested_bpm(tmp_path: Path, bpm: int) -> None:
    path = _write_click_track(tmp_path / f"{bpm}.wav", bpm)
    analyzer = DefaultTempoAnalyzer()

    matching = analyzer.analyze(path, requested_bpm=float(bpm))
    unrelated = analyzer.analyze(path, requested_bpm=75.0)

    assert matching.status is AudioAnalysisStatus.COMPLETED
    assert matching.detected_bpm == pytest.approx(bpm, abs=3.0)
    assert matching.confidence is not None and 0 <= matching.confidence <= 1
    assert unrelated.detected_bpm == matching.detected_bpm
    assert matching.absolute_bpm_error == pytest.approx(abs(matching.bpm_error or 0))


def test_marks_half_and_double_time_candidates_against_requested_bpm(
    tmp_path: Path,
) -> None:
    analyzer = DefaultTempoAnalyzer()

    half_time = analyzer.analyze(_write_click_track(tmp_path / "half.wav", 60), requested_bpm=120)
    double_time = analyzer.analyze(
        _write_click_track(tmp_path / "double.wav", 160), requested_bpm=80
    )

    assert half_time.half_time_candidate is True
    assert half_time.double_time_candidate is False
    assert double_time.double_time_candidate is True
    assert double_time.half_time_candidate is False


def test_returns_safe_failures_for_silence_short_and_invalid_audio(
    tmp_path: Path,
) -> None:
    analyzer = DefaultTempoAnalyzer()
    silence = tmp_path / "silence.wav"
    short = tmp_path / "short.wav"
    invalid = tmp_path / "invalid.wav"
    wavfile.write(silence, 22_050, np.zeros(22_050 * 5, dtype=np.int16))
    wavfile.write(short, 22_050, np.zeros(22_050, dtype=np.int16))
    invalid.write_bytes(b"not a wav")

    silent_result = analyzer.analyze(silence, requested_bpm=120)
    short_result = analyzer.analyze(short, requested_bpm=120)
    invalid_result = analyzer.analyze(invalid, requested_bpm=120)

    assert silent_result.status is AudioAnalysisStatus.FAILED
    assert silent_result.detected_bpm is None
    assert silent_result.warnings[0].code == "TEMPO_SILENT_AUDIO"
    assert short_result.warnings[0].code == "TEMPO_AUDIO_TOO_SHORT"
    assert invalid_result.warnings[0].code == "TEMPO_DETECTION_FAILED"
    assert all(
        result.requested_bpm == 120 for result in (silent_result, short_result, invalid_result)
    )


def test_rejects_non_wav_without_exposing_the_path(tmp_path: Path) -> None:
    path = tmp_path / "private-input.mp3"
    path.write_bytes(b"audio")

    result = DefaultTempoAnalyzer().analyze(path)

    assert result.status is AudioAnalysisStatus.UNSUPPORTED
    assert str(path) not in result.model_dump_json()
