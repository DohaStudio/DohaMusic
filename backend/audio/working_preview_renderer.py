"""Secure FFmpeg timeline renderer for immutable Working Preview manifests."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Protocol
from uuid import UUID

MAX_PREVIEW_TRACKS = 64
MAX_PREVIEW_CLIPS = 512
MAX_PREVIEW_DURATION_US = 30 * 60 * 1_000_000
MAX_PREVIEW_INPUT_BYTES = 128 * 1024 * 1024
MAX_PREVIEW_OUTPUT_BYTES = 384 * 1024 * 1024
PREVIEW_RENDER_TIMEOUT_SECONDS = 300
PREVIEW_SAMPLE_RATE = 48_000


class PreviewRenderError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class PreviewRenderClip:
    clip_id: UUID
    track_order: int
    canonical_order: int
    artifact_id: UUID
    source_in_us: int
    source_out_us: int
    timeline_start_us: int


@dataclass(frozen=True, slots=True)
class PreviewRenderedWav:
    path: Path
    duration_us: int
    size_bytes: int


ArtifactOpener = Callable[[UUID], AbstractContextManager[tuple[int, BinaryIO]]]


class WorkingCompositionPreviewRenderer(Protocol):
    def render(
        self,
        clips: Sequence[PreviewRenderClip],
        *,
        track_count: int,
        cancel_requested: Callable[[], bool] | None = None,
        open_artifact: ArtifactOpener | None = None,
    ) -> AbstractContextManager[PreviewRenderedWav]: ...


class FfmpegWorkingCompositionPreviewRenderer:
    def __init__(
        self,
        *,
        ffmpeg_executable: str,
        temp_root: Path,
        open_artifact: ArtifactOpener,
        timeout_seconds: int = PREVIEW_RENDER_TIMEOUT_SECONDS,
    ) -> None:
        self._ffmpeg = ffmpeg_executable
        self._temp_root = temp_root.resolve()
        self._open_artifact = open_artifact
        self._timeout = timeout_seconds

    @contextmanager
    def render(
        self,
        clips: Sequence[PreviewRenderClip],
        *,
        track_count: int,
        cancel_requested: Callable[[], bool] | None = None,
        open_artifact: ArtifactOpener | None = None,
    ) -> Iterator[PreviewRenderedWav]:
        ordered = _validate_manifest(clips, track_count=track_count)
        artifact_opener = open_artifact or self._open_artifact
        self._temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="working-preview-", dir=self._temp_root) as raw:
            root = Path(raw).resolve()
            inputs: list[Path] = []
            for index, clip in enumerate(ordered):
                target = root / f"input-{index:04d}.audio"
                with artifact_opener(clip.artifact_id) as (size_bytes, stream):
                    if not 0 < size_bytes <= MAX_PREVIEW_INPUT_BYTES:
                        raise PreviewRenderError("WORKING_PREVIEW_INPUT_SIZE_INVALID")
                    with target.open("xb") as output:
                        shutil.copyfileobj(stream, output, length=1024 * 1024)
                    if target.stat().st_size != size_bytes:
                        raise PreviewRenderError("WORKING_PREVIEW_INPUT_SIZE_MISMATCH")
                inputs.append(target)
            duration_us = max(
                item.timeline_start_us + item.source_out_us - item.source_in_us for item in ordered
            )
            output = root / "preview.wav"
            command = _ffmpeg_command(
                self._ffmpeg, inputs, ordered, output=output, duration_us=duration_us
            )
            process: subprocess.Popen[bytes] | None = None
            try:
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=False,
                )
                deadline = time.monotonic() + self._timeout
                while process.poll() is None:
                    if cancel_requested is not None and cancel_requested():
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait()
                        raise PreviewRenderError("WORKING_PREVIEW_CANCELLED")
                    if time.monotonic() >= deadline:
                        process.kill()
                        process.wait()
                        raise PreviewRenderError("WORKING_PREVIEW_RENDER_TIMEOUT")
                    time.sleep(0.05)
            except OSError:
                raise PreviewRenderError("WORKING_PREVIEW_RENDER_UNAVAILABLE") from None
            finally:
                if process is not None and process.poll() is None:
                    process.kill()
                    process.wait()
            if process is None or process.returncode != 0 or not output.is_file():
                raise PreviewRenderError("WORKING_PREVIEW_RENDER_FAILED")
            size_bytes = output.stat().st_size
            if not 0 < size_bytes <= MAX_PREVIEW_OUTPUT_BYTES:
                raise PreviewRenderError("WORKING_PREVIEW_OUTPUT_SIZE_INVALID")
            yield PreviewRenderedWav(output, duration_us, size_bytes)


def _validate_manifest(
    clips: Sequence[PreviewRenderClip], *, track_count: int
) -> tuple[PreviewRenderClip, ...]:
    if not 0 < track_count <= MAX_PREVIEW_TRACKS:
        raise PreviewRenderError("WORKING_PREVIEW_TRACK_LIMIT")
    if not 0 < len(clips) <= MAX_PREVIEW_CLIPS:
        raise PreviewRenderError("WORKING_PREVIEW_CLIP_LIMIT")
    ordered = tuple(
        sorted(
            clips,
            key=lambda item: (item.track_order, item.canonical_order, item.clip_id),
        )
    )
    if len({item.clip_id for item in ordered}) != len(ordered):
        raise PreviewRenderError("WORKING_PREVIEW_CLIP_DUPLICATE")
    for item in ordered:
        if (
            item.track_order < 0
            or item.canonical_order < 0
            or item.source_in_us < 0
            or item.source_out_us <= item.source_in_us
            or item.timeline_start_us < 0
            or item.timeline_start_us + item.source_out_us - item.source_in_us
            > MAX_PREVIEW_DURATION_US
        ):
            raise PreviewRenderError("WORKING_PREVIEW_GEOMETRY_INVALID")
    return ordered


def _seconds(microseconds: int) -> str:
    return f"{microseconds / 1_000_000:.6f}"


def _ffmpeg_command(
    executable: str,
    inputs: Sequence[Path],
    clips: Sequence[PreviewRenderClip],
    *,
    output: Path,
    duration_us: int,
) -> list[str]:
    command = [executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    for path in inputs:
        command.extend(["-i", str(path)])
    filters: list[str] = []
    labels: list[str] = []
    for index, clip in enumerate(clips):
        label = f"c{index}"
        delay_samples = (clip.timeline_start_us * PREVIEW_SAMPLE_RATE + 500_000) // 1_000_000
        filters.append(
            f"[{index}:a]atrim=start={_seconds(clip.source_in_us)}:end={_seconds(clip.source_out_us)},"
            f"asetpts=PTS-STARTPTS,aresample={PREVIEW_SAMPLE_RATE},aformat=sample_fmts=fltp:channel_layouts=stereo,"
            f"adelay={delay_samples}S:all=1[{label}]"
        )
        labels.append(f"[{label}]")
    filters.append(
        f"{''.join(labels)}amix=inputs={len(labels)}:duration=longest:normalize=0,"
        f"apad=whole_dur={_seconds(duration_us)},atrim=duration={_seconds(duration_us)}[out]"
    )
    command.extend(
        [
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[out]",
            "-c:a",
            "pcm_s16le",
            "-ar",
            str(PREVIEW_SAMPLE_RATE),
            "-ac",
            "2",
            str(output),
        ]
    )
    return command
