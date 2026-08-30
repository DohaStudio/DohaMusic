"""FFmpeg Working Preview geometry and secure temporary lifecycle tests."""

from __future__ import annotations

import io
import shutil
import struct
import subprocess
import wave
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from backend.audio.working_preview_renderer import (
    FfmpegWorkingCompositionPreviewRenderer,
    PreviewRenderClip,
    PreviewRenderError,
)


def test_ffmpeg_renders_wav_flac_mp3_offsets_gaps_and_overlap(tmp_path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg runtime is unavailable")
    wav_path = tmp_path / "source.wav"
    _tone_wav(wav_path, duration_frames=48_000)
    formats: dict[UUID, bytes] = {uuid4(): wav_path.read_bytes()}
    for suffix, codec in (("flac", "flac"), ("mp3", "libmp3lame")):
        output = tmp_path / f"source.{suffix}"
        completed = subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(wav_path),
                "-c:a",
                codec,
                str(output),
            ],
            check=False,
            shell=False,
        )
        assert completed.returncode == 0
        formats[uuid4()] = output.read_bytes()

    @contextmanager
    def open_artifact(artifact_id: UUID):
        payload = formats[artifact_id]
        yield len(payload), io.BytesIO(payload)

    clips = [
        PreviewRenderClip(
            clip_id=uuid4(),
            track_order=index,
            canonical_order=index,
            artifact_id=artifact_id,
            source_in_us=100_000,
            source_out_us=300_000,
            timeline_start_us=index * 300_000,
        )
        for index, artifact_id in enumerate(formats)
    ]
    # Cross-track overlap is allowed and deterministic.
    clips.append(
        PreviewRenderClip(
            clip_id=uuid4(),
            track_order=3,
            canonical_order=3,
            artifact_id=next(iter(formats)),
            source_in_us=100_000,
            source_out_us=300_000,
            timeline_start_us=300_000,
        )
    )
    temp_root = tmp_path / "runtime-owned"
    renderer = FfmpegWorkingCompositionPreviewRenderer(
        ffmpeg_executable=ffmpeg,
        temp_root=temp_root,
        open_artifact=open_artifact,
    )
    with renderer.render(clips, track_count=4) as rendered:
        assert rendered.duration_us == 800_000
        with wave.open(str(rendered.path), "rb") as output:
            assert output.getframerate() == 48_000
            assert output.getnchannels() == 2
            assert abs(output.getnframes() - 38_400) <= 1
            frames = output.readframes(output.getnframes())
        # First explicit gap [0.2s, 0.3s) is silence.
        gap = frames[9_600 * 4 : 14_400 * 4]
        assert max(abs(sample) for sample in struct.unpack(f"<{len(gap) // 2}h", gap)) <= 1
    assert list(temp_root.iterdir()) == []


def test_renderer_rejects_unbounded_or_pathless_manifest_before_subprocess(
    tmp_path: Path,
) -> None:
    called = False

    @contextmanager
    def open_artifact(_artifact_id: UUID):
        nonlocal called
        called = True
        yield 1, io.BytesIO(b"x")

    renderer = FfmpegWorkingCompositionPreviewRenderer(
        ffmpeg_executable="caller-controlled;command",
        temp_root=tmp_path,
        open_artifact=open_artifact,
    )
    with (
        pytest.raises(PreviewRenderError, match="WORKING_PREVIEW_GEOMETRY_INVALID"),
        renderer.render(
            [
                PreviewRenderClip(
                    clip_id=uuid4(),
                    track_order=0,
                    canonical_order=0,
                    artifact_id=uuid4(),
                    source_in_us=0,
                    source_out_us=1,
                    timeline_start_us=30 * 60 * 1_000_000,
                )
            ],
            track_count=1,
        ),
    ):
        pass
    assert called is False


def test_renderer_cancellation_terminates_process_and_cleans_temp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_id = uuid4()
    payload_path = tmp_path / "source.wav"
    _tone_wav(payload_path, duration_frames=4_800)
    payload = payload_path.read_bytes()

    @contextmanager
    def open_artifact(candidate: UUID):
        assert candidate == artifact_id
        yield len(payload), io.BytesIO(payload)

    class FakeProcess:
        returncode: int | None = None
        terminated = False

        def poll(self):
            return self.returncode

        def terminate(self):
            self.terminated = True
            self.returncode = 1

        def wait(self, timeout=None):
            return self.returncode

        def kill(self):
            self.returncode = 1

    process = FakeProcess()

    def fake_popen(command, **kwargs):
        assert isinstance(command, list)
        assert kwargs["shell"] is False
        return process

    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    temp_root = tmp_path / "cancel-runtime"
    renderer = FfmpegWorkingCompositionPreviewRenderer(
        ffmpeg_executable="ffmpeg",
        temp_root=temp_root,
        open_artifact=open_artifact,
    )
    with (
        pytest.raises(PreviewRenderError, match="WORKING_PREVIEW_CANCELLED"),
        renderer.render(
            [
                PreviewRenderClip(
                    clip_id=uuid4(),
                    track_order=0,
                    canonical_order=0,
                    artifact_id=artifact_id,
                    source_in_us=0,
                    source_out_us=50_000,
                    timeline_start_us=0,
                )
            ],
            track_count=1,
            cancel_requested=lambda: True,
        ),
    ):
        pass
    assert process.terminated is True
    assert list(temp_root.iterdir()) == []


def test_renderer_applies_pinned_clip_gain_with_deterministic_amplitude(
    tmp_path: Path,
) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg runtime is unavailable")
    artifact_id = uuid4()
    source = tmp_path / "gain-source.wav"
    _tone_wav(source, duration_frames=4_800)
    payload = source.read_bytes()

    @contextmanager
    def open_artifact(candidate: UUID):
        assert candidate == artifact_id
        yield len(payload), io.BytesIO(payload)

    renderer = FfmpegWorkingCompositionPreviewRenderer(
        ffmpeg_executable=ffmpeg,
        temp_root=tmp_path / "gain-runtime",
        open_artifact=open_artifact,
    )

    def peak(gain_db: Decimal) -> int:
        clip = PreviewRenderClip(
            clip_id=uuid4(),
            track_order=0,
            canonical_order=0,
            artifact_id=artifact_id,
            source_in_us=0,
            source_out_us=100_000,
            timeline_start_us=0,
            gain_db=gain_db,
        )
        with (
            renderer.render([clip], track_count=1) as rendered,
            wave.open(str(rendered.path), "rb") as output,
        ):
            frames = output.readframes(output.getnframes())
        return max(abs(sample) for sample in struct.unpack(f"<{len(frames) // 2}h", frames))

    unity = peak(Decimal("0.00"))
    attenuated = peak(Decimal("-6.02"))
    boosted = peak(Decimal("6.02"))
    assert attenuated / unity == pytest.approx(10 ** (-6.02 / 20), rel=0.03)
    assert boosted / unity == pytest.approx(10 ** (6.02 / 20), rel=0.03)


@pytest.mark.parametrize("gain_db", [Decimal("-24.01"), Decimal("24.01"), Decimal("NaN")])
def test_renderer_rejects_invalid_manifest_gain_before_opening_artifact(
    tmp_path: Path, gain_db: Decimal
) -> None:
    called = False

    @contextmanager
    def open_artifact(_artifact_id: UUID):
        nonlocal called
        called = True
        yield 1, io.BytesIO(b"x")

    renderer = FfmpegWorkingCompositionPreviewRenderer(
        ffmpeg_executable="ffmpeg",
        temp_root=tmp_path,
        open_artifact=open_artifact,
    )
    with (
        pytest.raises(PreviewRenderError, match="WORKING_PREVIEW_GEOMETRY_INVALID"),
        renderer.render(
            [
                PreviewRenderClip(
                    clip_id=uuid4(),
                    track_order=0,
                    canonical_order=0,
                    artifact_id=uuid4(),
                    source_in_us=0,
                    source_out_us=1,
                    timeline_start_us=0,
                    gain_db=gain_db,
                )
            ],
            track_count=1,
        ),
    ):
        pass
    assert called is False


def _tone_wav(path: Path, *, duration_frames: int) -> None:
    samples = bytearray()
    for frame in range(duration_frames):
        value = 8_000 if (frame // 100) % 2 == 0 else -8_000
        samples.extend(struct.pack("<hh", value, value))
    with wave.open(str(path), "wb") as output:
        output.setnchannels(2)
        output.setsampwidth(2)
        output.setframerate(48_000)
        output.writeframes(samples)
