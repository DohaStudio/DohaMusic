"""Deterministic PCM proof tests for Clip loop rendering authority."""

from __future__ import annotations

import io
import shutil
import struct
import wave
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.audio.working_preview_renderer import (
    FfmpegWorkingCompositionPreviewRenderer,
    PreviewRenderClip,
)

RATE = 48_000
BLOCK = 480
LEVELS = (2_000, 4_000, 6_000, 8_000)


def _source(path: Path) -> None:
    samples = bytearray()
    for level in LEVELS:
        for _ in range(BLOCK):
            samples.extend(struct.pack("<hh", level, level))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(RATE)
        output.writeframes(samples)


def _render(
    tmp_path: Path,
    *,
    duration_blocks: float,
    phase_blocks: int = 0,
    gain_db: Decimal = Decimal("0.00"),
    fade_in_blocks: int = 0,
    fade_out_blocks: int = 0,
) -> list[int]:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg runtime is unavailable")
    artifact_id = uuid4()
    source = tmp_path / f"source-{uuid4()}.wav"
    _source(source)
    payload = source.read_bytes()

    @contextmanager
    def open_artifact(candidate: UUID):
        assert candidate == artifact_id
        yield len(payload), io.BytesIO(payload)

    duration_us = round(duration_blocks * 10_000)
    clip = PreviewRenderClip(
        clip_id=uuid4(),
        track_order=0,
        canonical_order=0,
        artifact_id=artifact_id,
        source_in_us=0,
        source_out_us=40_000,
        timeline_start_us=0,
        timeline_duration_us=duration_us,
        manifest_schema=4,
        loop_enabled=True,
        loop_phase_us=phase_blocks * 10_000,
        gain_db=gain_db,
        fade_in_us=fade_in_blocks * 10_000,
        fade_out_us=fade_out_blocks * 10_000,
    )
    renderer = FfmpegWorkingCompositionPreviewRenderer(
        ffmpeg_executable=ffmpeg,
        temp_root=tmp_path / "runtime",
        open_artifact=open_artifact,
    )
    with (
        renderer.render([clip], track_count=1) as rendered,
        wave.open(str(rendered.path), "rb") as output,
    ):
        frames = output.readframes(output.getnframes())
    stereo = struct.unpack(f"<{len(frames) // 2}h", frames)
    return list(stereo[::2])


def _block_means(samples: list[int]) -> list[float]:
    return [
        sum(samples[index : index + BLOCK]) / BLOCK
        for index in range(0, len(samples), BLOCK)
        if len(samples[index : index + BLOCK]) == BLOCK
    ]


@pytest.mark.parametrize(
    ("duration", "phase", "expected"),
    [
        (2, 0, [2_000, 4_000]),
        (4, 0, [2_000, 4_000, 6_000, 8_000]),
        (4, 1, [4_000, 6_000, 8_000, 2_000]),
        (8, 0, list(LEVELS) * 2),
        (10, 0, list(LEVELS) * 2 + [2_000, 4_000]),
        (5, 3, [8_000, 2_000, 4_000, 6_000, 8_000]),
    ],
)
def test_loop_renderer_matches_phase_equation_for_short_equal_long_and_partial_cycles(
    tmp_path: Path, duration: int, phase: int, expected: list[int]
) -> None:
    means = _block_means(_render(tmp_path, duration_blocks=duration, phase_blocks=phase))
    assert means == pytest.approx(expected, abs=25)


def test_loop_renderer_applies_one_gain_to_every_expanded_cycle(tmp_path: Path) -> None:
    means = _block_means(_render(tmp_path, duration_blocks=8, gain_db=Decimal("-6.02")))
    assert means == pytest.approx([value * 10 ** (-6.02 / 20) for value in LEVELS * 2], abs=25)


def test_loop_renderer_applies_fade_once_to_full_timeline_not_each_cycle(tmp_path: Path) -> None:
    means = _block_means(_render(tmp_path, duration_blocks=12, fade_in_blocks=2, fade_out_blocks=2))
    assert means[0] < LEVELS[0] * 0.6
    assert means[1] < LEVELS[1]
    assert means[4:8] == pytest.approx(LEVELS, abs=25)
    assert means[8] == pytest.approx(LEVELS[0], abs=25)
    assert means[-1] < LEVELS[-1] * 0.6


def test_loop_renderer_combines_gain_then_full_timeline_fade(tmp_path: Path) -> None:
    means = _block_means(
        _render(
            tmp_path,
            duration_blocks=8,
            gain_db=Decimal("-6.02"),
            fade_in_blocks=2,
            fade_out_blocks=2,
        )
    )
    gain = 10 ** (-6.02 / 20)
    assert means[2:6] == pytest.approx(
        [value * gain for value in [6_000, 8_000, 2_000, 4_000]], abs=25
    )
    assert means[0] < 2_000 * gain * 0.6
    assert means[-1] < 8_000 * gain * 0.6
