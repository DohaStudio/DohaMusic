"""Asset Resource API와 Owner scope·transaction 계약 검증."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api.v1.dependencies import REQUEST_ID_HEADER
from backend.core.exceptions import ResourceConflictError
from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    ProjectAsset,
)
from backend.repositories.workspace import AssetRepository
from backend.services.workspace import AssetService, WorkspaceService


def _workspace_service(client: TestClient) -> WorkspaceService:
    service = client.app.state.workspace_service
    assert isinstance(service, WorkspaceService)
    return service


def _asset_service(client: TestClient) -> AssetService:
    service = client.app.state.asset_service
    assert isinstance(service, AssetService)
    return service


def _bootstrap(client: TestClient, *, name: str = "Asset API 작업실"):
    owner_id = uuid4()
    workspace = _workspace_service(client).create_workspace(
        owner_id=owner_id,
        name=name,
    )
    return owner_id, workspace


def _count(client: TestClient, entity_type: type[object]) -> int:
    with client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(entity_type)) or 0


def _stored_asset(client: TestClient, asset_id: UUID) -> Asset | None:
    with client.app.state.session_factory() as session:
        return AssetRepository(session).get_asset(asset_id, include_deleted=True)


def test_asset_endpoints_require_explicit_bootstrap(client: TestClient) -> None:
    asset_id = uuid4()
    requests = (
        ("GET", "/api/v1/assets", None),
        ("POST", "/api/v1/assets", {"asset_type": "music"}),
        ("GET", f"/api/v1/assets/{asset_id}", None),
        ("PATCH", f"/api/v1/assets/{asset_id}", {"lifecycle_status": "archived"}),
        ("DELETE", f"/api/v1/assets/{asset_id}", None),
    )

    for method, path, body in requests:
        response = client.request(method, path, json=body)

        assert response.status_code == 409
        assert response.json()["error"]["error_code"] == (
            "WORKSPACE_BOOTSTRAP_REQUIRED"
        )
        assert response.headers[REQUEST_ID_HEADER]


def test_asset_create_derives_owner_and_creates_only_asset(client: TestClient) -> None:
    owner_id, workspace = _bootstrap(client)

    response = client.post(
        "/api/v1/assets",
        json={
            "workspace_id": str(workspace.workspace_id),
            "asset_type": "music",
            "lifecycle_status": "draft",
        },
        headers={REQUEST_ID_HEADER: "asset-create-request"},
    )

    assert response.status_code == 201
    assert response.headers[REQUEST_ID_HEADER] == "asset-create-request"
    body = response.json()
    assert body["request_id"] == "asset-create-request"
    assert set(body["data"]) == {
        "asset_id",
        "workspace_id",
        "asset_type",
        "selected_asset_version_id",
        "lifecycle_status",
        "created_at",
        "updated_at",
    }
    assert body["data"]["workspace_id"] == str(workspace.workspace_id)
    assert body["data"]["asset_type"] == "music"
    assert body["data"]["lifecycle_status"] == "draft"
    asset = _stored_asset(client, UUID(body["data"]["asset_id"]))
    assert asset is not None and asset.owner_id == owner_id
    assert _count(client, Asset) == 1
    assert _count(client, AssetVersion) == 0
    assert _count(client, Artifact) == 0
    assert _count(client, ProjectAsset) == 0

    unscoped = client.post("/api/v1/assets", json={"asset_type": "lyrics"})
    assert unscoped.status_code == 201
    assert unscoped.json()["data"]["workspace_id"] is None
    unscoped_asset = _stored_asset(client, UUID(unscoped.json()["data"]["asset_id"]))
    assert unscoped_asset is not None and unscoped_asset.owner_id == owner_id


def test_asset_create_rejects_internal_fields(client: TestClient) -> None:
    _bootstrap(client)
    forbidden: list[tuple[str, Callable[[], object]]] = [
        ("owner_id", lambda: str(uuid4())),
        ("created_by", lambda: str(uuid4())),
        ("asset_id", lambda: str(uuid4())),
        ("created_at", lambda: "2026-08-08T00:00:00Z"),
        ("deleted_at", lambda: None),
        ("selected_asset_version_id", lambda: str(uuid4())),
        ("project_id", lambda: str(uuid4())),
    ]

    for field, value in forbidden:
        response = client.post(
            "/api/v1/assets",
            json={"asset_type": "music", field: value()},
        )
        assert response.status_code == 422
        assert response.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _count(client, Asset) == 0


def test_asset_list_uses_owner_scope_filters_and_cursor(client: TestClient) -> None:
    owner_id, workspace = _bootstrap(client)
    service = _asset_service(client)
    expected: list[Asset] = []
    for index in range(6):
        expected.append(
            service.create_asset(
                owner_id=owner_id,
                workspace_id=workspace.workspace_id if index < 4 else None,
                asset_type=AssetType.MUSIC if index % 2 == 0 else AssetType.VOCAL,
            )
        )
    service.delete_asset(expected[1].asset_id)
    other_owner = uuid4()
    service.create_asset(
        owner_id=other_owner,
        workspace_id=None,
        asset_type=AssetType.MUSIC,
    )

    returned: list[dict[str, object]] = []
    path = "/api/v1/assets?limit=2"
    while path:
        response = client.get(path)
        assert response.status_code == 200
        body = response.json()
        returned.extend(body["data"])
        assert (body["pagination"]["next_cursor"] is not None) == body["pagination"][
            "has_more"
        ]
        path = body["links"]["next"]

    expected_ids = [
        item.asset_id
        for item in sorted(
            [item for item in expected if item.asset_id != expected[1].asset_id],
            key=lambda item: (item.created_at, item.asset_id),
            reverse=True,
        )
    ]
    returned_ids = [UUID(str(item["asset_id"])) for item in returned]
    assert returned_ids == expected_ids
    assert len(returned_ids) == len(set(returned_ids)) == 5
    assert all("owner_id" not in item for item in returned)

    filtered = client.get(
        "/api/v1/assets",
        params={
            "workspace_id": str(workspace.workspace_id),
            "asset_type": "music",
        },
    )
    assert filtered.status_code == 200
    assert [item["asset_type"] for item in filtered.json()["data"]] == [
        "music",
        "music",
    ]
    assert all(
        item["workspace_id"] == str(workspace.workspace_id)
        for item in filtered.json()["data"]
    )


def test_asset_cursor_and_limit_errors_are_publicly_stable(client: TestClient) -> None:
    owner_id, workspace = _bootstrap(client)
    for _ in range(3):
        _asset_service(client).create_asset(
            owner_id=owner_id,
            workspace_id=workspace.workspace_id,
            asset_type=AssetType.MUSIC,
        )
    first = client.get(
        "/api/v1/assets",
        params={"workspace_id": str(workspace.workspace_id), "limit": 2},
    )
    cursor = first.json()["pagination"]["next_cursor"]

    changed_filter = client.get(
        "/api/v1/assets",
        params={
            "workspace_id": str(workspace.workspace_id),
            "limit": 2,
            "cursor": cursor,
            "asset_type": "music",
        },
    )
    invalid_cursor = client.get("/api/v1/assets?cursor=invalid&limit=2")
    invalid_limit = client.get("/api/v1/assets?limit=0")

    assert changed_filter.status_code == 422
    assert changed_filter.json()["error"]["error_code"] == "INVALID_CURSOR"
    assert invalid_cursor.status_code == 422
    assert invalid_cursor.json()["error"]["error_code"] == "INVALID_CURSOR"
    assert invalid_limit.status_code == 422
    assert invalid_limit.json()["error"]["error_code"] == "INVALID_LIMIT"


def test_asset_detail_patch_and_delete_contract(client: TestClient) -> None:
    owner_id, workspace = _bootstrap(client)
    asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.RECORDING,
    )

    detail = client.get(f"/api/v1/assets/{asset.asset_id}")
    patched = client.patch(
        f"/api/v1/assets/{asset.asset_id}",
        json={"lifecycle_status": "archived"},
    )
    deleted = client.delete(f"/api/v1/assets/{asset.asset_id}")
    missing = client.get(f"/api/v1/assets/{asset.asset_id}")

    assert detail.status_code == 200
    assert detail.json()["data"]["asset_type"] == "recording"
    assert patched.status_code == 200
    assert patched.json()["data"]["lifecycle_status"] == "archived"
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert deleted.headers[REQUEST_ID_HEADER]
    assert missing.status_code == 404
    assert missing.json()["error"]["error_code"] == "ASSET_NOT_FOUND"


def test_asset_patch_allows_only_lifecycle_status(client: TestClient) -> None:
    forbidden_payloads: list[dict[str, object]] = [
        {},
        {"lifecycle_status": None},
        {"owner_id": str(uuid4())},
        {"created_by": str(uuid4())},
        {"deleted_at": None},
        {"asset_id": str(uuid4())},
        {"created_at": "2026-08-08T00:00:00Z"},
        {"workspace_id": str(uuid4())},
        {"asset_type": "vocal"},
        {"selected_asset_version_id": str(uuid4())},
    ]
    owner_id, workspace = _bootstrap(client)
    asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )

    for payload in forbidden_payloads:
        response = client.patch(f"/api/v1/assets/{asset.asset_id}", json=payload)
        assert response.status_code == 422
        assert response.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _asset_service(client).get_asset(asset.asset_id).lifecycle_status == "active"


def test_asset_delete_preserves_versions_artifacts_and_project_links(
    client: TestClient,
) -> None:
    owner_id, workspace = _bootstrap(client)
    workspace_service = _workspace_service(client)
    asset_service = _asset_service(client)
    project = workspace_service.create_project(
        workspace_id=workspace.workspace_id,
        title="Asset 보존 곡",
        created_by=owner_id,
    )
    asset = asset_service.create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    version = asset_service.create_asset_version(
        asset_id=asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=owner_id,
    )
    asset_service.register_artifact(
        asset_version_id=version.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=0,
        artifact_checksum="a" * 64,
        producer_type="user",
        retention_status="active",
    )
    workspace_service.attach_asset(
        project_id=project.project_id,
        asset_id=asset.asset_id,
        display_order=0,
    )

    response = client.delete(f"/api/v1/assets/{asset.asset_id}")

    assert response.status_code == 204
    stored = _stored_asset(client, asset.asset_id)
    assert stored is not None and stored.deleted_at is not None
    assert _count(client, AssetVersion) == 1
    assert _count(client, Artifact) == 1
    assert _count(client, ProjectAsset) == 1


def test_asset_scope_uuid_query_and_conflict_mapping(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    other_owner = uuid4()
    other_workspace = _workspace_service(client).create_workspace(
        owner_id=other_owner,
        name="다른 Owner 작업실",
    )
    owner_id, workspace = _bootstrap(client)
    foreign_asset = _asset_service(client).create_asset(
        owner_id=other_owner,
        workspace_id=other_workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )

    assert client.get(f"/api/v1/assets/{foreign_asset.asset_id}").status_code == 404
    assert client.get("/api/v1/assets/not-a-uuid").status_code == 422
    owner_query = client.get("/api/v1/assets", params={"owner_id": str(owner_id)})
    assert owner_query.status_code == 422
    assert owner_query.json()["error"]["error_code"] == "INVALID_INPUT"
    cross_scope = client.get(
        "/api/v1/assets",
        params={"workspace_id": str(other_workspace.workspace_id)},
    )
    assert cross_scope.status_code == 404
    assert cross_scope.json()["error"]["error_code"] == "WORKSPACE_NOT_FOUND"

    def conflict(**_kwargs):
        raise ResourceConflictError("Asset")

    monkeypatch.setattr(_asset_service(client), "create_asset", conflict)
    response = client.post(
        "/api/v1/assets",
        json={"workspace_id": str(workspace.workspace_id), "asset_type": "music"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["error_code"] == "ASSET_CONFLICT"


def test_asset_service_transactions_roll_back_api_mutations(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    owner_id, workspace = _bootstrap(client)
    repository_add = AssetRepository.add_asset

    def fail_after_add(repository: AssetRepository, asset: Asset) -> Asset:
        repository_add(repository, asset)
        raise RuntimeError("injected create failure")

    monkeypatch.setattr(AssetRepository, "add_asset", fail_after_add)
    with pytest.raises(RuntimeError, match="injected create failure"):
        client.post(
            "/api/v1/assets",
            json={"workspace_id": str(workspace.workspace_id), "asset_type": "music"},
        )
    assert _count(client, Asset) == 0
    monkeypatch.setattr(AssetRepository, "add_asset", repository_add)

    asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    repository_delete = AssetRepository.soft_delete_asset

    def fail_after_delete(repository: AssetRepository, target: Asset) -> Asset:
        repository_delete(repository, target)
        raise RuntimeError("injected delete failure")

    monkeypatch.setattr(AssetRepository, "soft_delete_asset", fail_after_delete)
    with pytest.raises(RuntimeError, match="injected delete failure"):
        client.delete(f"/api/v1/assets/{asset.asset_id}")
    stored = _stored_asset(client, asset.asset_id)
    assert stored is not None and stored.deleted_at is None
