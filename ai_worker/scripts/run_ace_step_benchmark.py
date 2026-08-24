"""Run multiple ACE-Step requests in one isolated, model-resident process."""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ai_worker.benchmarking import aggregate_runs, hash_file, hash_text


class ResourceSampler:
    """Sample process and system resources for one load or inference span."""

    def __init__(self, psutil_module: Any) -> None:
        self._psutil = psutil_module
        self._process = psutil_module.Process()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self.process_memory_peak_mb = 0.0
        self.system_memory_peak_mb = 0.0
        self.peak_nvidia_smi_mb: float | None = None

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2)

    def _run(self) -> None:
        from ai_worker.scripts.run_ace_step_smoke_test import query_system_vram_mb

        while not self._stop.is_set():
            self.process_memory_peak_mb = max(
                self.process_memory_peak_mb,
                self._process.memory_info().rss / 1024 / 1024,
            )
            self.system_memory_peak_mb = max(
                self.system_memory_peak_mb,
                self._psutil.virtual_memory().used / 1024 / 1024,
            )
            system_vram = query_system_vram_mb()
            if system_vram is not None:
                self.peak_nvidia_smi_mb = max(
                    self.peak_nvidia_smi_mb or 0.0,
                    system_vram,
                )
            self._stop.wait(0.25)


def load_suite(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("experiment_id") or not payload.get("runs"):
        raise ValueError("Benchmark suite requires experiment_id and runs")
    request = payload.get("request", {})
    prompt = str(request.get("prompt", "")).strip()
    if not prompt:
        raise ValueError("Benchmark prompt must not be empty")
    duration = int(request.get("duration_seconds", 0))
    if not 10 <= duration <= 600:
        raise ValueError("Benchmark duration must be between 10 and 600 seconds")
    for run in payload["runs"]:
        if not run.get("run_id") or run.get("seed") is None:
            raise ValueError("Every benchmark run requires run_id and seed")
    return payload


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def bool_env(name: str) -> bool:
    value = required_env(name).lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"Unsupported boolean value for {name}")


def configure_logs(output_dir: Path) -> None:
    from loguru import logger

    def safe_log(record: dict[str, Any]) -> bool:
        message = str(record.get("message", ""))
        return not (record["name"].endswith("conditioning_text") or "conditioning_text" in message)

    logger.remove()
    logger.add(sys.stderr, level="INFO", filter=safe_log)
    logger.add(
        output_dir / "runtime.log",
        level="INFO",
        encoding="utf-8",
        filter=safe_log,
    )


def audio_metrics(path: Path, soundfile_module: Any, numpy_module: Any) -> dict[str, Any]:
    audio, sample_rate = soundfile_module.read(path, always_2d=True)
    absolute = numpy_module.abs(audio)
    peak = float(numpy_module.max(absolute)) if audio.size else 0.0
    rms = float(numpy_module.sqrt(numpy_module.mean(numpy_module.square(audio))))
    return {
        "sample_rate": int(sample_rate),
        "channels": int(audio.shape[1]),
        "duration_actual": round(float(audio.shape[0] / sample_rate), 3),
        "peak_amplitude": round(peak, 6),
        "rms_amplitude": round(rms, 6),
        "near_silence_ratio": round(float(numpy_module.mean(absolute < 1e-4)), 6),
        "clipped_sample_ratio": round(float(numpy_module.mean(absolute >= 0.999)), 6),
        "non_silent": bool(rms > 1e-4),
    }


def initialize_handlers(psutil_module: Any, torch_module: Any) -> tuple[Any, Any, dict[str, Any]]:
    from acestep.handler import AceStepHandler

    from ai_worker.scripts.run_ace_step_smoke_test import query_system_vram_mb

    project_root = Path(required_env("DOHAMUSIC_AI_ACE_STEP_PROJECT_ROOT")).resolve()
    checkpoints = Path(required_env("DOHAMUSIC_AI_ACE_STEP_CHECKPOINT_PATH")).resolve()
    variant = required_env("DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT")
    if not project_root.is_dir() or not checkpoints.is_dir():
        raise FileNotFoundError("Configured ACE-Step project or checkpoint path is missing")
    if not (checkpoints / variant).is_dir():
        raise FileNotFoundError("Configured ACE-Step model variant is missing")

    os.environ["ACESTEP_CHECKPOINTS_DIR"] = str(checkpoints)
    sampler = ResourceSampler(psutil_module)
    sampler.start()
    try:
        torch_module.cuda.empty_cache()
        load_started = time.perf_counter()
        handler = AceStepHandler()
        status, loaded = handler.initialize_service(
            project_root=str(project_root),
            config_path=variant,
            device=required_env("DOHAMUSIC_AI_ACE_STEP_DEVICE"),
            compile_model=False,
            offload_to_cpu=bool_env("DOHAMUSIC_AI_ACE_STEP_CPU_OFFLOAD"),
            offload_dit_to_cpu=bool_env("DOHAMUSIC_AI_ACE_STEP_DIT_CPU_OFFLOAD"),
            quantization=os.getenv("DOHAMUSIC_AI_ACE_STEP_QUANTIZATION") or None,
        )
        if not loaded:
            raise RuntimeError(f"ACE-Step DiT load failed: {status}")

        llm_handler = None
        lm_model = os.getenv("DOHAMUSIC_AI_ACE_STEP_LM_MODEL", "").strip() or None
        lm_backend = os.getenv("DOHAMUSIC_AI_ACE_STEP_LM_BACKEND", "pt").strip()
        if lm_model:
            if not (checkpoints / lm_model).is_dir():
                raise FileNotFoundError("Configured ACE-Step LM model is missing")
            from acestep.llm_inference import LLMHandler

            llm_handler = LLMHandler()
            lm_status, lm_loaded = llm_handler.initialize(
                checkpoint_dir=str(checkpoints),
                lm_model_path=lm_model,
                backend=lm_backend,
                device=required_env("DOHAMUSIC_AI_ACE_STEP_DEVICE"),
                offload_to_cpu=True,
            )
            if not lm_loaded:
                raise RuntimeError(f"ACE-Step LM load failed: {lm_status}")
    finally:
        sampler.stop()
    load_metadata = {
        "load_time_seconds": round(time.perf_counter() - load_started, 3),
        "lm_model": lm_model,
        "lm_backend": lm_backend if lm_model else None,
        "vram_after_load_mb": query_system_vram_mb(),
        "load_peak_nvidia_smi_mb": sampler.peak_nvidia_smi_mb,
        "load_process_memory_peak_mb": round(sampler.process_memory_peak_mb, 2),
        "load_system_memory_peak_mb": round(sampler.system_memory_peak_mb, 2),
    }
    return handler, llm_handler, load_metadata


def run_one(
    handler: Any,
    llm_handler: Any,
    suite_request: dict[str, Any],
    run: dict[str, Any],
    output_dir: Path,
    psutil_module: Any,
    soundfile_module: Any,
    numpy_module: Any,
    torch_module: Any,
) -> dict[str, Any]:
    from acestep.inference import GenerationConfig, GenerationParams, generate_music

    from ai_worker.scripts.run_ace_step_smoke_test import query_system_vram_mb

    run_dir = output_dir / str(run["run_id"])
    run_dir.mkdir(parents=True, exist_ok=True)
    seed = int(run["seed"])
    process = psutil_module.Process()
    torch_module.cuda.reset_peak_memory_stats()
    vram_before = query_system_vram_mb()
    allocated_before = torch_module.cuda.memory_allocated() / 1024 / 1024
    reserved_before = torch_module.cuda.memory_reserved() / 1024 / 1024
    process_memory_before = process.memory_info().rss / 1024 / 1024
    system_memory_before = psutil_module.virtual_memory().used / 1024 / 1024
    started_at = time.perf_counter()
    try:
        thinking = llm_handler is not None
        params = GenerationParams(
            task_type="text2music",
            thinking=thinking,
            use_cot_metas=thinking,
            use_cot_caption=thinking,
            use_cot_language=thinking,
            use_cot_lyrics=False,
            caption=str(suite_request["prompt"]),
            lyrics=suite_request.get("lyrics") or "[Instrumental]",
            instrumental=bool(suite_request.get("instrumental", False)),
            vocal_language=str(suite_request.get("vocal_language", "unknown")),
            duration=int(suite_request["duration_seconds"]),
            inference_steps=8,
            guidance_scale=1.0,
            seed=seed,
        )
        config = GenerationConfig(
            batch_size=1,
            use_random_seed=False,
            seeds=[seed],
            audio_format="wav",
        )
        inference_started = time.perf_counter()
        result = generate_music(
            handler,
            llm_handler,
            params=params,
            config=config,
            save_dir=str(run_dir),
        )
        inference_time = time.perf_counter() - inference_started
        if not result.success or not result.audios:
            raise RuntimeError(result.error or result.status_message)
        audio_path = Path(result.audios[0]["path"]).resolve()
        if not audio_path.is_file() or audio_path.stat().st_size == 0:
            raise FileNotFoundError("ACE-Step output was not created")
        actual_seed = int(result.audios[0].get("params", {}).get("seed", seed))
        metrics = audio_metrics(audio_path, soundfile_module, numpy_module)
        return {
            "run_id": run["run_id"],
            "success": True,
            "error_code": None,
            "error_message": None,
            "seed": actual_seed,
            "duration_requested": int(suite_request["duration_seconds"]),
            **metrics,
            "inference_time_seconds": round(inference_time, 3),
            "total_time_seconds": round(time.perf_counter() - started_at, 3),
            "peak_torch_allocated_mb": round(
                torch_module.cuda.max_memory_allocated() / 1024 / 1024, 2
            ),
            "peak_torch_reserved_mb": round(
                torch_module.cuda.max_memory_reserved() / 1024 / 1024, 2
            ),
            "torch_allocated_before_mb": round(allocated_before, 2),
            "torch_reserved_before_mb": round(reserved_before, 2),
            "nvidia_smi_before_mb": vram_before,
            "process_memory_before_mb": round(process_memory_before, 2),
            "system_memory_before_mb": round(system_memory_before, 2),
            "output_file": audio_path.relative_to(output_dir).as_posix(),
            "output_size": audio_path.stat().st_size,
            "output_hash": hash_file(audio_path),
        }
    except torch_module.cuda.OutOfMemoryError as exc:
        return {
            "run_id": run["run_id"],
            "success": False,
            "error_code": "AI_OUT_OF_MEMORY",
            "error_message": type(exc).__name__,
            "seed": seed,
        }
    except Exception as exc:  # noqa: BLE001 - 모델 런타임 예외를 벤치마크 결과로 격리한다.
        return {
            "run_id": run["run_id"],
            "success": False,
            "error_code": "AI_INFERENCE_FAILED",
            "error_message": type(exc).__name__,
            "seed": seed,
        }


def enrich_resources(
    result: dict[str, Any],
    sampler: ResourceSampler,
    psutil_module: Any,
    torch_module: Any,
) -> None:
    """Attach before/peak/after resource measurements to a run result."""

    result.update(
        peak_nvidia_smi_mb=sampler.peak_nvidia_smi_mb,
        process_memory_peak_mb=round(sampler.process_memory_peak_mb, 2),
        system_memory_peak_mb=round(sampler.system_memory_peak_mb, 2),
        process_memory_after_mb=round(psutil_module.Process().memory_info().rss / 1024 / 1024, 2),
        system_memory_after_mb=round(psutil_module.virtual_memory().used / 1024 / 1024, 2),
        torch_allocated_after_mb=round(torch_module.cuda.memory_allocated() / 1024 / 1024, 2),
        torch_reserved_after_mb=round(torch_module.cuda.memory_reserved() / 1024 / 1024, 2),
    )


def execute(suite_path: Path, output_dir: Path, metadata_path: Path) -> int:
    import numpy
    import psutil
    import soundfile
    import torch

    suite = load_suite(suite_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    configure_logs(output_dir)
    metadata: dict[str, Any] = {
        "experiment_id": suite["experiment_id"],
        "created_at": datetime.now(UTC).isoformat(),
        "model_name": "ACE-Step 1.5",
        "model_version": required_env("DOHAMUSIC_AI_ACE_STEP_MODEL_VERSION"),
        "model_variant": required_env("DOHAMUSIC_AI_ACE_STEP_MODEL_VARIANT"),
        "prompt_hash": hash_text(suite["request"]["prompt"]),
        "lyrics_hash": hash_text(suite["request"].get("lyrics")),
        "duration_requested": int(suite["request"]["duration_seconds"]),
        "runs": [],
    }
    handler = None
    llm_handler = None
    try:
        handler, llm_handler, load_metadata = initialize_handlers(psutil, torch)
        metadata.update(load_metadata)
        for run in suite["runs"]:
            run_sampler = ResourceSampler(psutil)
            run_sampler.start()
            result = run_one(
                handler,
                llm_handler,
                suite["request"],
                run,
                output_dir,
                psutil,
                soundfile,
                numpy,
                torch,
            )
            run_sampler.stop()
            enrich_resources(result, run_sampler, psutil, torch)
            metadata["runs"].append(result)
            metadata_path.write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        metadata["summary"] = aggregate_runs(metadata["runs"])
        metadata["success"] = metadata["summary"]["failure_count"] == 0
        return 0 if metadata["success"] else 4
    except FileNotFoundError as exc:
        metadata.update(
            success=False,
            error_code="AI_MODEL_NOT_FOUND",
            error_message=type(exc).__name__,
        )
        return 3
    except RuntimeError as exc:
        metadata.update(
            success=False,
            error_code="AI_MODEL_LOAD_FAILED",
            error_message=type(exc).__name__,
        )
        return 3
    except Exception as exc:  # noqa: BLE001 - 외부 모델 초기화 실패를 metadata로 기록한다.
        metadata.update(
            success=False,
            error_code="AI_BENCHMARK_SETUP_FAILED",
            error_message=type(exc).__name__,
        )
        return 3
    finally:
        del handler
        del llm_handler
        gc.collect()
        torch.cuda.empty_cache()
        from ai_worker.scripts.run_ace_step_smoke_test import query_system_vram_mb

        metadata["vram_after_release_mb"] = query_system_vram_mb()
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(json.dumps(metadata, ensure_ascii=False))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--metadata-path", type=Path)
    args = parser.parse_args()
    metadata_path = args.metadata_path or args.output_dir / "benchmark.json"
    try:
        return execute(args.suite.resolve(), args.output_dir.resolve(), metadata_path.resolve())
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_code": "AI_BENCHMARK_CONFIGURATION_FAILED",
                    "error_message": type(exc).__name__,
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
