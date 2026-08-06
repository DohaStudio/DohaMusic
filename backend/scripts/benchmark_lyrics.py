"""Benchmark the local Template lyrics provider through the HTTP API."""

from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.core.config import Settings


def _payload(language: str) -> dict[str, object]:
    if language == "ko":
        return {
            "topic": "끝난 사랑을 기억하는 밤",
            "genre": "Korean pop ballad",
            "mood": "warm and melancholic",
            "language": "ko",
            "keywords": ["밤", "계절", "기억"],
            "target_duration_seconds": 180,
        }
    return {
        "topic": "a night that remembers a finished love",
        "genre": "pop ballad",
        "mood": "warm and melancholic",
        "language": "en",
        "keywords": ["night", "season", "memory"],
        "target_duration_seconds": 180,
    }


def run_benchmark() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="dohamusic-lyrics-") as temp_dir:
        root = Path(temp_dir)
        app = create_app(
            Settings(
                database_url=f"sqlite:///{(root / 'benchmark.db').as_posix()}",
                auto_migrate=True,
                storage_root=root / "storage",
                lyrics_provider="template",
                mock_generation_delay_seconds=0.0,
                log_level="WARNING",
            )
        )
        results: dict[str, object] = {}
        with TestClient(app) as client:
            for language in ("ko", "en"):
                started_at = time.perf_counter()
                response = client.post("/api/lyrics", json=_payload(language))
                api_time = time.perf_counter() - started_at
                response.raise_for_status()
                document = response.json()

                validation_started_at = time.perf_counter()
                validation = client.post(
                    "/api/lyrics/validate",
                    json={
                        "raw_lyrics": document["full_text"],
                        "language": language,
                    },
                )
                validation_api_time = time.perf_counter() - validation_started_at
                validation.raise_for_status()
                metadata = document["metadata"]
                results[language] = {
                    "provider": document["provider"],
                    "model_name": document["model_name"],
                    "generation_time_seconds": metadata["generation_time_seconds"],
                    "validation_time_seconds": metadata["validation_time_seconds"],
                    "storage_time_seconds": metadata["storage_time_seconds"],
                    "api_response_time_seconds": api_time,
                    "validation_api_time_seconds": validation_api_time,
                    "character_count": metadata["character_count"],
                    "line_count": metadata["line_count"],
                    "section_count": metadata["section_count"],
                    "valid": validation.json()["valid"],
                    "warning_count": len(validation.json()["warnings"]),
                    "sample": document["sections"][0],
                }
        return {
            "external_llm_used": False,
            "quality_claim": False,
            "results": results,
        }


def main() -> int:
    print(json.dumps(run_benchmark(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
