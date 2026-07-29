"""Benchmark the external lyrics adapter contract without billable network calls."""

from __future__ import annotations

import argparse
import json
import statistics
import time

from backend.lyrics.interfaces import LyricsGenerationRequest
from backend.lyrics.providers.openai.adapter import OpenAILyricsGenerator
from backend.lyrics.providers.openai.config import OpenAILyricsConfig


class DeterministicTransport:
    def create_response(
        self, payload: dict[str, object], timeout_seconds: float
    ) -> dict[str, object]:
        del payload, timeout_seconds
        body = {
            "title": "기억의 밤",
            "language": "ko",
            "sections": [
                {"type": "verse", "label": "Verse", "lines": ["조용한 밤을 걸어"]},
                {"type": "chorus", "label": "Chorus", "lines": ["기억이 돌아와"]},
            ],
            "full_text": "",
            "warnings": [],
        }
        return {
            "status": "completed",
            "model": "gpt-5-mini-2025-08-07",
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": json.dumps(body)}],
                }
            ],
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=100)
    args = parser.parse_args()
    adapter = OpenAILyricsGenerator(
        OpenAILyricsConfig(
            api_key="benchmark-placeholder",
            model="gpt-5-mini-2025-08-07",
            base_url="https://api.openai.com/v1",
            timeout_seconds=1.0,
            total_deadline_seconds=5.0,
            max_retries=1,
            temperature=None,
            max_output_tokens=1000,
            input_cost_per_million=0.25,
            output_cost_per_million=2.0,
            pricing_version="2026-07-29",
            max_cost_per_request=None,
        ),
        transport=DeterministicTransport(),
    )
    request = LyricsGenerationRequest(
        topic="여름밤의 기억",
        genre="발라드",
        mood="따뜻함",
        language="ko",
        keywords=("여름", "기억"),
        structure=("verse", "chorus"),
        target_duration_seconds=120,
        additional_instructions=None,
    )
    durations: list[float] = []
    successes = 0
    for _ in range(args.runs):
        started_at = time.perf_counter()
        result = adapter.generate(request)
        durations.append((time.perf_counter() - started_at) * 1_000)
        successes += int(bool(result.sections))
    print(
        json.dumps(
            {
                "benchmark_kind": "simulated_transport_adapter_only",
                "external_api_called": False,
                "runs": args.runs,
                "successes": successes,
                "success_rate": successes / args.runs,
                "latency_ms": {
                    "min": min(durations),
                    "mean": statistics.fmean(durations),
                    "max": max(durations),
                },
                "synthetic_usage": {"input_tokens": 100, "output_tokens": 50},
                "estimated_cost_usd": 0.000125,
                "pricing_snapshot": "2026-07-29",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
