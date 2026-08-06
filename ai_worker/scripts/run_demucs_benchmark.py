"""Run reproducible offline Demucs repetitions and aggregate objective metrics."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ai_worker.benchmarking import aggregate_stem_runs, hash_file


def run_once(args: argparse.Namespace, run_number: int) -> dict[str, Any]:
    run_id = f"run-{run_number:02d}"
    run_root = args.output_root / run_id
    metadata_path = run_root / "metadata.json"
    command = [
        str(args.runtime_python),
        str(args.runner_path),
        "--input-path",
        str(args.input_path),
        "--vocals-output",
        str(run_root / "vocals.wav"),
        "--instrumental-output",
        str(run_root / "instrumental.wav"),
        "--metadata-path",
        str(metadata_path),
        "--work-dir",
        str(run_root / "work"),
        "--model-cache-path",
        str(args.model_cache_path),
        "--model-name",
        args.model_name,
        "--model-version",
        args.model_version,
        "--device",
        args.device,
        "--segment-seconds",
        str(args.segment_seconds),
        "--shifts",
        str(args.shifts),
        "--overlap",
        str(args.overlap),
        "--experiment-id",
        args.experiment_id,
    ]
    environment = os.environ.copy()
    environment.update(
        {
            "HF_HOME": str(args.model_cache_path.resolve()),
            "HF_HUB_OFFLINE": "1",
            "DO_NOT_TRACK": "1",
        }
    )
    started_at = time.perf_counter()
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        timeout=args.timeout_seconds,
        env=environment,
    )
    total_time = round(time.perf_counter() - started_at, 3)
    if metadata_path.is_file():
        result = json.loads(metadata_path.read_text(encoding="utf-8"))
    else:
        result = {
            "success": False,
            "error_code": "STEM_BENCHMARK_RUNNER_FAILED",
            "error_message": f"return code {completed.returncode}",
        }
    result.update(run_id=run_id, total_time_seconds=total_time)
    return result


def validate(args: argparse.Namespace) -> None:
    for file_path in (args.runtime_python, args.runner_path, args.input_path):
        if not file_path.is_file():
            raise ValueError(f"Required file is missing: {file_path}")
    if not args.model_cache_path.is_dir():
        raise ValueError("Demucs model cache is missing")
    if args.runs < 1:
        raise ValueError("runs must be at least one")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-python", type=Path, required=True)
    parser.add_argument("--runner-path", type=Path, required=True)
    parser.add_argument("--input-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--result-path", type=Path, required=True)
    parser.add_argument("--model-cache-path", type=Path, required=True)
    parser.add_argument("--model-name", default="htdemucs")
    parser.add_argument("--model-version", default="4.1.0")
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--segment-seconds", type=float, default=7.0)
    parser.add_argument("--shifts", type=int, default=1)
    parser.add_argument("--overlap", type=float, default=0.25)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--experiment-id", default="EXP-003")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validate(args)
    args.output_root.mkdir(parents=True, exist_ok=True)
    runs = [run_once(args, run_number) for run_number in range(1, args.runs + 1)]
    report = {
        "experiment_id": args.experiment_id,
        "created_at": datetime.now(UTC).isoformat(),
        "input": {
            "name": args.input_path.name,
            "size_bytes": args.input_path.stat().st_size,
            "sha256": hash_file(args.input_path),
        },
        "configuration": {
            "provider": "demucs",
            "model_name": args.model_name,
            "model_version": args.model_version,
            "device": args.device,
            "segment_seconds": args.segment_seconds,
            "shifts": args.shifts,
            "overlap": args.overlap,
            "offline": True,
        },
        "runs": runs,
        "summary": aggregate_stem_runs(runs),
    }
    args.result_path.parent.mkdir(parents=True, exist_ok=True)
    args.result_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["failure_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
