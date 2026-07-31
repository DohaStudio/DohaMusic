"""Run one ACE-Step 1.5 smoke test without the Backend API.

This script must be executed with the isolated official ACE-Step environment.
It writes generated audio, metadata, and a runtime log below the requested
output directory. It never downloads a model implicitly: checkpoint and
runtime locations must be configured explicitly through environment variables.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXIT_CONFIGURATION = 2
EXIT_MODEL_LOAD = 3
EXIT_INFERENCE = 4
EXIT_OUTPUT = 5


@dataclass(frozen=True, slots=True)
class RuntimeSettings:
    project_root: Path
    checkpoints_dir: Path
    model_variant: str
    model_version: str
    device: str
    quantization: str | None
    cpu_offload: bool
    dit_cpu_offload: bool


@dataclass(frozen=True, slots=True)
class SmokeRequest:
    experiment_case: str
    prompt: str
    lyrics: str | None
    instrumental: bool
    duration_seconds: int
    seed: int | None
    vocal_language: str


class ResourceSampler:
    """Sample process RSS and system GPU usage while a model operation runs."""

    def __init__(self, psutil_module: Any) -> None:
        self._process = psutil_module.Process()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.peak_process_memory_mb = 0.0
        self.peak_system_vram_mb: float | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        while not self._stop.is_set():
            rss_mb = self._process.memory_info().rss / 1024 / 1024
            self.peak_process_memory_mb = max(self.peak_process_memory_mb, rss_mb)
            system_vram = query_system_vram_mb()
            if system_vram is not None:
                current = self.peak_system_vram_mb or 0.0
                self.peak_system_vram_mb = max(current, system_vram)
            self._stop.wait(0.25)


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value: {value}")


def optional_env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def required_env(name: str) -> str:
    value = optional_env(name)
    if value is None:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def load_settings() -> RuntimeSettings:
    settings = RuntimeSettings(
        project_root=Path(required_env("DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT")).resolve(),
        checkpoints_dir=Path(
            required_env("DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH")
        ).resolve(),
        model_variant=required_env("DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT"),
        model_version=required_env("DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION"),
        device=required_env("DOHAMUSIC_AI_ACE_STEP_DEVICE"),
        quantization=optional_env("DOHAMUSIC_AI_ACE_STEP_QUANTIZATION"),
        cpu_offload=parse_bool(required_env("DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD")),
        dit_cpu_offload=parse_bool(
            required_env("DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD")
        ),
    )
    if not settings.project_root.is_dir():
        raise ValueError("Configured ACE-Step project root does not exist")
    if not settings.checkpoints_dir.is_dir():
        raise ValueError("Configured ACE-Step checkpoint directory does not exist")
    return settings


def load_request(path: Path) -> SmokeRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    request = SmokeRequest(
        experiment_case=str(payload["experiment_case"]),
        prompt=str(payload["prompt"]),
        lyrics=payload.get("lyrics"),
        instrumental=bool(payload["instrumental"]),
        duration_seconds=int(payload["duration_seconds"]),
        seed=int(payload["seed"]) if payload.get("seed") is not None else None,
        vocal_language=str(payload["vocal_language"]),
    )
    if not request.prompt.strip():
        raise ValueError("Prompt must not be empty")
    if not 10 <= request.duration_seconds <= 600:
        raise ValueError("ACE-Step duration must be between 10 and 600 seconds")
    return request


def query_system_vram_mb() -> float | None:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.used",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            check=True,
            text=True,
            timeout=5,
        )
        return float(result.stdout.strip().splitlines()[0])
    except (OSError, subprocess.SubprocessError, ValueError, IndexError):
        return None


def output_audio_path(result: Any) -> Path:
    if not result.success:
        raise RuntimeError(result.error or result.status_message)
    if not result.audios:
        raise FileNotFoundError("ACE-Step returned no audio entries")
    path = Path(result.audios[0].get("path", ""))
    if not path.is_file() or path.stat().st_size == 0:
        raise FileNotFoundError("ACE-Step output audio was not created")
    return path.resolve()


def configure_logs(output_dir: Path) -> None:
    from loguru import logger

    def safe_log(record: dict[str, Any]) -> bool:
        return not record["name"].endswith("conditioning_text")

    logger.remove()
    logger.add(sys.stderr, level="INFO", filter=safe_log)
    logger.add(
        output_dir / "runtime.log",
        level="INFO",
        encoding="utf-8",
        filter=safe_log,
    )


def write_metadata(path: Path, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def execute(
    settings: RuntimeSettings,
    request: SmokeRequest,
    output_dir: Path,
    metadata_path: Path,
) -> int:
    import psutil
    import soundfile
    import torch
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(settings.checkpoints_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    configure_logs(output_dir)
    sampler = ResourceSampler(psutil)
    sampler.start()
    total_started = time.perf_counter()
    baseline_vram = query_system_vram_mb()
    metadata: dict[str, Any] = {
        "experiment_id": output_dir.name,
        "created_at": datetime.now(UTC).isoformat(),
        "success": False,
        "request": asdict(request),
        "model_name": "ACE-Step 1.5",
        "model_version": settings.model_version,
        "model_variant": settings.model_variant,
        "lm_model": None,
        "device": settings.device,
        "quantization": settings.quantization,
        "cpu_offload": settings.cpu_offload,
        "dit_cpu_offload": settings.dit_cpu_offload,
        "batch_size": 1,
        "inference_steps": 8,
        "vram_before_load_mb": baseline_vram,
    }
    handler = None
    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        handler = AceStepHandler()
        load_started = time.perf_counter()
        status, loaded = handler.initialize_service(
            project_root=str(settings.project_root),
            config_path=settings.model_variant,
            device=settings.device,
            compile_model=False,
            offload_to_cpu=settings.cpu_offload,
            offload_dit_to_cpu=settings.dit_cpu_offload,
            quantization=settings.quantization,
        )
        metadata["load_time_seconds"] = round(time.perf_counter() - load_started, 3)
        metadata["vram_after_load_mb"] = query_system_vram_mb()
        if not loaded:
            metadata.update(error_code="AI_MODEL_LOAD_FAILED", error_message=status)
            return EXIT_MODEL_LOAD

        params = GenerationParams(
            task_type="text2music",
            thinking=False,
            use_cot_metas=False,
            use_cot_caption=False,
            use_cot_language=False,
            caption=request.prompt,
            lyrics=request.lyrics or "[Instrumental]",
            instrumental=request.instrumental,
            vocal_language=request.vocal_language,
            duration=request.duration_seconds,
            inference_steps=8,
            guidance_scale=1.0,
            seed=request.seed if request.seed is not None else -1,
        )
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=request.seed is None,
            seeds=[request.seed] if request.seed is not None else None,
            audio_format="wav",
        )
        torch.cuda.reset_peak_memory_stats()
        inference_started = time.perf_counter()
        result = generate_music(
            handler,
            None,
            params=params,
            config=config,
            save_dir=str(output_dir),
        )
        metadata["inference_time_seconds"] = round(
            time.perf_counter() - inference_started,
            3,
        )
        if not result.success:
            metadata.update(
                error_code="AI_INFERENCE_FAILED",
                error_message=result.error or result.status_message,
            )
            return EXIT_INFERENCE

        audio_path = output_audio_path(result)
        audio_params = result.audios[0].get("params", {})
        actual_seed_value = audio_params.get("seed", request.seed)
        actual_seed = int(actual_seed_value) if actual_seed_value is not None else None
        audio_info = soundfile.info(str(audio_path))
        metadata.update(
            success=True,
            seed=actual_seed,
            duration_requested=request.duration_seconds,
            duration_actual=round(float(audio_info.duration), 3),
            output_format=audio_path.suffix.lower().lstrip("."),
            output_path=audio_path.relative_to(output_dir.resolve()).as_posix(),
            output_file_size_bytes=audio_path.stat().st_size,
            sample_rate=audio_info.samplerate,
            channels=audio_info.channels,
            torch_peak_allocated_vram_mb=round(
                torch.cuda.max_memory_allocated() / 1024 / 1024,
                2,
            ),
            torch_peak_reserved_vram_mb=round(
                torch.cuda.max_memory_reserved() / 1024 / 1024,
                2,
            ),
        )
        return 0
    except torch.cuda.OutOfMemoryError as exc:
        metadata.update(error_code="AI_OUT_OF_MEMORY", error_message=str(exc))
        return EXIT_INFERENCE
    except FileNotFoundError as exc:
        metadata.update(error_code="AI_OUTPUT_NOT_CREATED", error_message=str(exc))
        return EXIT_OUTPUT
    except soundfile.LibsndfileError as exc:
        metadata.update(error_code="AI_AUDIO_DECODE_FAILED", error_message=str(exc))
        return EXIT_OUTPUT
    except Exception as exc:  # noqa: BLE001 - 외부 추론 예외를 smoke 결과로 변환한다.
        metadata.update(error_code="AI_INFERENCE_FAILED", error_message=str(exc))
        return EXIT_INFERENCE
    finally:
        metadata["total_time_seconds"] = round(time.perf_counter() - total_started, 3)
        sampler.stop()
        metadata["peak_process_memory_mb"] = round(
            sampler.peak_process_memory_mb,
            2,
        )
        metadata["nvidia_smi_peak_used_vram_mb"] = sampler.peak_system_vram_mb
        del handler
        gc.collect()
        torch.cuda.empty_cache()
        metadata["vram_after_release_mb"] = query_system_vram_mb()
        write_metadata(metadata_path, metadata)
        print(json.dumps(metadata, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-json", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--metadata-path", type=Path)
    args = parser.parse_args()
    metadata_path = args.metadata_path or args.output_dir / "metadata.json"
    try:
        settings = load_settings()
        request = load_request(args.request_json)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_code": "AI_PROVIDER_NOT_CONFIGURED",
                    "error_message": str(exc),
                }
            )
        )
        return EXIT_CONFIGURATION
    try:
        return execute(
            settings, request, args.output_dir.resolve(), metadata_path.resolve()
        )
    except ImportError as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_code": "AI_DEPENDENCY_NOT_INSTALLED",
                    "error_message": str(exc),
                }
            )
        )
        return EXIT_CONFIGURATION


if __name__ == "__main__":
    raise SystemExit(main())
