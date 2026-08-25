from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from scipy.io import wavfile

from backend.audio_analysis import (
    AudioAnalysisStatus,
    DefaultHookAnalyzer,
    HookSelectionStrategy,
)

SAMPLE_RATE = 8_000


def _write_wave(path: Path, samples: np.ndarray) -> Path:
    wavfile.write(path, SAMPLE_RATE, np.int16(np.clip(samples, -1, 1) * 32_767))
    return path


def _tone(duration: float, amplitude: float = 0.1, frequency: float = 220) -> np.ndarray:
    times = np.arange(round(duration * SAMPLE_RATE)) / SAMPLE_RATE
    return amplitude * np.sin(2 * np.pi * frequency * times)


def _repeating_hook_fixture(path: Path) -> Path:
    samples = _tone(60, 0.05)
    pattern_times = np.arange(15 * SAMPLE_RATE) / SAMPLE_RATE
    modulation = 0.35 + 0.25 * (np.sin(2 * np.pi * 2 * pattern_times) > 0)
    pattern = modulation * np.sin(2 * np.pi * 440 * pattern_times)
    for start_seconds in (10, 35):
        start = start_seconds * SAMPLE_RATE
        samples[start : start + pattern.size] = pattern
    return _write_wave(path, samples)


def test_selects_repeated_high_energy_hook_candidate(tmp_path: Path) -> None:
    result = DefaultHookAnalyzer().analyze(_repeating_hook_fixture(tmp_path / "repeated-hook.wav"))

    assert result.status is AudioAnalysisStatus.COMPLETED
    assert result.candidate is not None
    assert result.candidate.selection_strategy is HookSelectionStrategy.ENERGY_REPETITION
    assert result.candidate.confidence >= 0.5
    assert result.candidate.duration_seconds == pytest.approx(15.0)
    assert result.candidate.start_seconds == pytest.approx(10.0, abs=2.0)


def test_selects_single_energy_peak_without_claiming_repetition(tmp_path: Path) -> None:
    samples = _tone(60, 0.05)
    peak = _tone(15, 0.75, 440)
    samples[38 * SAMPLE_RATE : 53 * SAMPLE_RATE] = peak

    result = DefaultHookAnalyzer().analyze(_write_wave(tmp_path / "peak.wav", samples))

    assert result.status is AudioAnalysisStatus.COMPLETED
    assert result.candidate is not None
    assert result.candidate.selection_strategy is HookSelectionStrategy.ENERGY_PEAK
    assert result.candidate.start_seconds == pytest.approx(38.0, abs=2.0)


def test_uses_middle_fallback_when_no_hook_evidence_exists(tmp_path: Path) -> None:
    result = DefaultHookAnalyzer().analyze(_write_wave(tmp_path / "steady.wav", _tone(60, 0.1)))

    assert result.status is AudioAnalysisStatus.PARTIAL
    assert result.candidate is not None
    assert result.candidate.selection_strategy is HookSelectionStrategy.FALLBACK_MIDDLE
    assert result.candidate.start_seconds == pytest.approx(22.5)
    assert result.candidate.end_seconds == pytest.approx(37.5)
    assert result.candidate.confidence < 0.5
    assert result.warnings[0].code == "HOOK_FALLBACK_MIDDLE"


def test_short_wav_uses_whole_track_as_partial_fallback(tmp_path: Path) -> None:
    result = DefaultHookAnalyzer().analyze(_write_wave(tmp_path / "short.wav", _tone(8, 0.1)))

    assert result.status is AudioAnalysisStatus.PARTIAL
    assert result.candidate is not None
    assert result.candidate.start_seconds == 0
    assert result.candidate.end_seconds == pytest.approx(8.0)
    assert result.candidate.duration_seconds == pytest.approx(8.0)
    assert result.candidate.selection_strategy is HookSelectionStrategy.FALLBACK_MIDDLE
    assert result.warnings[0].code == "HOOK_AUDIO_TOO_SHORT"


def test_silence_invalid_and_unsupported_audio_fail_safely(tmp_path: Path) -> None:
    silence = _write_wave(tmp_path / "silence.wav", np.zeros(SAMPLE_RATE * 20))
    invalid = tmp_path / "invalid.wav"
    unsupported = tmp_path / "private.mp3"
    invalid.write_bytes(b"not a wav")
    unsupported.write_bytes(b"audio")

    analyzer = DefaultHookAnalyzer()
    silent_result = analyzer.analyze(silence)
    invalid_result = analyzer.analyze(invalid)
    unsupported_result = analyzer.analyze(unsupported)

    assert silent_result.status is AudioAnalysisStatus.FAILED
    assert silent_result.candidate is None
    assert silent_result.warnings[0].code == "HOOK_SILENT_AUDIO"
    assert invalid_result.status is AudioAnalysisStatus.FAILED
    assert invalid_result.candidate is None
    assert unsupported_result.status is AudioAnalysisStatus.UNSUPPORTED
    assert str(unsupported) not in unsupported_result.model_dump_json()
