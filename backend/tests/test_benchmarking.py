from pathlib import Path

import pytest

from ai_worker.benchmarking import aggregate_runs, hash_file, hash_text, summarize
from ai_worker.scripts.run_ace_step_benchmark import load_suite


def test_hash_helpers_are_deterministic_without_exposing_text(tmp_path: Path) -> None:
    output = tmp_path / "output.wav"
    output.write_bytes(b"RIFF-test")

    assert hash_text("같은 입력") == hash_text("같은 입력")
    assert hash_text("같은 입력") != hash_text("다른 입력")
    assert hash_text(None) is None
    assert hash_file(output) == hash_file(output)


def test_summary_records_small_sample_statistics() -> None:
    result = summarize([1.0, 2.0, 3.0, None])

    assert result == {
        "count": 3.0,
        "minimum": 1.0,
        "maximum": 3.0,
        "mean": 2.0,
        "median": 2.0,
        "population_standard_deviation": 0.816,
    }


def test_aggregate_runs_tracks_failures_and_available_metrics() -> None:
    result = aggregate_runs(
        [
            {
                "success": True,
                "inference_time_seconds": 10,
                "total_time_seconds": 11,
                "peak_torch_allocated_mb": 3000,
            },
            {"success": False, "error_code": "AI_INFERENCE_FAILED"},
        ]
    )

    assert result["run_count"] == 2
    assert result["success_count"] == 1
    assert result["failure_count"] == 1
    assert result["success_rate"] == 0.5
    assert result["inference_time_seconds"]["mean"] == 10.0
    assert result["peak_nvidia_smi_mb"] is None


def test_benchmark_suite_serialization_contract(tmp_path: Path) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        '{"experiment_id":"EXP-TEST","runs":[{"run_id":"run-1","seed":7}],'
        '"request":{"prompt":"test","duration_seconds":10}}',
        encoding="utf-8",
    )

    suite = load_suite(suite_path)

    assert suite["experiment_id"] == "EXP-TEST"
    assert suite["runs"][0]["seed"] == 7


@pytest.mark.parametrize(
    "request_json",
    [
        '{"prompt":"", "duration_seconds":10}',
        '{"prompt":"test", "duration_seconds":9}',
    ],
)
def test_benchmark_suite_rejects_invalid_input(
    tmp_path: Path, request_json: str
) -> None:
    suite_path = tmp_path / "suite.json"
    suite_path.write_text(
        '{"experiment_id":"EXP-TEST","runs":[{"run_id":"run-1","seed":7}],'
        f'"request":{request_json}}}',
        encoding="utf-8",
    )

    with pytest.raises(ValueError):
        load_suite(suite_path)
