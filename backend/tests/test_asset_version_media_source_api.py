"""Project-scoped exact AssetVersion safe media resolution contract tests."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy import func, select, text

from backend.models.workspace import (
    Artifact,
    Asset,
    AssetType,
    AssetVersion,
    ProjectAsset,
    WorkingComposition,
)
from backend.services.workspace import AssetService, WorkspaceService


@dataclass(frozen=True, slots=True)
class MediaGraph:
    owner_id: UUID
    workspace_id: UUID
    project_id: UUID
    asset_id: UUID
    asset_version_id: UUID
    artifact_id: UUID


def _services(client: TestClient) -> tuple[WorkspaceService, AssetService]:
    workspace = client.app.state.workspace_service
    assets = client.app.state.asset_service
    assert isinstance(workspace, WorkspaceService)
    assert isinstance(assets, AssetService)
    return workspace, assets


def _seed_graph(client: TestClient) -> MediaGraph:
    workspace_service, asset_service = _services(client)
    owner_id = uuid4()
    workspace = workspace_service.create_workspace(owner_id=owner_id, name="Media resolver")
    project = workspace_service.create_project(
        workspace_id=workspace.workspace_id,
        title="Waveform source",
        created_by=owner_id,
    )
    asset = asset_service.create_asset(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        asset_type=AssetType.MUSIC,
    )
    version = asset_service.create_asset_version(
        asset_id=asset.asset_id,
        version_origin="provider",
        settings_snapshot={},
        created_by=owner_id,
    )
    artifact = _add_artifact(client, version.asset_version_id, checksum="a" * 64)
    workspace_service.attach_asset(
        project_id=project.project_id,
        asset_id=asset.asset_id,
        display_order=0,
        role="music",
    )
    return MediaGraph(
        owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        project_id=project.project_id,
        asset_id=asset.asset_id,
        asset_version_id=version.asset_version_id,
        artifact_id=artifact.artifact_id,
    )


def _add_artifact(
    client: TestClient,
    asset_version_id: UUID,
    *,
    checksum: str,
    artifact_kind: str = "audio",
    media_type: str = "audio/wav",
    retention_status: str = "active",
    duration_us: int | None = 12_500_000,
) -> Artifact:
    _workspace_service, asset_service = _services(client)
    artifact = asset_service.register_artifact(
        asset_version_id=asset_version_id,
        artifact_kind=artifact_kind,
        media_type=media_type,
        size_bytes=4_096,
        artifact_checksum=checksum,
        producer_type="test",
        retention_status=retention_status,
    )
    with client.app.state.session_factory() as session, session.begin():
        stored = session.get(Artifact, artifact.artifact_id)
        assert stored is not None
        stored.duration_us = duration_us
    artifact.duration_us = duration_us
    return artifact


def _url(graph: MediaGraph, version_id: UUID | None = None) -> str:
    selected = version_id or graph.asset_version_id
    return f"/api/v1/projects/{graph.project_id}/asset-versions/{selected}/media-source"


def _error_code(response) -> str:
    return response.json()["error"]["error_code"]


def test_resolves_exact_version_to_one_safe_same_origin_artifact(client: TestClient) -> None:
    graph = _seed_graph(client)

    response = client.get(_url(graph))

    assert response.status_code == 200
    assert response.json()["data"] == {
        "asset_version_id": str(graph.asset_version_id),
        "artifact_id": str(graph.artifact_id),
        "media_type": "audio/wav",
        "size_bytes": 4_096,
        "artifact_checksum": "a" * 64,
        "duration_seconds": "12.5",
        "content_url": f"/api/v1/artifacts/{graph.artifact_id}/content",
    }
    content_url = response.json()["data"]["content_url"]
    assert content_url.startswith("/api/v1/artifacts/")
    assert content_url.endswith("/content")
    assert "://" not in content_url
    assert "?" not in content_url
    assert all(key not in response.text for key in ("storage", "locator", "filesystem"))


def test_exact_version_never_falls_forward_to_newer_version(client: TestClient) -> None:
    graph = _seed_graph(client)
    _workspace_service, asset_service = _services(client)
    newer = asset_service.create_asset_version(
        asset_id=graph.asset_id,
        version_origin="provider",
        settings_snapshot={},
        created_by=graph.owner_id,
    )
    newer_artifact = _add_artifact(client, newer.asset_version_id, checksum="b" * 64)

    response = client.get(_url(graph))

    assert response.status_code == 200
    assert response.json()["data"]["asset_version_id"] == str(graph.asset_version_id)
    assert response.json()["data"]["artifact_id"] == str(graph.artifact_id)
    assert str(newer.asset_version_id) not in response.text
    assert str(newer_artifact.artifact_id) not in response.text


def test_zero_eligible_artifacts_fails_closed_without_latest_fallback(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    with client.app.state.session_factory() as session, session.begin():
        artifact = session.get(Artifact, graph.artifact_id)
        assert artifact is not None
        artifact.retention_status = "deleted"

    response = client.get(_url(graph))

    assert response.status_code == 409
    assert _error_code(response) == "SOURCE_ASSET_UNAVAILABLE"
    assert str(graph.artifact_id) not in response.text


def test_multiple_eligible_artifacts_is_ambiguous_without_first_selection(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    second = _add_artifact(
        client,
        graph.asset_version_id,
        checksum="c" * 64,
        media_type="audio/flac",
    )

    response = client.get(_url(graph))

    assert response.status_code == 409
    assert _error_code(response) == "SOURCE_ARTIFACT_AMBIGUOUS"
    assert str(graph.artifact_id) not in response.text
    assert str(second.artifact_id) not in response.text


def test_revoked_project_asset_and_wrong_project_are_scope_hidden(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    workspace_service, _asset_service = _services(client)
    other_project = workspace_service.create_project(
        workspace_id=graph.workspace_id,
        title="Other project",
        created_by=graph.owner_id,
    )

    wrong_project = client.get(
        f"/api/v1/projects/{other_project.project_id}/asset-versions/"
        f"{graph.asset_version_id}/media-source"
    )
    workspace_service.detach_asset(project_id=graph.project_id, asset_id=graph.asset_id)
    revoked = client.get(_url(graph))

    for response in (wrong_project, revoked):
        assert response.status_code == 409
        assert _error_code(response) == "SOURCE_ASSET_UNAVAILABLE"
        assert str(graph.artifact_id) not in response.text


def test_cross_owner_asset_binding_does_not_leak_artifact(client: TestClient) -> None:
    graph = _seed_graph(client)
    foreign_asset = Asset(
        asset_id=uuid4(),
        workspace_id=None,
        owner_id=uuid4(),
        asset_type=AssetType.MUSIC,
        lifecycle_status="active",
    )
    foreign_version = AssetVersion(
        asset_version_id=uuid4(),
        asset_id=foreign_asset.asset_id,
        version_number=1,
        version_origin="provider",
        settings_snapshot={},
        created_by=foreign_asset.owner_id,
    )
    foreign_artifact = Artifact(
        artifact_id=uuid4(),
        asset_version_id=foreign_version.asset_version_id,
        artifact_kind="audio",
        media_type="audio/wav",
        size_bytes=4_096,
        duration_us=5_000_000,
        checksum_algorithm="sha256",
        artifact_checksum="d" * 64,
        producer_type="test",
        retention_status="active",
    )
    with client.app.state.session_factory() as session, session.begin():
        session.add(foreign_asset)
        session.flush()
        session.add(foreign_version)
        session.flush()
        session.add_all(
            [
                foreign_artifact,
                ProjectAsset(
                    project_asset_id=uuid4(),
                    project_id=graph.project_id,
                    asset_id=foreign_asset.asset_id,
                    role="music",
                    display_order=1,
                ),
            ]
        )

    response = client.get(_url(graph, foreign_version.asset_version_id))

    assert response.status_code == 409
    assert _error_code(response) == "SOURCE_ASSET_UNAVAILABLE"
    assert str(foreign_artifact.artifact_id) not in response.text


def test_unsupported_media_and_missing_trusted_duration_fail_closed(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    with client.app.state.session_factory() as session, session.begin():
        artifact = session.get(Artifact, graph.artifact_id)
        assert artifact is not None
        artifact.media_type = "audio/ogg"
    unsupported = client.get(_url(graph))
    assert unsupported.status_code == 409
    assert _error_code(unsupported) == "SOURCE_ASSET_UNAVAILABLE"

    with client.app.state.session_factory() as session, session.begin():
        artifact = session.get(Artifact, graph.artifact_id)
        assert artifact is not None
        artifact.media_type = "audio/mpeg"
        artifact.duration_us = None
    no_duration = client.get(_url(graph))
    assert no_duration.status_code == 409
    assert _error_code(no_duration) == "SOURCE_DURATION_UNAVAILABLE"


def test_supported_mpeg_with_persisted_trusted_duration_is_resolved(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    with client.app.state.session_factory() as session, session.begin():
        artifact = session.get(Artifact, graph.artifact_id)
        assert artifact is not None
        artifact.media_type = "audio/mpeg"

    response = client.get(_url(graph))

    assert response.status_code == 200
    assert response.json()["data"]["media_type"] == "audio/mpeg"
    assert response.json()["data"]["duration_seconds"] == "12.5"


def test_existing_stem_role_and_flac_media_are_resolved(client: TestClient) -> None:
    graph = _seed_graph(client)
    with client.app.state.session_factory() as session, session.begin():
        artifact = session.get(Artifact, graph.artifact_id)
        assert artifact is not None
        artifact.artifact_kind = "stem"
        artifact.media_type = "audio/flac"

    response = client.get(_url(graph))

    assert response.status_code == 200
    assert response.json()["data"]["media_type"] == "audio/flac"
    assert response.json()["data"]["artifact_id"] == str(graph.artifact_id)


def test_media_source_get_is_read_only(client: TestClient) -> None:
    graph = _seed_graph(client)

    def snapshot() -> tuple[object, ...]:
        with client.app.state.session_factory() as session:
            asset = session.get(Asset, graph.asset_id)
            version = session.get(AssetVersion, graph.asset_version_id)
            artifact = session.get(Artifact, graph.artifact_id)
            project_asset = session.scalar(
                select(ProjectAsset).where(
                    ProjectAsset.project_id == graph.project_id,
                    ProjectAsset.asset_id == graph.asset_id,
                )
            )
            working_count = session.scalar(
                select(func.count(WorkingComposition.working_composition_id))
            )
            assert asset and version and artifact and project_asset
            return (
                asset.updated_at,
                asset.selected_asset_version_id,
                version.settings_snapshot,
                artifact.retention_status,
                artifact.duration_us,
                project_asset.deleted_at,
                working_count,
            )

    before = snapshot()
    first = client.get(_url(graph))
    second = client.get(_url(graph))
    after = snapshot()

    assert first.status_code == second.status_code == 200
    assert first.json()["data"] == second.json()["data"]
    assert after == before


def test_media_source_openapi_contract_is_explicit_and_path_safe(client: TestClient) -> None:
    graph = _seed_graph(client)
    path = "/api/v1/projects/{project_id}/asset-versions/{asset_version_id}/media-source"

    operation = client.app.openapi()["paths"][path]["get"]
    schema = client.app.openapi()["components"]["schemas"]["ClipMediaSourceDetail"]

    assert operation["operationId"] == "resolve_project_asset_version_media_source"
    assert {parameter["name"] for parameter in operation["parameters"]} == {
        "project_id",
        "asset_version_id",
    }
    assert set(schema["properties"]) == {
        "asset_version_id",
        "artifact_id",
        "media_type",
        "size_bytes",
        "artifact_checksum",
        "duration_seconds",
        "content_url",
    }
    assert all(
        forbidden not in str(operation).lower()
        for forbidden in ("absolute_path", "storage_key", "locator", "credential")
    )
    assert str(graph.artifact_id) not in str(operation)


def test_exact_version_candidate_query_uses_existing_artifact_index(
    client: TestClient,
) -> None:
    graph = _seed_graph(client)
    query = """
        SELECT artifact_id
        FROM artifacts
        WHERE asset_version_id = :asset_version_id
          AND artifact_kind IN ('audio', 'stem')
          AND media_type IN ('audio/wav', 'audio/flac', 'audio/mpeg')
          AND retention_status = 'active'
        ORDER BY created_at, artifact_id
    """

    with client.app.state.session_factory() as session:
        plan = " ".join(
            str(row[-1])
            for row in session.execute(
                text(f"EXPLAIN QUERY PLAN {query}"),
                {"asset_version_id": graph.asset_version_id.hex},
            )
        )

    assert "ix_artifacts_version_created" in plan
