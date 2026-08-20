"""D1-A Project Composition selection과 aggregate API 계약 검증."""

from __future__ import annotations

from collections import Counter
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from backend.models.workspace import (
    Artifact,
    Asset,
    AssetVersion,
    CompositionSnapshot,
    ProjectCompositionSelection,
    SnapshotItem,
)
from backend.repositories.workspace import CompositionRepository
from backend.tests.test_composition_snapshot_api import (
    _asset_service,
    _body,
    _composition_service,
    _post,
    _seed_graph,
)


def _entity_count(client: TestClient, entity: type[object]) -> int:
    with client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(entity)) or 0


def _select(client: TestClient, project_id: object, snapshot_id: object | None):
    return client.patch(
        f"/api/v1/projects/{project_id}/composition-selection",
        json={"selected_snapshot_id": str(snapshot_id) if snapshot_id else None},
    )


def test_composition_aggregate_requires_bootstrap(client: TestClient) -> None:
    project_id = uuid4()
    response = client.get(f"/api/v1/projects/{project_id}/composition")
    mutation = _select(client, project_id, uuid4())

    assert response.status_code == mutation.status_code == 409
    assert response.json()["error"]["error_code"] == "WORKSPACE_BOOTSTRAP_REQUIRED"
    assert mutation.json()["error"]["error_code"] == "WORKSPACE_BOOTSTRAP_REQUIRED"


def test_empty_selection_required_and_explicit_selection_persist(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    empty = client.get(f"/api/v1/projects/{graph.project_id}/composition")
    assert empty.status_code == 200
    assert empty.json()["data"]["state"] == "empty"
    assert empty.json()["data"]["snapshot"] is None

    created = _post(
        client,
        graph,
        key="d1-a-first",
        body=_body(
            graph,
            mix_settings_snapshot={"gain": -2},
            provider_versions={"audio": "1.0"},
            model_manifest_ids={"audio": "manifest-1"},
        ),
    ).json()["data"]
    snapshot_id = created["composition_snapshot_id"]
    required = client.get(f"/api/v1/projects/{graph.project_id}/composition")
    assert required.status_code == 200
    assert required.json()["data"]["state"] == "selection_required"

    selected = _select(client, graph.project_id, snapshot_id)
    replay = _select(client, graph.project_id, snapshot_id)
    assert selected.status_code == replay.status_code == 200
    assert selected.json()["data"] == replay.json()["data"]

    with client.app.state.session_factory() as session:
        persisted = session.get(ProjectCompositionSelection, graph.project_id)
        assert persisted is not None
        assert str(persisted.selected_composition_snapshot_id) == snapshot_id

    ready = client.get(f"/api/v1/projects/{graph.project_id}/composition")
    data = ready.json()["data"]
    assert ready.status_code == 200
    assert data["state"] == "ready"
    assert data["selection"] == {
        "selected_snapshot_id": snapshot_id,
        "resolved_snapshot_id": snapshot_id,
        "resolution": "selected",
        "is_current": True,
    }
    assert data["mix_settings_snapshot"] == {"gain": -2}
    assert data["lineage"]["provider_versions"] == {"audio": "1.0"}
    assert data["lineage"]["model_manifest_ids"] == {"audio": "manifest-1"}


def test_aggregate_preserves_exact_version_safe_artifact_and_projection(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    second_version = _asset_service(client).create_asset_version(
        asset_id=graph.asset_id,
        version_origin="user_edited",
        settings_snapshot={"revision": 2},
        parent_asset_version_id=graph.asset_version_id,
        created_by=graph.owner_id,
    )
    created = _post(
        client,
        graph,
        key="d1-a-exact-version",
        body=_body(
            graph,
            items=[
                {
                    "asset_version_id": str(graph.asset_version_id),
                    "item_role": "lyrics",
                    "sort_order": 1,
                },
                {
                    "asset_version_id": str(second_version.asset_version_id),
                    "item_role": "music",
                    "sort_order": 0,
                },
            ],
        ),
    ).json()["data"]
    snapshot_id = created["composition_snapshot_id"]
    artifact_id = uuid4()
    with client.app.state.session_factory.begin() as session:
        session.add(
            Artifact(
                artifact_id=artifact_id,
                asset_version_id=second_version.asset_version_id,
                artifact_kind="mix_preview",
                media_type="audio/wav",
                size_bytes=128,
                checksum_algorithm="sha256",
                artifact_checksum="a" * 64,
                producer_type="test",
                producer_id=None,
                run_id=None,
                retention_status="active",
            )
        )
    assert _select(client, graph.project_id, snapshot_id).status_code == 200

    response = client.get(f"/api/v1/projects/{graph.project_id}/composition")
    data = response.json()["data"]
    assert response.status_code == 200
    assert [(item["item_role"], item["sort_order"]) for item in data["items"]] == [
        ("lyrics", 1),
        ("music", 0),
    ]
    music = data["items"][1]
    assert music["asset_version"]["asset_version_id"] == str(
        second_version.asset_version_id
    )
    assert music["asset_version"]["parent_asset_version_id"] == str(
        graph.asset_version_id
    )
    artifact = music["artifacts"][0]
    assert artifact["artifact_id"] == str(artifact_id)
    assert artifact["content_url"] == f"/api/v1/artifacts/{artifact_id}/content"
    assert artifact["download_url"] == f"/api/v1/artifacts/{artifact_id}/download"
    assert not {"path", "storage_key", "locator", "credential"}.intersection(artifact)
    assert len(data["track_projections"]) == 1
    projection = data["track_projections"][0]
    assert projection["projection_id"] == projection["snapshot_item_id"]
    assert projection["identity_scope"] == "snapshot"
    assert "track_id" not in projection
    assert data["section_projection"] == {
        "availability": "not_available",
        "items": [],
    }


def test_query_override_never_changes_selection_and_latest_is_not_current(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    first_id = _post(client, graph, key="d1-a-history-1").json()["data"][
        "composition_snapshot_id"
    ]
    second_id = _post(client, graph, key="d1-a-history-2").json()["data"][
        "composition_snapshot_id"
    ]
    assert _select(client, graph.project_id, first_id).status_code == 200

    override = client.get(
        f"/api/v1/projects/{graph.project_id}/composition",
        params={"composition_snapshot_id": second_id},
    ).json()["data"]
    assert override["selection"] == {
        "selected_snapshot_id": first_id,
        "resolved_snapshot_id": second_id,
        "resolution": "requested",
        "is_current": False,
    }
    current = client.get(f"/api/v1/projects/{graph.project_id}/composition").json()[
        "data"
    ]
    assert current["snapshot"]["composition_snapshot_id"] == first_id
    assert current["snapshot"]["snapshot_version"] == 1


def test_selection_and_override_enforce_project_and_owner_privacy(
    client: TestClient,
) -> None:
    first = _seed_graph(client)
    first_snapshot = _post(client, first, key="d1-a-scope-1").json()["data"][
        "composition_snapshot_id"
    ]
    second = _seed_graph(
        client,
        owner_id=first.owner_id,
        workspace_id=first.workspace_id,
    )
    second_snapshot = _post(client, second, key="d1-a-scope-2").json()["data"][
        "composition_snapshot_id"
    ]

    wrong_selection = _select(client, first.project_id, second_snapshot)
    wrong_override = client.get(
        f"/api/v1/projects/{first.project_id}/composition",
        params={"composition_snapshot_id": second_snapshot},
    )
    assert wrong_selection.status_code == wrong_override.status_code == 404
    assert wrong_selection.json()["error"]["error_code"] == (
        "COMPOSITION_SNAPSHOT_NOT_FOUND"
    )
    assert wrong_override.json()["error"]["error_code"] == (
        "COMPOSITION_SNAPSHOT_NOT_FOUND"
    )

    other_owner = _seed_graph(client)
    foreign = client.get(f"/api/v1/projects/{first.project_id}/composition")
    foreign_mutation = _select(client, first.project_id, first_snapshot)
    assert foreign.status_code == foreign_mutation.status_code == 404
    assert foreign.json()["error"]["error_code"] == "PROJECT_NOT_FOUND"
    assert other_owner.owner_id != first.owner_id


def test_get_has_no_side_effects_and_selection_is_atomic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    graph = _seed_graph(client)
    snapshot_id = _post(client, graph, key="d1-a-no-side-effect").json()["data"][
        "composition_snapshot_id"
    ]
    counts_before = {
        entity: _entity_count(client, entity)
        for entity in (Asset, AssetVersion, CompositionSnapshot, SnapshotItem)
    }
    assert (
        client.get(f"/api/v1/projects/{graph.project_id}/composition").status_code
        == 200
    )
    assert counts_before == {
        entity: _entity_count(client, entity) for entity in counts_before
    }
    assert _entity_count(client, ProjectCompositionSelection) == 0

    original = CompositionRepository.set_project_selection

    def fail_after_flush(
        repository: CompositionRepository, project_id: object, selected_id: object
    ):
        original(repository, project_id, selected_id)  # type: ignore[arg-type]
        raise RuntimeError("forced rollback")

    monkeypatch.setattr(
        CompositionRepository, "set_project_selection", fail_after_flush
    )
    with pytest.raises(RuntimeError, match="forced rollback"):
        _composition_service(client).set_project_selection(
            graph.project_id,
            selected_snapshot_id=UUID(snapshot_id),
            effective_owner_id=graph.owner_id,
        )
    assert _entity_count(client, ProjectCompositionSelection) == 0


def test_openapi_adds_only_d1_a_operations_without_new_duplicates(
    client: TestClient,
) -> None:
    schema = client.app.openapi()
    assert "get" in schema["paths"]["/api/v1/projects/{project_id}/composition"]
    assert (
        "patch"
        in schema["paths"]["/api/v1/projects/{project_id}/composition-selection"]
    )
    operation_ids = [
        operation["operationId"]
        for path_item in schema["paths"].values()
        for operation in path_item.values()
        if isinstance(operation, dict) and "operationId" in operation
    ]
    duplicates = {
        operation_id
        for operation_id, count in Counter(operation_ids).items()
        if count > 1
    }
    assert {
        "get_project_composition",
        "update_project_composition_selection",
    }.isdisjoint(duplicates)


def test_aggregate_read_query_plan_uses_bounded_index_lookups(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    second_version = _asset_service(client).create_asset_version(
        asset_id=graph.asset_id,
        version_origin="user_edited",
        settings_snapshot={"revision": 2},
        parent_asset_version_id=graph.asset_version_id,
        created_by=graph.owner_id,
    )
    _post(client, graph, key="d1-a-query-plan-history")
    snapshot_id = _post(
        client,
        graph,
        key="d1-a-query-plan-selected",
        body=_body(
            graph,
            items=[
                {
                    "asset_version_id": str(graph.asset_version_id),
                    "item_role": "lyrics",
                    "sort_order": 0,
                },
                {
                    "asset_version_id": str(second_version.asset_version_id),
                    "item_role": "music",
                    "sort_order": 0,
                },
            ],
        ),
    ).json()["data"]["composition_snapshot_id"]
    with client.app.state.session_factory.begin() as session:
        for offset, version_id in enumerate(
            (graph.asset_version_id, second_version.asset_version_id)
        ):
            session.add(
                Artifact(
                    artifact_id=uuid4(),
                    asset_version_id=version_id,
                    artifact_kind="query_plan_fixture",
                    media_type="audio/wav",
                    size_bytes=offset + 1,
                    checksum_algorithm="sha256",
                    artifact_checksum=f"{offset + 1:064x}",
                    producer_type="test",
                    producer_id=None,
                    run_id=None,
                    retention_status="active",
                )
            )
    assert _select(client, graph.project_id, snapshot_id).status_code == 200
    statements = (
        (
            "selection",
            "SELECT * FROM project_composition_selections WHERE project_id = :project_id",
            {"project_id": graph.project_id.hex},
        ),
        (
            "snapshot",
            (
                "SELECT * FROM composition_snapshots "
                "WHERE project_id = :project_id AND composition_snapshot_id = :snapshot_id"
            ),
            {"project_id": graph.project_id.hex, "snapshot_id": UUID(snapshot_id).hex},
        ),
        (
            "items",
            (
                "SELECT * FROM snapshot_items "
                "WHERE composition_snapshot_id = :snapshot_id "
                "ORDER BY item_role, sort_order LIMIT 100"
            ),
            {"snapshot_id": UUID(snapshot_id).hex},
        ),
        (
            "versions",
            "SELECT * FROM asset_versions WHERE asset_version_id IN (:first, :second)",
            {
                "first": graph.asset_version_id.hex,
                "second": second_version.asset_version_id.hex,
            },
        ),
        (
            "artifacts",
            (
                "SELECT * FROM artifacts WHERE asset_version_id IN (:first, :second) "
                "ORDER BY asset_version_id, created_at, artifact_id LIMIT 257"
            ),
            {
                "first": graph.asset_version_id.hex,
                "second": second_version.asset_version_id.hex,
            },
        ),
    )
    with client.app.state.session_factory() as session:
        plans = {
            name: [
                str(row[3])
                for row in session.execute(text(f"EXPLAIN QUERY PLAN {sql}"), params)
            ]
            for name, sql, params in statements
        }

    for details in plans.values():
        assert any("SEARCH" in detail and "INDEX" in detail for detail in details)
        assert not any(detail.startswith("SCAN ") for detail in details)
        assert not any("USE TEMP B-TREE" in detail for detail in details)
