"""Workspace Job 공식 Resource API transport 계약 검증."""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.api.v1.dependencies import REQUEST_ID_HEADER
from backend.models.workspace import JobStatus
from backend.services.workspace import JobService, WorkspaceService


def _workspace_service(client: TestClient) -> WorkspaceService:
    service = client.app.state.workspace_service
    assert isinstance(service, WorkspaceService)
    return service


def _job_service(client: TestClient) -> JobService:
    service = client.app.state.job_service
    assert isinstance(service, JobService)
    return service


def _seed_project(client: TestClient) -> tuple[UUID, UUID]:
    owner_id = uuid4()
    workspace = _workspace_service(client).create_workspace(
        owner_id=owner_id,
        name=f"Job 작업실-{uuid4()}",
    )
    project = _workspace_service(client).create_project(
        workspace_id=workspace.workspace_id,
        title=f"Job 프로젝트-{uuid4()}",
        created_by=owner_id,
    )
    return owner_id, project.project_id


def _create_job(
    client: TestClient,
    project_id: UUID,
    *,
    key: str,
    job_type: str = "lyrics_generation",
    extra: dict[str, object] | None = None,
):
    payload: dict[str, object] = {
        "project_id": str(project_id),
        "job_type": job_type,
        "settings_snapshot": {"temperature": 0.7},
    }
    if extra:
        payload.update(extra)
    return client.post(
        "/api/v1/jobs",
        json=payload,
        headers={"Idempotency-Key": key},
    )


def test_job_endpoints_require_bootstrap(client: TestClient) -> None:
    job_id = uuid4()
    project_id = uuid4()
    requests = (
        ("GET", "/api/v1/jobs", None, None),
        (
            "POST",
            "/api/v1/jobs",
            {"project_id": str(project_id), "job_type": "lyrics_generation"},
            {"Idempotency-Key": "bootstrap-create"},
        ),
        ("GET", f"/api/v1/jobs/{job_id}", None, None),
        ("POST", f"/api/v1/jobs/{job_id}/cancel", None, None),
        (
            "POST",
            f"/api/v1/jobs/{job_id}/retry",
            None,
            {"Idempotency-Key": "bootstrap-retry"},
        ),
    )
    for method, path, body, headers in requests:
        response = client.request(method, path, json=body, headers=headers)
        assert response.status_code == 409
        assert response.json()["error"]["error_code"] == (
            "WORKSPACE_BOOTSTRAP_REQUIRED"
        )
        assert response.headers[REQUEST_ID_HEADER]


def test_job_create_and_replay_return_safe_immutable_aggregate(
    client: TestClient,
) -> None:
    _, project_id = _seed_project(client)

    created = _create_job(client, project_id, key="job-create")
    replayed = _create_job(client, project_id, key="job-create")

    assert created.status_code == replayed.status_code == 201
    assert created.json()["data"]["job_id"] == replayed.json()["data"]["job_id"]
    data = created.json()["data"]
    assert data["status"] == "queued"
    assert data["inputs"] == []
    assert data["outputs"] == []
    assert data["model_usages"] == []
    for sensitive in (
        "workspace_id",
        "requested_by",
        "claim_token",
        "claimed_by",
        "lease_expires_at",
        "heartbeat_at",
        "cancel_requested_at",
        "attempt",
        "settings_snapshot",
    ):
        assert sensitive not in data


def test_job_create_rejects_internal_fields_and_invalid_inputs(
    client: TestClient,
) -> None:
    _, project_id = _seed_project(client)
    for index, extra in enumerate(
        (
            {"workspace_id": str(uuid4())},
            {"requested_by": str(uuid4())},
            {"status": "running"},
            {"claim_token": str(uuid4())},
            {
                "inputs": [
                    {
                        "input_role": "lyrics",
                        "input_order": 0,
                        "asset_version_id": str(uuid4()),
                        "artifact_id": str(uuid4()),
                    }
                ]
            },
        )
    ):
        response = _create_job(
            client,
            project_id,
            key=f"invalid-create-{index}",
            extra=extra,
        )
        assert response.status_code == 422
        assert response.json()["error"]["error_code"] == "INVALID_INPUT"


def test_job_list_uses_service_cursor_and_official_filters(client: TestClient) -> None:
    _, project_id = _seed_project(client)
    for index in range(3):
        assert (
            _create_job(client, project_id, key=f"job-list-{index}").status_code == 201
        )

    first = client.get(
        "/api/v1/jobs",
        params={"project_id": str(project_id), "limit": 2},
    )
    assert first.status_code == 200
    assert first.json()["pagination"]["has_more"] is True
    second = client.get(first.json()["links"]["next"])
    ids = [item["job_id"] for item in first.json()["data"] + second.json()["data"]]
    assert len(ids) == len(set(ids)) == 3

    filtered = client.get(
        "/api/v1/jobs",
        params={"status": "queued", "job_type": "lyrics_generation"},
    )
    assert filtered.status_code == 200
    assert len(filtered.json()["data"]) == 3

    invalid = client.get("/api/v1/jobs", params={"job_type": "unknown"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["error_code"] == "INVALID_INPUT"

    for forbidden in ("owner_id", "workspace_id", "include_deleted", "sort"):
        rejected = client.get("/api/v1/jobs", params={forbidden: str(uuid4())})
        assert rejected.status_code == 422
        assert rejected.json()["error"]["error_code"] == "INVALID_INPUT"

    tampered = client.get(
        "/api/v1/jobs",
        params={"limit": 2, "cursor": first.json()["pagination"]["next_cursor"] + "x"},
    )
    assert tampered.status_code == 422
    assert tampered.json()["error"]["error_code"] == "INVALID_CURSOR"

    cross_filter = client.get(
        "/api/v1/jobs",
        params={
            "limit": 2,
            "status": "queued",
            "cursor": first.json()["pagination"]["next_cursor"],
        },
    )
    assert cross_filter.status_code == 422
    assert cross_filter.json()["error"]["error_code"] == "INVALID_CURSOR"


def test_job_create_requires_key_and_maps_idempotency_conflict(
    client: TestClient,
) -> None:
    _, project_id = _seed_project(client)
    missing = client.post(
        "/api/v1/jobs",
        json={"project_id": str(project_id), "job_type": "lyrics_generation"},
    )
    assert missing.status_code == 422
    assert missing.json()["error"]["error_code"] == "INVALID_INPUT"

    assert _create_job(client, project_id, key="job-conflict").status_code == 201
    conflict = _create_job(
        client,
        project_id,
        key="job-conflict",
        extra={"settings_snapshot": {"temperature": 0.2}},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["error_code"] == "IDEMPOTENCY_KEY_REUSED"

    snapshot_required = _create_job(
        client,
        project_id,
        key="job-mix-without-snapshot",
        job_type="mix",
    )
    assert snapshot_required.status_code == 422
    assert snapshot_required.json()["error"]["error_code"] == "INVALID_INPUT"


def test_job_detail_and_missing_error_are_resource_specific(client: TestClient) -> None:
    _, project_id = _seed_project(client)
    created = _create_job(client, project_id, key="job-detail")
    job_id = created.json()["data"]["job_id"]

    detailed = client.get(f"/api/v1/jobs/{job_id}")
    assert detailed.status_code == 200
    assert detailed.json()["data"] == created.json()["data"]

    missing = client.get(f"/api/v1/jobs/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["error_code"] == "JOB_NOT_FOUND"


def test_job_cancel_is_idempotent_and_retry_creates_frozen_job(
    client: TestClient,
) -> None:
    _, project_id = _seed_project(client)
    created = _create_job(client, project_id, key="job-cancel-retry")
    original_id = created.json()["data"]["job_id"]

    cancelled = client.post(f"/api/v1/jobs/{original_id}/cancel")
    repeated_cancel = client.post(f"/api/v1/jobs/{original_id}/cancel")
    assert cancelled.status_code == repeated_cancel.status_code == 200
    assert cancelled.json()["data"]["status"] == "cancelled"

    retried = client.post(
        f"/api/v1/jobs/{original_id}/retry",
        headers={"Idempotency-Key": "job-retry"},
    )
    replayed = client.post(
        f"/api/v1/jobs/{original_id}/retry",
        headers={"Idempotency-Key": "job-retry"},
    )
    assert retried.status_code == replayed.status_code == 202
    assert retried.json()["data"]["job_id"] == replayed.json()["data"]["job_id"]
    assert retried.json()["data"]["retry_of_job_id"] == original_id
    assert retried.json()["data"]["status"] == "queued"


def test_running_cancel_returns_accepted_marker_and_terminal_conflicts(
    client: TestClient,
) -> None:
    owner_id, project_id = _seed_project(client)
    created = _create_job(client, project_id, key="job-running-cancel")
    job_id = UUID(created.json()["data"]["job_id"])
    _job_service(client).transition_job_for_owner(
        job_id,
        effective_owner_id=owner_id,
        status=JobStatus.RUNNING,
        progress_percent=Decimal("10"),
        stage="provider_dispatch",
    )

    cancel = client.post(f"/api/v1/jobs/{job_id}/cancel")
    assert cancel.status_code == 202
    assert cancel.json()["data"]["status"] == "running"

    active_retry = client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers={"Idempotency-Key": "active-retry"},
    )
    assert active_retry.status_code == 409
    assert active_retry.json()["error"]["error_code"] == "JOB_NOT_RETRYABLE"
