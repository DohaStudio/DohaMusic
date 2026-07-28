"""Run one offline Demucs vocal separation with objective resource metadata."""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import os
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def query_system_vram_mb() -> float | None:
    try:
        completed = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip().splitlines()[0])
    except (ValueError, IndexError):
        return None


class ResourceSampler:
    def __init__(self, psutil_module: Any) -> None:
        self._psutil = psutil_module
        self._process = psutil_module.Process()
        self._process.cpu_percent(interval=None)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.process_memory_peak_mb = 0.0
        self.system_memory_peak_mb = 0.0
        self.process_cpu_percent_peak = 0.0
        self.peak_nvidia_smi_mb: float | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            self.process_memory_peak_mb = max(
                self.process_memory_peak_mb,
                self._process.memory_info().rss / 1024 / 1024,
            )
            self.system_memory_peak_mb = max(
                self.system_memory_peak_mb,
                self._psutil.virtual_memory().used / 1024 / 1024,
            )
            self.process_cpu_percent_peak = max(
                self.process_cpu_percent_peak,
                self._process.cpu_percent(interval=None),
            )
            system_vram = query_system_vram_mb()
            if system_vram is not None:
                self.peak_nvidia_smi_mb = max(
                    self.peak_nvidia_smi_mb or 0.0,
                    system_vram,
                )
            self._stop.wait(0.2)


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audio_metrics(
    path: Path, soundfile_module: Any, numpy_module: Any
) -> dict[str, Any]:
    audio, sample_rate = soundfile_module.read(path, always_2d=True, dtype="float32")
    absolute = numpy_module.abs(audio)
    rms = float(numpy_module.sqrt(numpy_module.mean(numpy_module.square(audio))))
    return {
        "file": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": hash_file(path),
        "sample_rate": int(sample_rate),
        "channels": int(audio.shape[1]),
        "duration_seconds": round(float(audio.shape[0] / sample_rate), 3),
        "peak_amplitude": round(float(numpy_module.max(absolute)), 6),
        "rms_amplitude": round(rms, 6),
        "near_silence_ratio": round(float(numpy_module.mean(absolute < 1e-4)), 6),
        "clipped_sample_ratio": round(float(numpy_module.mean(absolute >= 0.999)), 6),
        "non_silent": bool(rms > 1e-4),
    }


def save_48k_stereo(
    audio: Any,
    source_rate: int,
    output_path: Path,
    torchaudio_module: Any,
    soundfile_module: Any,
) -> None:
    if audio.shape[0] == 1:
        audio = audio.repeat(2, 1)
    elif audio.shape[0] != 2:
        raise ValueError("Demucs output must be mono or stereo")
    if source_rate != 48_000:
        audio = torchaudio_module.functional.resample(audio, source_rate, 48_000)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    soundfile_module.write(
        output_path,
        audio.detach().cpu().numpy().T,
        48_000,
        subtype="FLOAT",
    )


def run(args: argparse.Namespace) -> tuple[int, dict[str, Any]]:
    os.environ["HF_HOME"] = str(args.model_cache_path.resolve())
    os.environ["HF_HUB_OFFLINE"] = "1"
    import numpy
    import psutil
    import soundfile
    import torch
    import torchaudio
    from demucs.api import LoadAudioError, LoadModelError, Separator

    metadata: dict[str, Any] = {
        "experiment_id": args.experiment_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "provider": "demucs",
        "model_name": args.model_name,
        "model_version": args.model_version,
        "device": args.device,
        "segment_seconds": args.segment_seconds,
        "shifts": args.shifts,
        "overlap": args.overlap,
        "input_size_bytes": args.input_path.stat().st_size,
        "input_sha256": hash_file(args.input_path),
    }
    try:
        soundfile.info(args.input_path)
    except soundfile.LibsndfileError as exc:
        metadata.update(
            success=False,
            error_code="STEM_AUDIO_DECODE_FAILED",
            error_message=type(exc).__name__,
        )
        return 3, metadata
    sampler = ResourceSampler(psutil)
    process = psutil.Process()
    cpu_before = process.cpu_times()
    sampler.start()
    torch.cuda.empty_cache()
    torch.cuda.reset_peak_memory_stats()
    stage = "model_load"
    separator = None
    try:
        load_started = time.perf_counter()
        separator = Separator(
            model=args.model_name,
            device=args.device,
            shifts=args.shifts,
            overlap=args.overlap,
            split=True,
            segment=args.segment_seconds,
            jobs=0,
            progress=False,
        )
        metadata["load_time_seconds"] = round(time.perf_counter() - load_started, 3)
        stage = "inference"
        inference_started = time.perf_counter()
        _, sources = separator.separate_audio_file(args.input_path)
        metadata["separation_time_seconds"] = round(
            time.perf_counter() - inference_started, 3
        )
        vocals = sources["vocals"]
        instrumental = torch.stack(
            [source for name, source in sources.items() if name != "vocals"]
        ).sum(dim=0)
        save_48k_stereo(
            vocals,
            separator.samplerate,
            args.vocals_output,
            torchaudio,
            soundfile,
        )
        save_48k_stereo(
            instrumental,
            separator.samplerate,
            args.instrumental_output,
            torchaudio,
            soundfile,
        )
        vocals_metrics = audio_metrics(args.vocals_output, soundfile, numpy)
        instrumental_metrics = audio_metrics(args.instrumental_output, soundfile, numpy)
        if (
            vocals_metrics["duration_seconds"]
            != instrumental_metrics["duration_seconds"]
        ):
            raise ValueError("Stem durations do not match")
        metadata.update(
            success=True,
            duration_actual=vocals_metrics["duration_seconds"],
            vocals=vocals_metrics,
            instrumental=instrumental_metrics,
        )
        return 0, metadata
    except torch.cuda.OutOfMemoryError as exc:
        metadata.update(
            success=False,
            error_code="STEM_OUT_OF_MEMORY",
            error_message=type(exc).__name__,
        )
        return 4, metadata
    except LoadAudioError as exc:
        metadata.update(
            success=False,
            error_code="STEM_AUDIO_DECODE_FAILED",
            error_message=type(exc).__name__,
        )
        return 3, metadata
    except LoadModelError as exc:
        metadata.update(
            success=False,
            error_code="STEM_MODEL_LOAD_FAILED",
            error_message=type(exc).__name__,
        )
        return 3, metadata
    except Exception as exc:
        metadata.update(
            success=False,
            error_code=(
                "STEM_MODEL_LOAD_FAILED"
                if stage == "model_load"
                else "STEM_SEPARATION_FAILED"
            ),
            error_message=type(exc).__name__,
        )
        return 3, metadata
    finally:
        sampler.stop()
        cpu_after = process.cpu_times()
        metadata.update(
            peak_torch_allocated_mb=round(
                torch.cuda.max_memory_allocated() / 1024 / 1024, 2
            ),
            peak_torch_reserved_mb=round(
                torch.cuda.max_memory_reserved() / 1024 / 1024, 2
            ),
            peak_nvidia_smi_mb=sampler.peak_nvidia_smi_mb,
            process_memory_peak_mb=round(sampler.process_memory_peak_mb, 2),
            system_memory_peak_mb=round(sampler.system_memory_peak_mb, 2),
            process_cpu_percent_peak=round(sampler.process_cpu_percent_peak, 2),
            process_cpu_time_seconds=round(
                (cpu_after.user + cpu_after.system)
                - (cpu_before.user + cpu_before.system),
                3,
            ),
        )
        del separator
        gc.collect()
        torch.cuda.empty_cache()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-path", type=Path, required=True)
    parser.add_argument("--vocals-output", type=Path, required=True)
    parser.add_argument("--instrumental-output", type=Path, required=True)
    parser.add_argument("--metadata-path", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--model-cache-path", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--device", required=True)
    parser.add_argument("--segment-seconds", type=float, required=True)
    parser.add_argument("--shifts", type=int, required=True)
    parser.add_argument("--overlap", type=float, required=True)
    parser.add_argument("--experiment-id", default="backend-stem-job")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    args.work_dir.mkdir(parents=True, exist_ok=True)
    try:
        if not args.input_path.is_file():
            raise FileNotFoundError("Stem input does not exist")
        if not args.model_cache_path.is_dir():
            raise FileNotFoundError("Demucs model cache does not exist")
        return_code, metadata = run(args)
    except (OSError, ValueError, TypeError) as exc:
        return_code = 2
        metadata = {
            "success": False,
            "error_code": "STEM_PROVIDER_NOT_CONFIGURED",
            "error_message": type(exc).__name__,
        }
    args.metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
