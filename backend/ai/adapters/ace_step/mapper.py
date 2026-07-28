"""Map the common request to the standalone ACE-Step runner contract."""

from backend.ai.interfaces.music_generator import GenerationInput


def to_runner_request(request: GenerationInput) -> dict[str, object]:
    return {
        "experiment_case": f"backend-job-{request.job_id}",
        "prompt": request.prompt,
        "lyrics": request.lyrics,
        "instrumental": request.lyrics is None,
        "duration_seconds": request.duration_seconds,
        "seed": request.seed,
        "vocal_language": "unknown",
    }
