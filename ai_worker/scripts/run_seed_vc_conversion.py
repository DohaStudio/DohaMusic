"""Execute pinned Seed-VC CLI and emit stable JSON metadata.

This script runs only inside the isolated Seed-VC environment. It intentionally
keeps model-specific imports out of the FastAPI process.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import threading
import time
import wave
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--source-path", type=Path, required=True)
    parser.add_argument("--reference-path", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, required=True)
    parser.add_argument("--metadata-path", type=Path, required=True)
    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--config-path", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--model-version", required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--diffusion-steps", type=int, default=30)
    return parser.parse_args()


def gpu_memory_mb() -> float | None:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        values = [float(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        return sum(values) if values else 0.0
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None


def audio_metrics(path: Path) -> dict[str, object]:
    import numpy as np
    import soundfile as sf

    audio, sample_rate = sf.read(path, always_2d=True, dtype="float32")
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
    return {
        "sample_rate": int(sample_rate),
        "channels": int(audio.shape[1]),
        "output_duration_seconds": float(len(audio) / sample_rate),
        "output_size_bytes": path.stat().st_size,
        "peak_amplitude": peak,
        "rms": rms,
        "is_silent": rms < 1e-4,
        "is_clipping": peak >= 0.999,
    }


def normalize_output(source: Path, destination: Path) -> None:
    import torchaudio

    audio, sample_rate = torchaudio.load(str(source))
    if sample_rate != 48_000:
        audio = torchaudio.functional.resample(audio, sample_rate, 48_000)
    if audio.shape[0] == 1:
        audio = audio.repeat(2, 1)
    elif audio.shape[0] > 2:
        audio = audio[:2]
    destination.parent.mkdir(parents=True, exist_ok=True)
    torchaudio.save(
        str(destination),
        audio.cpu(),
        48_000,
        encoding="PCM_S",
        bits_per_sample=16,
    )


def main() -> int:
    args = parse_args()
    for name in (
        "project_root",
        "source_path",
        "reference_path",
        "output_path",
        "metadata_path",
        "checkpoint_path",
        "config_path",
    ):
        setattr(args, name, getattr(args, name).resolve())
    started_at = time.perf_counter()
    args.metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = args.output_path.parent / f".{args.output_path.stem}-seed-vc"
    peak_vram: list[float] = []
    peak_process_memory: list[float] = []
    peak_cpu_percent: list[float] = []
    stop = threading.Event()

    def monitor() -> None:
        try:
            import psutil

            process = psutil.Process()
            process.cpu_percent(interval=None)
        except (ImportError, OSError):
            process = None
        while not stop.wait(0.1):
            value = gpu_memory_mb()
            if value is not None:
                peak_vram.append(value)
            if process is not None:
                try:
                    processes = [process, *process.children(recursive=True)]
                    peak_process_memory.append(
                        sum(item.memory_info().rss for item in processes) / 1024 / 1024
                    )
                    peak_cpu_percent.append(
                        sum(item.cpu_percent(interval=None) for item in processes)
                    )
                except (psutil.Error, OSError):
                    pass

    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    payload: dict[str, object] = {
        "success": False,
        "provider": "seed_vc",
        "model_name": args.model_name,
        "model_version": args.model_version,
        "device": args.device,
        "diffusion_steps": args.diffusion_steps,
    }
    try:
        if args.device == "cuda":
            import torch

            if not torch.cuda.is_available():
                raise RuntimeError("CUDA is not available")
        command = [
            sys.executable,
            str(args.project_root / "inference.py"),
            "--source",
            str(args.source_path),
            "--target",
            str(args.reference_path),
            "--output",
            str(temporary_output),
            "--diffusion-steps",
            str(args.diffusion_steps),
            "--length-adjust",
            "1.0",
            "--inference-cfg-rate",
            "0.7",
            "--f0-condition",
            "True",
            "--auto-f0-adjust",
            "False",
            "--semi-tone-shift",
            "0",
            "--checkpoint",
            str(args.checkpoint_path),
            "--config",
            str(args.config_path),
            "--fp16",
            "True",
        ]
        completed = subprocess.run(
            command,
            cwd=args.project_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.lower()
            if "out of memory" in stderr:
                code = "VOICE_OUT_OF_MEMORY"
            elif "no module named" in stderr:
                code = "VOICE_DEPENDENCY_NOT_INSTALLED"
            elif "state_dict" in stderr or "checkpoint" in stderr:
                code = "VOICE_MODEL_LOAD_FAILED"
            else:
                code = "VOICE_CONVERSION_FAILED"
            raise RuntimeError(f"{code}: Seed-VC inference failed")
        candidates = sorted(temporary_output.glob("*.wav"), key=lambda path: path.stat().st_mtime)
        if not candidates:
            raise RuntimeError("VOICE_OUTPUT_NOT_CREATED: Seed-VC produced no WAV")
        normalize_output(candidates[-1], args.output_path)
        metrics = audio_metrics(args.output_path)
        payload.update(metrics)
        payload.update(
            {
                "success": True,
                "conversion_time_seconds": time.perf_counter() - started_at,
                "input_duration_seconds": wav_duration(args.source_path),
                "reference_duration_seconds": wav_duration(args.reference_path),
                "peak_vram_mb": max(peak_vram) if peak_vram else None,
                "peak_process_memory_mb": max(peak_process_memory) if peak_process_memory else None,
                "peak_cpu_percent": max(peak_cpu_percent) if peak_cpu_percent else None,
            }
        )
        return 0
    except Exception as exc:  # noqa: BLE001 - Seed-VC 경계의 예외를 안전한 오류로 변환한다.
        message = str(exc)
        code = (
            message.split(":", 1)[0] if message.startswith("VOICE_") else "VOICE_CONVERSION_FAILED"
        )
        payload.update(
            {
                "error_code": code,
                "error_message": "Seed-VC 실행에 실패했습니다. 상세 내용은 로컬 로그를 확인하세요.",
                "conversion_time_seconds": time.perf_counter() - started_at,
                "peak_vram_mb": max(peak_vram) if peak_vram else None,
                "peak_process_memory_mb": max(peak_process_memory) if peak_process_memory else None,
                "peak_cpu_percent": max(peak_cpu_percent) if peak_cpu_percent else None,
            }
        )
        return 1
    finally:
        stop.set()
        monitor_thread.join(timeout=2)
        args.metadata_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(payload, ensure_ascii=False))
        if temporary_output.exists():
            shutil.rmtree(temporary_output, ignore_errors=True)


def wav_duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as audio:
            return audio.getnframes() / audio.getframerate()
    except wave.Error:
        import soundfile as sf

        return float(sf.info(path).duration)


if __name__ == "__main__":
    raise SystemExit(main())
