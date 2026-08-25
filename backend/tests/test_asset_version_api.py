"""AssetVersion Resource API와 불변 Lineage 계약 검증."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from backend.api.v1.dependencies import REQUEST_ID_HEADER
from backend.core.exceptions import ResourceConflictError
from backend.models.workspace import Artifact, AssetType, AssetVersion
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


def _bootstrap(client: TestClient):
    owner_id = uuid4()
    workspace = _workspace_service(client).create_workspace(
        owner_id=owner_id,
        name="AssetVersion API 작업실",
    )
    return owner_id, workspace


def _create_asset(client: TestClient):
    owner_id, workspace = _bootstrap(client)
    asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    return owner_id, workspace, asset


def _count(client: TestClient, entity_type: type[object]) -> int:
    with client.app.state.session_factory() as session:
        return session.scalar(select(func.count()).select_from(entity_type)) or 0


def _post_version(
    client: TestClient,
    asset_id: UUID,
    *,
    origin: str = "user_created",
    parent_id: UUID | None = None,
):
    payload: dict[str, object] = {
        "version_origin": origin,
        "settings_snapshot": {"temperature": 0.7},
        "provider_id": "local",
        "model_manifest_id": "music-model-v1",
    }
    if parent_id is not None:
        payload["parent_asset_version_id"] = str(parent_id)
    return client.post(f"/api/v1/assets/{asset_id}/versions", json=payload)


def test_asset_version_endpoints_require_explicit_bootstrap(
    client: TestClient,
) -> None:
    asset_id = uuid4()
    version_id = uuid4()
    requests = (
        ("GET", f"/api/v1/assets/{asset_id}/versions", None),
        (
            "POST",
            f"/api/v1/assets/{asset_id}/versions",
            {"version_origin": "user_created"},
        ),
        ("GET", f"/api/v1/assets/{asset_id}/versions/{version_id}", None),
    )

    for method, path, body in requests:
        response = client.request(method, path, json=body)

        assert response.status_code == 409
        assert response.json()["error"]["error_code"] == ("WORKSPACE_BOOTSTRAP_REQUIRED")
        assert response.headers[REQUEST_ID_HEADER]


def test_asset_version_create_appends_rows_and_derives_internal_fields(
    client: TestClient,
) -> None:
    owner_id, _workspace, asset = _create_asset(client)

    first = _post_version(client, asset.asset_id)
    first_id = UUID(first.json()["data"]["asset_version_id"])
    second = _post_version(
        client,
        asset.asset_id,
        origin="ai_generated",
        parent_id=first_id,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["data"]["version_number"] == 1
    assert second.json()["data"]["version_number"] == 2
    assert second.json()["data"]["parent_asset_version_id"] == str(first_id)
    assert set(second.json()["data"]) == {
        "asset_version_id",
        "asset_id",
        "version_number",
        "version_origin",
        "parent_asset_version_id",
        "processing_chain_id",
        "provider_id",
        "model_manifest_id",
        "settings_snapshot",
        "created_at",
    }
    assert "created_by" not in second.json()["data"]
    assert _count(client, AssetVersion) == 2
    assert _count(client, Artifact) == 0
    with client.app.state.session_factory() as session:
        versions = AssetRepository(session).list_asset_versions(asset.asset_id)
        stored_asset = AssetRepository(session).get_asset(asset.asset_id)
    assert [version.version_number for version in versions] == [1, 2]
    assert all(version.created_by == owner_id for version in versions)
    assert stored_asset is not None
    assert stored_asset.selected_asset_version_id is None


def test_asset_version_list_is_complete_and_newest_first(client: TestClient) -> None:
    _owner_id, _workspace, asset = _create_asset(client)
    for index in range(3):
        response = _post_version(
            client,
            asset.asset_id,
            origin=f"version_{index + 1}",
        )
        assert response.status_code == 201

    response = client.get(f"/api/v1/assets/{asset.asset_id}/versions")

    assert response.status_code == 200
    assert [item["version_number"] for item in response.json()["data"]] == [3, 2, 1]
    assert len({item["asset_version_id"] for item in response.json()["data"]}) == 3
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_asset_version_detail_is_nested_and_owner_scoped(client: TestClient) -> None:
    owner_id, workspace, asset = _create_asset(client)
    version = _asset_service(client).create_asset_version(
        asset_id=asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=owner_id,
    )
    other_asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.VOCAL,
    )

    response = client.get(f"/api/v1/assets/{asset.asset_id}/versions/{version.asset_version_id}")
    wrong_parent = client.get(
        f"/api/v1/assets/{other_asset.asset_id}/versions/{version.asset_version_id}"
    )
    global_path = client.get(f"/api/v1/versions/{version.asset_version_id}")

    assert response.status_code == 200
    assert response.json()["data"]["asset_id"] == str(asset.asset_id)
    assert wrong_parent.status_code == 404
    assert wrong_parent.json()["error"]["error_code"] == "ASSET_VERSION_NOT_FOUND"
    assert global_path.status_code == 404


def test_asset_version_input_rejects_internal_and_unknown_fields(
    client: TestClient,
) -> None:
    _owner_id, _workspace, asset = _create_asset(client)
    forbidden = {
        "asset_version_id": str(uuid4()),
        "asset_id": str(asset.asset_id),
        "version_number": 10,
        "created_by": str(uuid4()),
        "created_at": "2026-08-08T00:00:00Z",
        "artifacts": [],
    }

    for field, value in forbidden.items():
        response = client.post(
            f"/api/v1/assets/{asset.asset_id}/versions",
            json={"version_origin": "user_created", field: value},
        )
        assert response.status_code == 422
        assert response.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _count(client, AssetVersion) == 0


def test_asset_version_has_no_patch_or_delete_and_keeps_existing_row(
    client: TestClient,
) -> None:
    _owner_id, _workspace, asset = _create_asset(client)
    created = _post_version(client, asset.asset_id)
    version_id = UUID(created.json()["data"]["asset_version_id"])
    original = created.json()["data"]
    path = f"/api/v1/assets/{asset.asset_id}/versions/{version_id}"

    patched = client.patch(path, json={"version_origin": "overwritten"})
    deleted = client.delete(path)
    detail = client.get(path)

    assert patched.status_code == 405
    assert deleted.status_code == 405
    assert detail.status_code == 200
    detail_data = detail.json()["data"]
    assert detail_data["asset_version_id"] == original["asset_version_id"]
    assert detail_data["asset_id"] == original["asset_id"]
    assert detail_data["version_number"] == original["version_number"]
    assert detail_data["version_origin"] == original["version_origin"]
    assert detail_data["settings_snapshot"] == original["settings_snapshot"]
    assert _count(client, AssetVersion) == 1
    assert not hasattr(AssetRepository, "update_asset_version")
    assert not hasattr(AssetRepository, "delete_asset_version")


def test_asset_version_parent_must_belong_to_same_asset(client: TestClient) -> None:
    owner_id, workspace, first_asset = _create_asset(client)
    second_asset = _asset_service(client).create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.VOCAL,
    )
    parent = _asset_service(client).create_asset_version(
        asset_id=first_asset.asset_id,
        version_origin="user_created",
        settings_snapshot={},
        created_by=owner_id,
    )

    response = _post_version(
        client,
        second_asset.asset_id,
        parent_id=parent.asset_version_id,
    )

    assert response.status_code == 422
    assert response.json()["error"]["error_code"] == "INVALID_INPUT"
    assert _count(client, AssetVersion) == 1


def test_asset_version_conflict_and_transaction_rollback(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _owner_id, _workspace, asset = _create_asset(client)
    service = _asset_service(client)

    def conflict(**_kwargs):
        raise ResourceConflictError("AssetVersion")

    monkeypatch.setattr(service, "create_asset_version", conflict)
    response = _post_version(client, asset.asset_id)
    assert response.status_code == 409
    assert response.json()["error"]["error_code"] == "ASSET_VERSION_CONFLICT"
    monkeypatch.undo()

    repository_add = AssetRepository.add_asset_version

    def fail_after_add(
        repository: AssetRepository,
        version: AssetVersion,
    ) -> AssetVersion:
        repository_add(repository, version)
        raise RuntimeError("injected version failure")

    monkeypatch.setattr(AssetRepository, "add_asset_version", fail_after_add)
    with pytest.raises(RuntimeError, match="injected version failure"):
        _post_version(client, asset.asset_id)
    assert _count(client, AssetVersion) == 0
