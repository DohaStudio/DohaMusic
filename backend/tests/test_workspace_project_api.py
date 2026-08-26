"""Workspace와 MusicProject 첫 Resource API 계약 검증."""

from __future__ import annotations

from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from backend.api.v1.dependencies import REQUEST_ID_HEADER
from backend.services.workspace import WorkspaceService


def _service(client: TestClient) -> WorkspaceService:
    service = client.app.state.workspace_service
    assert isinstance(service, WorkspaceService)
    return service


def _create_workspace(client: TestClient, *, name: str = "개인 작업실"):
    return _service(client).create_workspace(owner_id=uuid4(), name=name)


def test_resource_api_requires_workspace_bootstrap(client: TestClient) -> None:
    workspace_id = uuid4()
    project_id = uuid4()
    requests = (
        ("GET", "/api/v1/workspaces", None),
        ("GET", f"/api/v1/workspaces/{workspace_id}", None),
        ("PATCH", f"/api/v1/workspaces/{workspace_id}", {"name": "작업실"}),
        ("GET", f"/api/v1/projects?workspace_id={workspace_id}", None),
        (
            "POST",
            "/api/v1/projects",
            {"workspace_id": str(workspace_id), "title": "첫 곡"},
        ),
        ("GET", f"/api/v1/projects/{project_id}", None),
        ("PATCH", f"/api/v1/projects/{project_id}", {"title": "수정"}),
        ("DELETE", f"/api/v1/projects/{project_id}", None),
    )
    for method, path, body in requests:
        response = client.request(method, path, json=body)

        assert response.status_code == 409
        assert response.json()["error"]["error_code"] == "WORKSPACE_BOOTSTRAP_REQUIRED"
        assert response.json()["error"]["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_workspace_list_detail_and_update(client: TestClient) -> None:
    workspace = _create_workspace(client)

    listed = client.get("/api/v1/workspaces?limit=1")
    assert listed.status_code == 200
    assert listed.json()["data"][0]["workspace_id"] == str(workspace.workspace_id)
    assert listed.json()["pagination"] == {
        "limit": 1,
        "next_cursor": None,
        "has_more": False,
    }
    assert listed.json()["links"]["self"] == "/api/v1/workspaces?limit=1"

    detailed = client.get(f"/api/v1/workspaces/{workspace.workspace_id}")
    assert detailed.status_code == 200
    assert "owner_id" not in detailed.json()["data"]

    updated = client.patch(
        f"/api/v1/workspaces/{workspace.workspace_id}",
        json={"name": "  새 작업실  "},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["name"] == "새 작업실"

    invalid = client.patch(
        f"/api/v1/workspaces/{workspace.workspace_id}",
        json={"owner_id": str(uuid4())},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["error_code"] == "INVALID_INPUT"


def test_workspace_errors_are_resource_specific(client: TestClient) -> None:
    first = _create_workspace(client, name="첫 작업실")
    second = _service(client).create_workspace(owner_id=first.owner_id, name="둘째 작업실")

    missing = client.get(f"/api/v1/workspaces/{uuid4()}")
    assert missing.status_code == 404
    assert missing.json()["error"]["error_code"] == "WORKSPACE_NOT_FOUND"

    conflict = client.patch(
        f"/api/v1/workspaces/{second.workspace_id}",
        json={"name": first.name},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["error_code"] == "WORKSPACE_NAME_CONFLICT"


def test_project_created_by_is_derived_and_input_is_forbidden(
    client: TestClient,
) -> None:
    workspace = _create_workspace(client)

    response = client.post(
        "/api/v1/projects",
        json={
            "workspace_id": str(workspace.workspace_id),
            "title": "  첫 곡  ",
            "description": "설명",
        },
    )
    assert response.status_code == 201
    assert response.json()["data"]["title"] == "첫 곡"
    assert "created_by" not in response.json()["data"]
    project_id = UUID(response.json()["data"]["project_id"])
    assert _service(client).get_project(project_id).created_by == workspace.owner_id

    forbidden = client.post(
        "/api/v1/projects",
        json={
            "workspace_id": str(workspace.workspace_id),
            "title": "주입 시도",
            "created_by": str(uuid4()),
        },
    )
    assert forbidden.status_code == 422
    assert forbidden.json()["error"]["error_code"] == "INVALID_INPUT"


def test_project_list_uses_hmac_cursor_without_duplicates(client: TestClient) -> None:
    workspace = _create_workspace(client)
    for index in range(3):
        response = client.post(
            "/api/v1/projects",
            json={"workspace_id": str(workspace.workspace_id), "title": f"곡 {index}"},
        )
        assert response.status_code == 201

    first = client.get(f"/api/v1/projects?workspace_id={workspace.workspace_id}&limit=2")
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["pagination"]["has_more"] is True
    assert first_body["pagination"]["next_cursor"]

    second = client.get(first_body["links"]["next"])
    assert second.status_code == 200
    ids = [item["project_id"] for item in first_body["data"] + second.json()["data"]]
    assert len(ids) == 3
    assert len(set(ids)) == 3

    other_workspace = _service(client).create_workspace(owner_id=uuid4(), name="다른 작업실")
    reused = client.get(
        "/api/v1/projects",
        params={
            "workspace_id": str(other_workspace.workspace_id),
            "limit": 2,
            "cursor": first_body["pagination"]["next_cursor"],
        },
    )
    assert reused.status_code == 422
    assert reused.json()["error"]["error_code"] == "INVALID_CURSOR"


def test_project_detail_update_and_delete(client: TestClient) -> None:
    workspace = _create_workspace(client)
    created = client.post(
        "/api/v1/projects",
        json={"workspace_id": str(workspace.workspace_id), "title": "초안"},
    )
    project_id = created.json()["data"]["project_id"]

    detailed = client.get(f"/api/v1/projects/{project_id}")
    assert detailed.status_code == 200

    updated = client.patch(
        f"/api/v1/projects/{project_id}",
        json={"title": "완성", "description": "최종 설명"},
    )
    assert updated.status_code == 200
    assert updated.json()["data"]["title"] == "완성"
    assert updated.json()["data"]["description"] == "최종 설명"

    deleted = client.delete(f"/api/v1/projects/{project_id}")
    assert deleted.status_code == 204
    assert deleted.content == b""
    assert deleted.headers[REQUEST_ID_HEADER]

    missing = client.get(f"/api/v1/projects/{project_id}")
    assert missing.status_code == 404
    assert missing.json()["error"]["error_code"] == "PROJECT_NOT_FOUND"


def test_project_conflict_not_found_and_invalid_update(client: TestClient) -> None:
    workspace = _create_workspace(client)
    created = client.post(
        "/api/v1/projects",
        json={"workspace_id": str(workspace.workspace_id), "title": "중복"},
    )
    assert created.status_code == 201

    conflict = client.post(
        "/api/v1/projects",
        json={"workspace_id": str(workspace.workspace_id), "title": "중복"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["error_code"] == "PROJECT_TITLE_CONFLICT"

    second = client.post(
        "/api/v1/projects",
        json={"workspace_id": str(workspace.workspace_id), "title": "다른 곡"},
    )
    duplicate_patch = client.patch(
        f"/api/v1/projects/{second.json()['data']['project_id']}",
        json={"title": "중복"},
    )
    assert duplicate_patch.status_code == 409
    assert duplicate_patch.json()["error"]["error_code"] == "PROJECT_TITLE_CONFLICT"

    unknown_workspace = client.get(f"/api/v1/projects?workspace_id={uuid4()}")
    assert unknown_workspace.status_code == 404
    assert unknown_workspace.json()["error"]["error_code"] == "WORKSPACE_NOT_FOUND"

    for payload in (
        {},
        {"title": None},
        {"description": None},
        {"owner_id": str(uuid4())},
    ):
        invalid = client.patch(f"/api/v1/projects/{uuid4()}", json=payload)
        assert invalid.status_code == 422
        assert invalid.json()["error"]["error_code"] == "INVALID_INPUT"


def test_project_input_contract_does_not_expose_owner_fields(
    client: TestClient,
) -> None:
    _create_workspace(client)
    schemas = client.app.openapi()["components"]["schemas"]

    assert "owner_id" not in schemas["WorkspaceUpdateRequest"]["properties"]
    assert "owner_id" not in schemas["WorkspaceDetail"]["properties"]
    assert "created_by" not in schemas["ProjectCreateRequest"]["properties"]
    assert "created_by" not in schemas["ProjectUpdateRequest"]["properties"]
    assert "created_by" not in schemas["ProjectDetail"]["properties"]
    assert UUID(str(_service(client).list_workspaces(limit=1)[0].owner_id))

    forbidden_query = client.get(f"/api/v1/workspaces?owner_id={uuid4()}")
    assert forbidden_query.status_code == 422
    assert forbidden_query.json()["error"]["error_code"] == "INVALID_INPUT"


def test_resource_api_validates_uuid_name_and_limit(client: TestClient) -> None:
    workspace = _create_workspace(client)

    invalid_uuid = client.get("/api/v1/workspaces/not-a-uuid")
    assert invalid_uuid.status_code == 422
    assert invalid_uuid.json()["error"]["error_code"] == "INVALID_INPUT"

    for body in ({}, {"name": ""}, {"name": "   "}, {"deleted_at": None}):
        response = client.patch(f"/api/v1/workspaces/{workspace.workspace_id}", json=body)
        assert response.status_code == 422
        assert response.json()["error"]["error_code"] == "INVALID_INPUT"

    for path in (
        "/api/v1/workspaces?limit=0",
        f"/api/v1/projects?workspace_id={workspace.workspace_id}&limit=101",
    ):
        response = client.get(path)
        assert response.status_code == 422
        assert response.json()["error"]["error_code"] == "INVALID_LIMIT"
