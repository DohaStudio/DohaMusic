from __future__ import annotations

from fastapi.testclient import TestClient

from backend.tests.test_pipeline_api import (
    create_pipeline,
    create_profile,
    wait_for_pipeline,
)


def test_history_empty_and_pagination(client: TestClient) -> None:
    assert client.get("/api/history").json() == []
    profile_id = create_profile(client)
    first = create_pipeline(client, profile_id)
    second = create_pipeline(client, profile_id)

    page = client.get("/api/history", params={"limit": 1, "offset": 1})
    assert page.status_code == 200
    assert len(page.json()) == 1
    assert page.json()[0]["job_id"] == first["id"]
    assert second["project_id"] == first["project_id"]


def test_history_detail_filter_search_and_public_dto(client: TestClient) -> None:
    job = create_pipeline(client, create_profile(client))
    completed = wait_for_pipeline(client, str(job["id"]))

    response = client.get("/api/history", params={"status": "COMPLETED", "q": "Mock pipeline"})
    assert response.status_code == 200
    item = response.json()[0]
    assert item["job_id"] == job["id"]
    assert item["has_audio"] is True
    assert item["duration"] == 10
    assert item["voice_profile_name"] == "Pipeline 동의 음성"
    assert item["audio_analysis"]["analysis_status"] == "PARTIAL"
    assert "source_file_role" not in item["audio_analysis"]
    assert not {
        "file_path",
        "storage_path",
        "filesystem",
        "provider_config",
        "result_metadata",
    }.intersection(item)

    detail = client.get(f"/api/history/{job['id']}")
    assert detail.status_code == 200
    assert detail.json()["completed_at"] == completed["completed_at"]
    assert client.get("/api/history/missing").status_code == 404


def test_project_crud_detail_and_safe_delete_keeps_jobs(client: TestClient) -> None:
    created = client.post("/api/projects", json={"title": "Dance Pop", "description": "Singles"})
    assert created.status_code == 201
    project_id = created.json()["id"]
    profile_id = create_profile(client)
    pipeline = client.post(
        "/api/pipelines",
        json={
            "prompt": "Project song",
            "voice_profile_id": profile_id,
            "project_id": project_id,
        },
    )
    assert pipeline.status_code == 202
    wait_for_pipeline(client, pipeline.json()["id"])

    projects = client.get("/api/projects").json()
    assert next(item for item in projects if item["id"] == project_id)["job_count"] == 1
    detail = client.get(f"/api/projects/{project_id}")
    assert detail.status_code == 200
    assert detail.json()["jobs"][0]["job_id"] == pipeline.json()["id"]
    assert detail.json()["jobs"][0]["audio_analysis"]["analysis_status"] == "PARTIAL"

    updated = client.patch(
        f"/api/projects/{project_id}",
        json={"title": "Dance Pop Album", "description": None},
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Dance Pop Album"
    assert updated.json()["description"] is None

    deleted = client.delete(f"/api/projects/{project_id}")
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}").status_code == 404
    kept = client.get(f"/api/history/{pipeline.json()['id']}")
    assert kept.status_code == 200
    assert kept.json()["project_id"] is None


def test_pipeline_rejects_missing_project(client: TestClient) -> None:
    response = client.post(
        "/api/pipelines",
        json={
            "prompt": "Missing project",
            "voice_profile_id": create_profile(client),
            "project_id": "00000000-0000-0000-0000-000000000099",
        },
    )
    assert response.status_code == 404
