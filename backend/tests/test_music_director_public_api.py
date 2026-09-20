from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from backend.models.workspace import CompositionSnapshot, Job
from backend.schemas.workspace.music_director import MusicDirectorApplyRequest
from backend.services.workspace import (
    JobService,
    MusicDirectorCandidatePersistenceService,
    MusicDirectorPublicService,
    WorkspaceService,
)
from backend.services.workspace.music_director_public_service import (
    MusicDirectorPublicError,
    MusicDirectorPublicErrorCode,
)
from backend.tests.test_music_director_candidate_persistence_service import Graph


def _seed(client: TestClient):
    workspace_service = client.app.state.workspace_service
    assert isinstance(workspace_service, WorkspaceService)
    owner_id = uuid4()
    workspace = workspace_service.create_workspace(owner_id=owner_id, name="Director")
    project = workspace_service.create_project(
        workspace_id=workspace.workspace_id,
        title="Director project",
        created_by=owner_id,
    )
    with client.app.state.session_factory() as session, session.begin():
        snapshot = CompositionSnapshot(
            project_id=project.project_id,
            snapshot_version=1,
            mix_settings_snapshot={},
            provider_versions={},
            model_manifest_ids={},
            created_by=owner_id,
        )
        session.add(snapshot)
        session.flush()
        snapshot_id = snapshot.composition_snapshot_id
    return project.project_id, snapshot_id


def _create(client: TestClient, project_id, snapshot_id, *, key="director", count=None):
    intent = {"instruction": "Create two restrained alternatives"}
    if count is not None:
        intent["candidate_count"] = count
    return client.post(
        f"/api/v1/projects/{project_id}/music-director/runs",
        headers={"Idempotency-Key": key},
        json={"composition_snapshot_id": str(snapshot_id), "music_intent": intent},
    )


def test_create_defaults_to_two_and_exact_replay_is_safe(client: TestClient) -> None:
    project_id, snapshot_id = _seed(client)
    first = _create(client, project_id, snapshot_id)
    replay = _create(client, project_id, snapshot_id)
    assert first.status_code == replay.status_code == 201
    assert first.json()["data"] == replay.json()["data"]
    assert first.json()["data"]["candidate_count"] == 2
    assert first.json()["data"]["status"] == "queued"
    serialized = str(first.json())
    for secret in ("claim_token", "client_execution_key", "storage_key", "provider_payload"):
        assert secret not in serialized


def test_create_bounds_unknown_fields_conflict_and_new_key(client: TestClient) -> None:
    project_id, snapshot_id = _seed(client)
    for count in (0, 5):
        assert (
            _create(client, project_id, snapshot_id, key=f"bad-{count}", count=count).status_code
            == 422
        )
    unknown = client.post(
        f"/api/v1/projects/{project_id}/music-director/runs",
        headers={"Idempotency-Key": "unknown"},
        json={
            "composition_snapshot_id": str(snapshot_id),
            "music_intent": {"instruction": "x"},
            "provider_id": "arbitrary",
        },
    )
    assert unknown.status_code == 422
    first = _create(client, project_id, snapshot_id, key="same", count=1)
    conflict = _create(client, project_id, snapshot_id, key="same", count=4)
    second = _create(client, project_id, snapshot_id, key="new", count=1)
    assert first.status_code == second.status_code == 201
    assert conflict.status_code == 409
    assert first.json()["data"]["job_id"] != second.json()["data"]["job_id"]


def test_project_scoped_cancel_reuses_job_authority(client: TestClient) -> None:
    project_id, snapshot_id = _seed(client)
    created = _create(client, project_id, snapshot_id)
    job_id = created.json()["data"]["job_id"]
    cancelled = client.post(f"/api/v1/projects/{project_id}/music-director/jobs/{job_id}/cancel")
    replay = client.post(f"/api/v1/projects/{project_id}/music-director/jobs/{job_id}/cancel")
    assert cancelled.status_code == replay.status_code == 200
    assert cancelled.json()["status"] == replay.json()["status"] == "cancelled"
    with client.app.state.session_factory() as session:
        assert session.get(Job, uuid4()) is None


def test_run_is_not_fabricated_before_worker_completion(client: TestClient) -> None:
    project_id, snapshot_id = _seed(client)
    _create(client, project_id, snapshot_id)
    response = client.get(f"/api/v1/projects/{project_id}/music-director/runs/{uuid4()}")
    assert response.status_code == 404


def test_fresh_session_read_orders_complete_set_and_selects_with_cas(tmp_path) -> None:
    graph = Graph(tmp_path)
    persisted = MusicDirectorCandidatePersistenceService(graph.factory).persist(graph.request)
    service = MusicDirectorPublicService(graph.factory, JobService(graph.factory))
    with pytest.raises(MusicDirectorPublicError) as pending:
        service.get_run(
            effective_owner_id=graph.owner,
            project_id=graph.request.project_id,
            run_id=persisted.run.run_id,
        )
    assert pending.value.code is MusicDirectorPublicErrorCode.NOT_READY
    with graph.factory() as session, session.begin():
        session.get(Job, graph.request.job_id).status = "succeeded"
    aggregate = service.get_run(
        effective_owner_id=graph.owner,
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
    )
    assert [item.ordinal for item in aggregate.candidates] == [0, 1]
    first = aggregate.candidates[0]
    detail_aggregate, detail = service.get_candidate(
        effective_owner_id=graph.owner,
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
        candidate_id=first.candidate_id,
    )
    assert detail_aggregate.run.run_id == persisted.run.run_id
    assert detail.proposal_artifact_id == first.proposal_artifact_id
    selected = service.select_candidate(
        effective_owner_id=graph.owner,
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
        candidate_id=first.candidate_id,
        expected_version=0,
    )
    replay = service.select_candidate(
        effective_owner_id=graph.owner,
        project_id=graph.request.project_id,
        run_id=persisted.run.run_id,
        candidate_id=first.candidate_id,
        expected_version=0,
    )
    assert selected.selected_candidate_id == replay.selected_candidate_id == first.candidate_id
    assert selected.version == replay.version == 1
    assert graph.revision() == 7
    graph.engine.dispose()


def test_apply_requires_strict_cas_body_and_idempotency_key(client: TestClient) -> None:
    project_id, run_id, candidate_id = uuid4(), uuid4(), uuid4()
    path = (
        f"/api/v1/projects/{project_id}/music-director/runs/{run_id}"
        f"/candidates/{candidate_id}/apply"
    )
    body = {
        "expected_run_version": 0,
        "expected_working_composition_revision": 0,
    }

    operation = client.app.openapi()["paths"][
        "/api/v1/projects/{project_id}/music-director/runs/{run_id}/candidates/{candidate_id}/apply"
    ]["post"]
    idempotency = next(
        item for item in operation["parameters"] if item["name"] == "Idempotency-Key"
    )
    assert idempotency["in"] == "header"
    assert idempotency["required"] is True
    with pytest.raises(ValidationError):
        MusicDirectorApplyRequest.model_validate({**body, "unexpected": True})
    response = client.post(
        path,
        headers={"Idempotency-Key": "apply-contract"},
        json=body,
    )
    assert response.status_code == 409
    assert response.json()["error"]["error_code"] == "WORKSPACE_BOOTSTRAP_REQUIRED"
