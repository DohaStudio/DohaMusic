"""ProjectAsset Resource API 계약과 transaction 회귀 검증."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api.v1.dependencies import REQUEST_ID_HEADER
from backend.models.workspace import Asset, AssetType, AssetVersion, ProjectAsset
from backend.repositories.workspace import WorkspaceRepository
from backend.services.workspace import AssetService, WorkspaceService


@dataclass(frozen=True)
class ApiGraph:
    workspace_id: UUID
    owner_id: UUID
    project_id: UUID
    asset_id: UUID


def _workspace_service(client: TestClient) -> WorkspaceService:
    service = client.app.state.workspace_service
    assert isinstance(service, WorkspaceService)
    return service


def _asset_service(client: TestClient) -> AssetService:
    return AssetService(client.app.state.session_factory)


def _seed_graph(client: TestClient) -> ApiGraph:
    owner_id = uuid4()
    workspace = _workspace_service(client).create_workspace(
        owner_id=owner_id,
        name="ProjectAsset API 작업실",
    )
    project = _workspace_service(client).create_project(
        workspace_id=workspace.workspace_id,
        title="ProjectAsset API 곡",
        created_by=owner_id,
    )
    asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    return ApiGraph(
        workspace_id=workspace.workspace_id,
        owner_id=owner_id,
        project_id=project.project_id,
        asset_id=asset.asset_id,
    )


def _create_asset(client: TestClient, graph: ApiGraph) -> Asset:
    return _asset_service(client).create_asset(
        owner_id=graph.owner_id,
        workspace_id=graph.workspace_id,
        asset_type=AssetType.MUSIC,
    )


def _link(
    client: TestClient,
    project_id: UUID,
    asset_id: UUID,
    *,
    include_deleted: bool = False,
) -> ProjectAsset | None:
    with client.app.state.session_factory() as session:
        return WorkspaceRepository(session).find_project_asset(
            project_id,
            asset_id,
            include_deleted=include_deleted,
        )


def _count(client: TestClient, entity_type: type[object]) -> int:
    with client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(entity_type)) or 0


def test_project_asset_endpoints_require_explicit_bootstrap(
    client: TestClient,
) -> None:
    project_id = uuid4()
    asset_id = uuid4()
    requests = (
        ("GET", f"/api/v1/projects/{project_id}/assets", None),
        (
            "POST",
            f"/api/v1/projects/{project_id}/assets",
            {"asset_id": str(asset_id), "display_order": 0},
        ),
        ("DELETE", f"/api/v1/projects/{project_id}/assets/{asset_id}", None),
    )

    for method, path, body in requests:
        response = client.request(method, path, json=body)

        assert response.status_code == 409
        assert response.json()["error"]["error_code"] == (
            "WORKSPACE_BOOTSTRAP_REQUIRED"
        )
        assert response.headers[REQUEST_ID_HEADER]


def test_project_asset_list_uses_cursor_without_duplicates_or_omissions(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    service = _workspace_service(client)
    assets = [
        graph.asset_id,
        *[_create_asset(client, graph).asset_id for _ in range(5)],
    ]
    links = [
        service.attach_asset(
            project_id=graph.project_id,
            asset_id=asset_id,
            role=f"role-{index}",
            display_order=display_order,
        )
        for index, (asset_id, display_order) in enumerate(
            zip(assets, (0, 0, 1, 1, 2, 3), strict=True)
        )
    ]
    service.detach_asset(project_id=graph.project_id, asset_id=assets[4])

    pages: list[dict[str, object]] = []
    path = f"/api/v1/projects/{graph.project_id}/assets?limit=2"
    while path:
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        pages.extend(body["data"])
        assert body["pagination"]["limit"] == 2
        assert (body["pagination"]["next_cursor"] is not None) == body["pagination"][
            "has_more"
        ]
        path = body["links"]["next"]

    returned_ids = [UUID(str(item["asset_id"])) for item in pages]
    assert len(returned_ids) == 5
    assert len(set(returned_ids)) == 5
    assert assets[4] not in returned_ids
    expected = [
        item.asset_id
        for item in sorted(
            [link for link in links if link.asset_id != assets[4]],
            key=lambda item: (item.display_order, item.project_asset_id),
        )
    ]
    assert returned_ids == expected
    assert all(set(item) == {"asset_id", "role", "display_order"} for item in pages)

    empty_project = service.create_project(
        workspace_id=graph.workspace_id,
        title="빈 곡",
        created_by=graph.owner_id,
    )
    empty = client.get(f"/api/v1/projects/{empty_project.project_id}/assets")
    assert empty.status_code == 200
    assert empty.json()["data"] == []
    assert empty.json()["pagination"]["next_cursor"] is None


def test_project_asset_cursor_cannot_be_reused_for_another_project(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    service = _workspace_service(client)
    for index in range(3):
        asset = graph.asset_id if index == 0 else _create_asset(client, graph).asset_id
        service.attach_asset(
            project_id=graph.project_id,
            asset_id=asset,
            display_order=index,
        )
    first = client.get(f"/api/v1/projects/{graph.project_id}/assets?limit=2")
    cursor = first.json()["pagination"]["next_cursor"]
    other_project = service.create_project(
        workspace_id=graph.workspace_id,
        title="다른 곡",
        created_by=graph.owner_id,
    )

    reused = client.get(
        f"/api/v1/projects/{other_project.project_id}/assets",
        params={"limit": 2, "cursor": cursor},
    )

    assert reused.status_code == 422
    assert reused.json()["error"]["error_code"] == "INVALID_CURSOR"


def test_project_asset_create_conflict_and_restore_contract(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    path = f"/api/v1/projects/{graph.project_id}/assets"
    asset_count = _count(client, Asset)

    created = client.post(
        path,
        json={
            "asset_id": str(graph.asset_id),
            "role": "music",
            "display_order": 3,
        },
    )
    assert created.status_code == 201
    assert created.json()["data"] == {
        "asset_id": str(graph.asset_id),
        "role": "music",
        "display_order": 3,
    }
    assert _count(client, Asset) == asset_count
    original = _link(client, graph.project_id, graph.asset_id)
    assert original is not None

    duplicate = client.post(
        path,
        json={"asset_id": str(graph.asset_id), "display_order": 4},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["error_code"] == "PROJECT_ASSET_CONFLICT"

    detached = client.delete(f"{path}/{graph.asset_id}")
    assert detached.status_code == 204
    restored = client.post(
        path,
        json={
            "asset_id": str(graph.asset_id),
            "role": "selected",
            "display_order": 1,
        },
    )
    assert restored.status_code == 201
    restored_link = _link(client, graph.project_id, graph.asset_id)
    assert restored_link is not None
    assert restored_link.project_asset_id == original.project_asset_id
    assert restored_link.role == "selected"
    assert restored_link.display_order == 1
    assert _count(client, ProjectAsset) == 1


@pytest.mark.parametrize(
    "extra",
    [
        {"project_asset_id": str(uuid4())},
        {"project_id": str(uuid4())},
        {"owner_id": str(uuid4())},
        {"created_by": str(uuid4())},
        {"deleted_at": None},
        {"created_at": "2026-08-07T00:00:00Z"},
    ],
)
def test_project_asset_create_rejects_internal_fields(
    client: TestClient,
    extra: dict[str, object],
) -> None:
    graph = _seed_graph(client)
    payload = {"asset_id": str(graph.asset_id), "display_order": 0, **extra}

    response = client.post(
        f"/api/v1/projects/{graph.project_id}/assets",
        json=payload,
    )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _link(client, graph.project_id, graph.asset_id) is None


@pytest.mark.parametrize("display_order", [True, 1.5, "1", -1])
def test_project_asset_create_rejects_invalid_display_order(
    client: TestClient,
    display_order: object,
) -> None:
    graph = _seed_graph(client)

    response = client.post(
        f"/api/v1/projects/{graph.project_id}/assets",
        json={"asset_id": str(graph.asset_id), "display_order": display_order},
    )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _link(client, graph.project_id, graph.asset_id) is None


def test_project_asset_create_maps_project_asset_and_scope_errors(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    path = f"/api/v1/projects/{graph.project_id}/assets"
    missing_project = client.post(
        f"/api/v1/projects/{uuid4()}/assets",
        json={"asset_id": str(graph.asset_id), "display_order": 0},
    )
    missing_asset = client.post(
        path,
        json={"asset_id": str(uuid4()), "display_order": 0},
    )
    assert missing_project.status_code == 404
    assert missing_project.json()["error"]["error_code"] == "PROJECT_NOT_FOUND"
    assert missing_asset.status_code == 404
    assert missing_asset.json()["error"]["error_code"] == "ASSET_NOT_FOUND"

    other_owner = uuid4()
    other_workspace = _workspace_service(client).create_workspace(
        owner_id=other_owner,
        name="다른 작업실",
    )
    other_project = _workspace_service(client).create_project(
        workspace_id=other_workspace.workspace_id,
        title="다른 곡",
        created_by=other_owner,
    )
    cross_scope = client.post(
        f"/api/v1/projects/{other_project.project_id}/assets",
        json={"asset_id": str(graph.asset_id), "display_order": 0},
    )
    assert cross_scope.status_code == 422
    assert cross_scope.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _link(client, other_project.project_id, graph.asset_id) is None


def test_project_asset_delete_preserves_asset_version_and_other_project_link(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    version = _asset_service(client).create_asset_version(
        asset_id=graph.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    other_project = _workspace_service(client).create_project(
        workspace_id=graph.workspace_id,
        title="공유 곡",
        created_by=graph.owner_id,
    )
    _workspace_service(client).attach_asset(
        project_id=graph.project_id,
        asset_id=graph.asset_id,
        display_order=0,
    )
    _workspace_service(client).attach_asset(
        project_id=other_project.project_id,
        asset_id=graph.asset_id,
        display_order=0,
    )

    response = client.delete(
        f"/api/v1/projects/{graph.project_id}/assets/{graph.asset_id}"
    )

    assert response.status_code == 204
    assert response.content == b""
    assert response.headers[REQUEST_ID_HEADER]
    removed = _link(
        client,
        graph.project_id,
        graph.asset_id,
        include_deleted=True,
    )
    assert removed is not None and removed.deleted_at is not None
    assert _link(client, other_project.project_id, graph.asset_id) is not None
    assert _asset_service(client).get_asset(graph.asset_id).asset_id == graph.asset_id
    assert _count(client, AssetVersion) == 1
    assert version.asset_version_id
    listed = client.get(f"/api/v1/projects/{graph.project_id}/assets")
    assert listed.json()["data"] == []

    missing_link = client.delete(
        f"/api/v1/projects/{graph.project_id}/assets/{graph.asset_id}"
    )
    assert missing_link.status_code == 404
    assert missing_link.json()["error"]["error_code"] == "PROJECT_ASSET_NOT_FOUND"


def test_project_asset_delete_maps_project_and_asset_not_found(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    missing_project = client.delete(
        f"/api/v1/projects/{uuid4()}/assets/{graph.asset_id}"
    )
    missing_asset = client.delete(
        f"/api/v1/projects/{graph.project_id}/assets/{uuid4()}"
    )

    assert missing_project.status_code == 404
    assert missing_project.json()["error"]["error_code"] == "PROJECT_NOT_FOUND"
    assert missing_asset.status_code == 404
    assert missing_asset.json()["error"]["error_code"] == "ASSET_NOT_FOUND"


def test_project_asset_endpoints_reject_soft_deleted_project_and_asset(
    client: TestClient,
) -> None:
    deleted_project_graph = _seed_graph(client)
    _workspace_service(client).delete_project(deleted_project_graph.project_id)

    project_responses = (
        client.get(f"/api/v1/projects/{deleted_project_graph.project_id}/assets"),
        client.post(
            f"/api/v1/projects/{deleted_project_graph.project_id}/assets",
            json={"asset_id": str(deleted_project_graph.asset_id)},
        ),
        client.delete(
            "/api/v1/projects/"
            f"{deleted_project_graph.project_id}/assets/"
            f"{deleted_project_graph.asset_id}"
        ),
    )
    assert [response.status_code for response in project_responses] == [404, 404, 404]
    assert all(
        response.json()["error"]["error_code"] == "PROJECT_NOT_FOUND"
        for response in project_responses
    )

    deleted_asset_graph = _seed_graph(client)
    _asset_service(client).delete_asset(deleted_asset_graph.asset_id)
    asset_responses = (
        client.post(
            f"/api/v1/projects/{deleted_asset_graph.project_id}/assets",
            json={"asset_id": str(deleted_asset_graph.asset_id)},
        ),
        client.delete(
            "/api/v1/projects/"
            f"{deleted_asset_graph.project_id}/assets/{deleted_asset_graph.asset_id}"
        ),
    )
    assert all(response.status_code == 404 for response in asset_responses)
    assert all(
        response.json()["error"]["error_code"] == "ASSET_NOT_FOUND"
        for response in asset_responses
    )


def test_project_asset_transactions_roll_back_partial_create_and_delete(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    graph = _seed_graph(client)
    asset_count = _count(client, Asset)
    original_add = WorkspaceRepository.add_project_asset

    def fail_after_add(
        repository: WorkspaceRepository,
        project_asset: ProjectAsset,
    ) -> ProjectAsset:
        original_add(repository, project_asset)
        raise RuntimeError("injected create failure")

    monkeypatch.setattr(WorkspaceRepository, "add_project_asset", fail_after_add)
    with pytest.raises(RuntimeError, match="injected create failure"):
        _workspace_service(client).attach_asset(
            project_id=graph.project_id,
            asset_id=graph.asset_id,
            display_order=0,
        )
    assert _link(client, graph.project_id, graph.asset_id) is None
    assert _count(client, Asset) == asset_count
    monkeypatch.setattr(WorkspaceRepository, "add_project_asset", original_add)

    _workspace_service(client).attach_asset(
        project_id=graph.project_id,
        asset_id=graph.asset_id,
        display_order=0,
    )
    original_remove = WorkspaceRepository.remove_project_asset

    def fail_after_remove(
        repository: WorkspaceRepository,
        project_asset: ProjectAsset,
    ) -> ProjectAsset:
        original_remove(repository, project_asset)
        raise RuntimeError("injected delete failure")

    monkeypatch.setattr(WorkspaceRepository, "remove_project_asset", fail_after_remove)
    with pytest.raises(RuntimeError, match="injected delete failure"):
        _workspace_service(client).detach_asset(
            project_id=graph.project_id,
            asset_id=graph.asset_id,
        )
    remaining = _link(client, graph.project_id, graph.asset_id)
    assert remaining is not None and remaining.deleted_at is None
