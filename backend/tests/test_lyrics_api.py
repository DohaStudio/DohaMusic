from __future__ import annotations

from fastapi.testclient import TestClient

from backend.lyrics.interfaces import LyricsGenerationResult, LyricsSection
from backend.lyrics.validator import render_sections


def payload() -> dict[str, object]:
    return {
        "topic": "<b>끝난 사랑</b>을 기억하는 밤",
        "genre": "Korean pop ballad",
        "mood": "warm and melancholic",
        "language": "ko",
        "keywords": ["밤", "계절", "기억"],
        "structure": [
            "verse",
            "pre_chorus",
            "chorus",
            "verse",
            "chorus",
            "bridge",
            "final_chorus",
        ],
        "target_duration_seconds": 180,
    }


def test_create_get_and_delete_template_lyrics(client: TestClient) -> None:
    response = client.post("/api/lyrics", json=payload())
    assert response.status_code == 201
    document = response.json()
    assert document["provider"] == "template"
    assert document["topic"] == "끝난 사랑을 기억하는 밤"
    assert document["status"] == "GENERATED"
    assert document["metadata"]["external_api"] is False
    assert document["metadata"]["section_count"] == 7
    assert document["metadata"]["generation_time_seconds"] >= 0
    assert document["metadata"]["validation_time_seconds"] >= 0
    assert document["metadata"]["storage_time_seconds"] >= 0
    assert len(document["sections"]) == 7

    fetched = client.get(f"/api/lyrics/{document['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == document

    deleted = client.delete(f"/api/lyrics/{document['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/lyrics/{document['id']}").status_code == 404


def test_validate_direct_lyrics(client: TestClient) -> None:
    response = client.post(
        "/api/lyrics/validate",
        json={
            "raw_lyrics": "[Verse]\n밤을 걷는다\n\n[Chorus]\n기억해",
            "language": "ko",
        },
    )
    assert response.status_code == 200
    result = response.json()
    assert result["valid"] is True
    assert result["section_count"] == 2
    assert result["line_count"] == 2
    assert result["errors"] == []


def test_lyrics_api_rejects_invalid_requests(client: TestClient) -> None:
    cases = [
        {**payload(), "topic": ""},
        {**payload(), "language": "ja"},
        {**payload(), "structure": ["verse", "unknown"]},
        {**payload(), "keywords": [str(index) for index in range(11)]},
    ]
    for case in cases:
        response = client.post("/api/lyrics", json=case)
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "INVALID_INPUT"


def test_lyrics_api_not_found(client: TestClient) -> None:
    response = client.get("/api/lyrics/missing")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "RESOURCE_NOT_FOUND"


def test_provider_failure_maps_to_stable_error(client: TestClient) -> None:
    class FailingGenerator:
        provider = "failing"
        model_name = "failing"
        model_version = None

        def generate(self, _request):
            raise RuntimeError("sensitive provider detail")

    client.app.state.lyrics_service.generator = FailingGenerator()
    response = client.post("/api/lyrics", json=payload())
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "LYRICS_GENERATION_FAILED"
    assert "sensitive" not in response.text


def test_revision_creates_immutable_version_and_preserves_source(
    client: TestClient,
) -> None:
    source_payload = {
        "topic": "a remembered night",
        "genre": "ballad",
        "mood": "warm",
        "language": "en",
        "keywords": ["night", "memory"],
        "structure": ["verse", "chorus"],
    }
    source_response = client.post("/api/lyrics", json=source_payload)
    assert source_response.status_code == 201
    source = source_response.json()

    class RevisionGenerator:
        provider = "revision-test"
        model_name = "revision-test"
        model_version = "1"

        def revise(self, _request):
            sections = (
                LyricsSection("verse", ("A revised quiet night",)),
                LyricsSection("chorus", ("The memory returns",)),
            )
            return LyricsGenerationResult(
                title="Night Memory Revised",
                sections=sections,
                full_text=render_sections(sections),
                provider=self.provider,
                model_name=self.model_name,
                model_version=self.model_version,
                generation_time_seconds=0.01,
            )

    client.app.state.lyrics_service.generator = RevisionGenerator()
    revised_response = client.post(
        f"/api/lyrics/{source['id']}/revise",
        json={"instruction": "make the chorus more concise"},
    )
    assert revised_response.status_code == 201
    revised = revised_response.json()
    assert revised["parent_id"] == source["id"]
    assert revised["version"] == 2
    assert revised["status"] == "REVISED"
    assert len(revised["source_hash"]) == 64
    assert len(revised["result_hash"]) == 64
    assert revised["full_text"] != source["full_text"]

    unchanged = client.get(f"/api/lyrics/{source['id']}").json()
    assert unchanged["full_text"] == source["full_text"]
    assert unchanged["version"] == 1
    protected_delete = client.delete(f"/api/lyrics/{source['id']}")
    assert protected_delete.status_code == 422
    assert protected_delete.json()["error"]["code"] == "LYRICS_REVISION_FAILED"


def test_template_provider_rejects_semantic_revision(client: TestClient) -> None:
    source = client.post(
        "/api/lyrics",
        json={
            "topic": "a remembered night",
            "language": "en",
            "structure": ["verse", "chorus"],
        },
    ).json()
    response = client.post(
        f"/api/lyrics/{source['id']}/revise",
        json={"instruction": "change the point of view"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "LYRICS_REVISION_FAILED"
