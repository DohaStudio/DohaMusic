from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.kpop.options import KPopGenerationOptions
from backend.kpop.prompt_compiler import (
    KPopPromptCompiler,
    KPopPromptValidationError,
)
from backend.models.pipeline_job import PipelineJob
from backend.schemas.lyrics import LyricsCreate
from backend.schemas.pipeline import PipelineCreate
from backend.tests.test_pipeline_api import create_profile, wait_for_pipeline


def options_payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "preset_id": "kpop_dance",
        "requested_bpm": 124,
        "language_ratio": {"ko": 70, "en": 30},
        "hook": {
            "phrase": "Play My Heart",
            "style": "title_repeat",
            "repeat_count": 3,
        },
        "include_post_chorus": True,
        "include_dance_break": False,
        "vocal_energy": "medium",
        "concept": "confident_bright",
    }
    payload.update(updates)
    return payload


def pipeline_payload(profile_id: str, **updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "prompt": "여름밤의 자신감 있는 곡",
        "genre": "kpop_dance",
        "duration_seconds": 30,
        "seed": 1042,
        "voice_profile_id": profile_id,
        "generation_options": options_payload(),
    }
    payload.update(updates)
    return payload


def test_generation_options_are_optional_and_strict() -> None:
    legacy = PipelineCreate(prompt="legacy", voice_profile_id="1" * 36, genre="rock")
    assert legacy.generation_options is None
    valid = PipelineCreate.model_validate(pipeline_payload("1" * 36)).generation_options
    assert valid is not None
    assert valid.requested_bpm == 124
    with pytest.raises(ValidationError):
        KPopGenerationOptions.model_validate(options_payload(detected_bpm=123))
    with pytest.raises(ValidationError):
        KPopGenerationOptions.model_validate(
            options_payload(hook={"phrase": "Hook", "unknown": True})
        )


@pytest.mark.parametrize("bpm", [70, 180])
def test_bpm_accepts_integer_boundaries(bpm: int) -> None:
    assert (
        KPopGenerationOptions.model_validate(
            options_payload(requested_bpm=bpm)
        ).requested_bpm
        == bpm
    )


@pytest.mark.parametrize(
    ("updates", "location"),
    [
        ({"preset_id": "unknown"}, "preset_id"),
        ({"requested_bpm": 69}, "requested_bpm"),
        ({"language_ratio": {"ko": 70, "en": 20}}, "language_ratio"),
        ({"hook": {"phrase": "", "style": "title_repeat"}}, "hook"),
        ({"hook": {"phrase": "ok", "style": "unknown"}}, "hook"),
        ({"hook": {"phrase": "ok", "repeat_count": 7}}, "hook"),
        ({"vocal_energy": "extreme"}, "vocal_energy"),
        ({"concept": "x" * 41}, "concept"),
    ],
)
def test_generation_option_validation_rejects_invalid_values(
    updates: dict[str, object], location: str
) -> None:
    with pytest.raises(ValidationError) as captured:
        KPopGenerationOptions.model_validate(options_payload(**updates))
    assert location in str(captured.value)


def test_preset_and_genre_mismatch_is_rejected() -> None:
    with pytest.raises(ValidationError) as captured:
        PipelineCreate.model_validate(pipeline_payload("1" * 36, genre="rock"))
    assert "genre must match" in str(captured.value)


def test_compiler_applies_all_options_deterministically() -> None:
    options = KPopGenerationOptions.model_validate(options_payload())
    first = KPopPromptCompiler().compile(
        "kpop_dance", "여름밤의 자신감 있는 곡", options=options
    )
    second = KPopPromptCompiler().compile(
        "kpop_dance", "여름밤의 자신감 있는 곡", options=options
    )
    assert first == second
    assert first.normalized_options is not None
    for expected in (
        "124 BPM",
        "70% Korean and 30% English",
        '"Play My Heart"',
        "approximately 3 times",
        "Include a post-chorus",
        "Do not include a dance break",
        "medium vocal energy",
        "confident_bright",
    ):
        assert expected in first.prompt
    assert first.prompt.endswith("여름밤의 자신감 있는 곡")
    assert first.prompt.count("Target tempo around") == 1


def test_compiler_omits_empty_hook_and_keeps_safety_and_length_limits() -> None:
    options = KPopGenerationOptions.model_validate(
        options_payload(hook=None, concept=None)
    )
    result = KPopPromptCompiler().compile("kpop_dance", "원본 요청", options=options)
    assert "Repeat the hook" not in result.prompt
    with pytest.raises(KPopPromptValidationError):
        KPopPromptCompiler().compile(
            "kpop_dance", "유명 가수처럼 노래해 줘", options=options
        )
    with pytest.raises(KPopPromptValidationError):
        KPopPromptCompiler().compile("kpop_dance", "가" * 1400, options=options)


def test_pipeline_snapshot_public_metadata_and_retry_restore_options(
    client: TestClient,
) -> None:
    profile_id = create_profile(client)
    response = client.post("/api/pipelines", json=pipeline_payload(profile_id))
    assert response.status_code == 202
    created = response.json()
    assert created["generation_options"]["requested_bpm"] == 124
    assert created["kpop_prompt_compiler_version"] == "kpop-prompt-v1"
    assert created["prompt"].endswith("여름밤의 자신감 있는 곡")
    completed = wait_for_pipeline(client, created["id"])
    assert (
        completed["result_metadata"]["generation_options"]["hook"]["phrase"]
        == "Play My Heart"
    )
    assert "input_snapshot" not in completed

    with client.app.state.session_factory() as session:
        source = session.get(PipelineJob, created["id"])
        assert source is not None
        snapshot = source.input_snapshot
        assert snapshot["original_prompt"] == "여름밤의 자신감 있는 곡"
        assert snapshot["compiled_prompt"] == source.prompt
        assert snapshot["compiler_version"] == "kpop-prompt-v1"
        assert snapshot["normalized_generation_options"]["requested_bpm"] == 124
        source.status = "FAILED"
        source.current_step = "failed"
        session.commit()

    retried = client.post(f"/api/pipelines/{created['id']}/retry")
    assert retried.status_code == 202
    retry_job = retried.json()["job"]
    assert retry_job["retry_of_job_id"] == created["id"]
    assert retry_job["generation_options"] == created["generation_options"]
    assert retry_job["seed"] == created["seed"]

    history = client.get("/api/history").json()
    history_item = next(item for item in history if item["job_id"] == created["id"])
    assert history_item["generation_options"]["preset_id"] == "kpop_dance"
    assert "compiled_prompt" not in history_item
    project = client.get(f"/api/projects/{created['project_id']}").json()
    project_item = next(
        item for item in project["jobs"] if item["job_id"] == created["id"]
    )
    assert project_item["generation_options"]["concept"] == "confident_bright"


def test_api_maps_generation_option_errors(client: TestClient) -> None:
    profile_id = create_profile(client)
    invalid_bpm = client.post(
        "/api/pipelines",
        json=pipeline_payload(
            profile_id,
            generation_options=options_payload(requested_bpm=181),
        ),
    )
    assert invalid_bpm.status_code == 422
    assert invalid_bpm.json()["error"]["code"] == "INVALID_REQUESTED_BPM"
    mismatch = client.post(
        "/api/pipelines", json=pipeline_payload(profile_id, genre="rock")
    )
    assert mismatch.status_code == 422
    assert mismatch.json()["error"]["code"] == "PRESET_GENRE_MISMATCH"


def test_lyrics_options_control_hook_and_post_chorus(client: TestClient) -> None:
    request = LyricsCreate.model_validate(
        {
            "topic": "여름",
            "genre": "kpop_dance",
            "generation_options": options_payload(
                hook={
                    "phrase": "Play My Heart",
                    "style": "chant",
                    "repeat_count": 3,
                },
                include_post_chorus=False,
            ),
        }
    )
    assert "post_chorus" not in request.structure
    assert request.generation_options is not None
    assert request.generation_options.language_ratio is not None
    assert request.generation_options.language_ratio.ko == 70
    response = client.post(
        "/api/lyrics",
        json={
            "topic": "여름",
            "genre": "kpop_dance",
            "generation_options": options_payload(
                hook={
                    "phrase": "Play My Heart",
                    "style": "chant",
                    "repeat_count": 3,
                },
                include_post_chorus=False,
            ),
        },
    )
    assert response.status_code == 201
    document = response.json()
    assert "post_chorus" not in document["structure"]
    chorus = next(
        section
        for section in document["sections"]
        if section["section_type"] == "chorus"
    )
    assert "Play My Heart, Play My Heart, Play My Heart" in chorus["lines"][0]
    assert document["metadata"]["generation_options"]["language_ratio"] == {
        "ko": 70,
        "en": 30,
    }
