"""Standard-library helpers for reproducible AI benchmark metadata."""

from __future__ import annotations

import hashlib
import statistics
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def hash_text(value: str | None) -> str | None:
    """Return a stable SHA-256 without retaining the original text."""

    if value is None:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def hash_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a potentially large output without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        while chunk := file_handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def summarize(values: Iterable[float | int | None]) -> dict[str, float] | None:
    """Compute small-sample descriptive statistics for available values."""

    numbers = [float(value) for value in values if value is not None]
    if not numbers:
        return None
    return {
        "count": float(len(numbers)),
        "minimum": round(min(numbers), 3),
        "maximum": round(max(numbers), 3),
        "mean": round(statistics.fmean(numbers), 3),
        "median": round(statistics.median(numbers), 3),
        "population_standard_deviation": round(statistics.pstdev(numbers), 3),
    }


def aggregate_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate success and performance without inventing missing metrics."""

    successful = [run for run in runs if run.get("success") is True]
    return {
        "run_count": len(runs),
        "success_count": len(successful),
        "failure_count": len(runs) - len(successful),
        "success_rate": round(len(successful) / len(runs), 4) if runs else 0.0,
        "inference_time_seconds": summarize(
            run.get("inference_time_seconds") for run in successful
        ),
        "total_time_seconds": summarize(
            run.get("total_time_seconds") for run in successful
        ),
        "peak_torch_allocated_mb": summarize(
            run.get("peak_torch_allocated_mb") for run in successful
        ),
        "peak_torch_reserved_mb": summarize(
            run.get("peak_torch_reserved_mb") for run in successful
        ),
        "peak_nvidia_smi_mb": summarize(
            run.get("peak_nvidia_smi_mb") for run in successful
        ),
        "system_memory_peak_mb": summarize(
            run.get("system_memory_peak_mb") for run in successful
        ),
    }


def aggregate_stem_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate the objective fields emitted by the Demucs runner."""

    successful = [run for run in runs if run.get("success") is True]
    return {
        "run_count": len(runs),
        "success_count": len(successful),
        "failure_count": len(runs) - len(successful),
        "success_rate": round(len(successful) / len(runs), 4) if runs else 0.0,
        "load_time_seconds": summarize(
            run.get("load_time_seconds") for run in successful
        ),
        "separation_time_seconds": summarize(
            run.get("separation_time_seconds") for run in successful
        ),
        "total_time_seconds": summarize(
            run.get("total_time_seconds") for run in successful
        ),
        "peak_torch_allocated_mb": summarize(
            run.get("peak_torch_allocated_mb") for run in successful
        ),
        "peak_torch_reserved_mb": summarize(
            run.get("peak_torch_reserved_mb") for run in successful
        ),
        "peak_nvidia_smi_mb": summarize(
            run.get("peak_nvidia_smi_mb") for run in successful
        ),
        "process_memory_peak_mb": summarize(
            run.get("process_memory_peak_mb") for run in successful
        ),
        "system_memory_peak_mb": summarize(
            run.get("system_memory_peak_mb") for run in successful
        ),
        "process_cpu_percent_peak": summarize(
            run.get("process_cpu_percent_peak") for run in successful
        ),
        "process_cpu_time_seconds": summarize(
            run.get("process_cpu_time_seconds") for run in successful
        ),
    }
