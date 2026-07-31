"""Compare two PCM16 or float32 WAV outputs and print privacy-safe JSON metrics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from ai_worker.audio_similarity import compare_wav


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        metrics = compare_wav(args.reference.resolve(), args.candidate.resolve())
    except (OSError, ValueError, EOFError) as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error_code": "AUDIO_COMPARISON_FAILED",
                    "error_message": type(exc).__name__,
                }
            )
        )
        return 2
    payload = {"success": True, **metrics}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
