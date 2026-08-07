"""ProjectAsset 전용 HMAC cursor와 keyset pagination 검증."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy.orm import sessionmaker

from backend.core.cursor_pagination import (
    MAX_CURSOR_TOKEN_LENGTH,
    PROJECT_ASSET_CURSOR_SORT,
    CursorCodec,
    filter_fingerprint,
)
from backend.core.exceptions import (
    InvalidCursorError,
    InvalidLimitError,
    ResourceNotFoundError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import (
    Asset,
    AssetType,
    MusicProject,
    ProjectAsset,
    Workspace,
)
from backend.services.workspace import WorkspaceService

TEST_KEY = "project-asset-cursor-signing-key-with-32-bytes"
CREATED_AT = datetime(2026, 8, 7, 6, 0, tzinfo=timezone.utc)


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'project-asset-cursor.db').as_posix()}"
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    assert engine.pool.checkedout() == 0
    engine.dispose()


def _workspace(identifier: int) -> Workspace:
    return Workspace(
        workspace_id=UUID(int=identifier),
        owner_id=UUID(int=10_000 + identifier),
        name=f"Workspace {identifier}",
        lifecycle_status="active",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _project(workspace_id: UUID, identifier: int) -> MusicProject:
    return MusicProject(
        project_id=UUID(int=identifier),
        workspace_id=workspace_id,
        title=f"Project {identifier}",
        description=None,
        lifecycle_status="active",
        created_by=UUID(int=20_000 + identifier),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _asset(workspace_id: UUID, identifier: int) -> Asset:
    return Asset(
        asset_id=UUID(int=identifier),
        workspace_id=workspace_id,
        owner_id=UUID(int=30_000 + identifier),
        asset_type=AssetType.MUSIC,
        lifecycle_status="active",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _link(
    project_id: UUID,
    asset_id: UUID,
    identifier: int,
    display_order: int,
    *,
    deleted: bool = False,
) -> ProjectAsset:
    return ProjectAsset(
        project_asset_id=UUID(int=identifier),
        project_id=project_id,
        asset_id=asset_id,
        role="music",
        display_order=display_order,
        created_at=CREATED_AT,
        deleted_at=CREATED_AT + timedelta(days=1) if deleted else None,
    )


def _project_filter(project_id: UUID) -> str:
    return filter_fingerprint(
        {
            "include_deleted": False,
            "project_id": str(project_id),
            "sort": PROJECT_ASSET_CURSOR_SORT,
        }
    )


def _signed_token(payload: dict[str, object]) -> str:
    payload_bytes = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    signature = hmac.new(TEST_KEY.encode(), payload_bytes, hashlib.sha256).digest()

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    return f"{encode(payload_bytes)}.{encode(signature)}"


def _valid_payload(project_id: UUID) -> dict[str, object]:
    return {
        "direction": "next",
        "filter_hash": _project_filter(project_id),
        "last_display_order": 3,
        "last_id": str(UUID(int=1)),
        "limit": 25,
        "resource": "project_asset",
        "sort": PROJECT_ASSET_CURSOR_SORT,
        "v": 1,
    }


def _seed_pages(session_factory):
    first_workspace = _workspace(1)
    second_workspace = _workspace(2)
    first_project = _project(first_workspace.workspace_id, 101)
    second_project = _project(second_workspace.workspace_id, 201)
    first_assets = [
        _asset(first_workspace.workspace_id, 1_000 + item) for item in range(7)
    ]
    second_asset = _asset(second_workspace.workspace_id, 2_000)
    links = [
        _link(first_project.project_id, first_assets[0].asset_id, 301, 0),
        _link(first_project.project_id, first_assets[1].asset_id, 302, 0),
        _link(first_project.project_id, first_assets[2].asset_id, 303, 1),
        _link(first_project.project_id, first_assets[3].asset_id, 304, 1),
        _link(first_project.project_id, first_assets[4].asset_id, 305, 2),
        _link(
            first_project.project_id,
            first_assets[5].asset_id,
            306,
            0,
            deleted=True,
        ),
        _link(second_project.project_id, second_asset.asset_id, 401, 0),
    ]
    with session_factory.begin() as session:
        session.add_all(
            [
                first_workspace,
                second_workspace,
                first_project,
                second_project,
                *first_assets,
                second_asset,
                *links,
            ]
        )
    return first_project, second_project, first_assets, links


def test_project_asset_codec_round_trip_uses_resource_specific_payload() -> None:
    project_id = uuid4()
    codec = CursorCodec(TEST_KEY)
    token = codec.encode_project_asset(
        last_display_order=3,
        last_id=UUID(int=1),
        filter_hash=_project_filter(project_id),
        limit=25,
    )
    position = codec.decode_project_asset(
        token,
        expected_filter_hash=_project_filter(project_id),
        expected_limit=25,
    )
    encoded_payload = token.split(".")[0]
    payload = json.loads(
        base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
    )

    assert set(payload) == {
        "v",
        "resource",
        "direction",
        "sort",
        "last_display_order",
        "last_id",
        "filter_hash",
        "limit",
    }
    assert "last_created_at" not in payload
    assert payload["resource"] == "project_asset"
    assert payload["sort"] == PROJECT_ASSET_CURSOR_SORT
    assert position.last_display_order == 3
    assert position.last_id == UUID(int=1)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("v", 2),
        ("v", True),
        ("direction", "previous"),
        ("sort", "created_at_desc"),
        ("resource", "project"),
        ("last_display_order", -1),
        ("last_display_order", True),
        ("last_display_order", 1.0),
        ("last_display_order", "1"),
        ("last_id", "not-a-uuid"),
        ("limit", 0),
        ("limit", 101),
        ("limit", True),
        ("limit", 25.0),
        ("limit", "25"),
    ],
)
def test_project_asset_codec_rejects_invalid_signed_payload(
    field: str, value: object
) -> None:
    project_id = uuid4()
    payload = _valid_payload(project_id)
    payload[field] = value
    with pytest.raises(InvalidCursorError):
        CursorCodec(TEST_KEY).decode_project_asset(
            _signed_token(payload),
            expected_filter_hash=_project_filter(project_id),
            expected_limit=25,
        )


def test_project_asset_codec_rejects_tamper_filter_limit_shape_and_size() -> None:
    project_id = uuid4()
    codec = CursorCodec(TEST_KEY)
    token = codec.encode_project_asset(
        last_display_order=3,
        last_id=UUID(int=1),
        filter_hash=_project_filter(project_id),
        limit=25,
    )
    payload, signature = token.split(".")
    tampered = ("A" if payload[0] != "A" else "B") + payload[1:]

    with pytest.raises(InvalidCursorError):
        codec.decode_project_asset(
            f"{tampered}.{signature}",
            expected_filter_hash=_project_filter(project_id),
            expected_limit=25,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode_project_asset(
            token,
            expected_filter_hash=_project_filter(uuid4()),
            expected_limit=25,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode_project_asset(
            token,
            expected_filter_hash=_project_filter(project_id),
            expected_limit=10,
        )
    unexpected = _valid_payload(project_id)
    unexpected["unexpected"] = "value"
    with pytest.raises(InvalidCursorError):
        codec.decode_project_asset(
            _signed_token(unexpected),
            expected_filter_hash=_project_filter(project_id),
            expected_limit=25,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode_project_asset(
            "A" * (MAX_CURSOR_TOKEN_LENGTH + 1),
            expected_filter_hash=_project_filter(project_id),
            expected_limit=25,
        )


def test_project_asset_pages_are_stable_and_bound_to_project(session_factory) -> None:
    first_project, second_project, _, _ = _seed_pages(session_factory)
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    pages = []
    cursor = None
    seen_cursors = set()
    for _ in range(4):
        page = service.list_project_asset_page(
            first_project.project_id,
            limit=2,
            cursor=cursor,
        )
        pages.append(page)
        if page.next_cursor is None:
            break
        assert page.next_cursor not in seen_cursors
        seen_cursors.add(page.next_cursor)
        cursor = page.next_cursor
    identifiers = [item.project_asset_id for page in pages for item in page.items]

    assert [len(page.items) for page in pages] == [2, 2, 1]
    assert identifiers == [UUID(int=item) for item in range(301, 306)]
    assert len(identifiers) == len(set(identifiers))
    assert pages[-1].has_more is False
    assert pages[-1].next_cursor is None
    with pytest.raises(InvalidCursorError):
        service.list_project_asset_page(
            second_project.project_id,
            limit=2,
            cursor=pages[0].next_cursor,
        )


def test_project_asset_page_is_forward_only_across_insert_detach_and_restore(
    session_factory,
) -> None:
    project, _, assets, links = _seed_pages(session_factory)
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    first = service.list_project_asset_page(project.project_id, limit=2)

    with session_factory.begin() as session:
        earlier_asset = _asset(project.workspace_id, 9_999)
        session.add(earlier_asset)
        session.add(_link(project.project_id, earlier_asset.asset_id, 300, 0))
    service.detach_asset(project_id=project.project_id, asset_id=assets[2].asset_id)
    restored = service.attach_asset(
        project_id=project.project_id,
        asset_id=assets[2].asset_id,
        role="restored",
        display_order=1,
    )
    second = service.list_project_asset_page(
        project.project_id, limit=2, cursor=first.next_cursor
    )
    third = service.list_project_asset_page(
        project.project_id, limit=2, cursor=second.next_cursor
    )
    identifiers = [
        item.project_asset_id for page in (first, second, third) for item in page.items
    ]

    assert restored.project_asset_id == links[2].project_asset_id
    assert identifiers == [UUID(int=item) for item in range(301, 306)]
    assert UUID(int=300) not in identifiers
    assert len(identifiers) == len(set(identifiers))


def test_project_asset_page_handles_empty_and_missing_project(session_factory) -> None:
    workspace = _workspace(1)
    project = _project(workspace.workspace_id, 101)
    with session_factory.begin() as session:
        session.add_all([workspace, project])
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    page = service.list_project_asset_page(project.project_id, limit=10)
    assert page.items == ()
    assert page.has_more is False
    assert page.next_cursor is None
    with pytest.raises(ResourceNotFoundError):
        service.list_project_asset_page(uuid4(), limit=10)


@pytest.mark.parametrize("limit", [True, False, 1.0, 1.5, "10", 0, 101])
def test_project_asset_page_rejects_non_integer_or_out_of_range_limit(
    session_factory, limit: object
) -> None:
    workspace = _workspace(1)
    project = _project(workspace.workspace_id, 101)
    with session_factory.begin() as session:
        session.add_all([workspace, project])
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    with pytest.raises(InvalidLimitError) as exc_info:
        service.list_project_asset_page(project.project_id, limit=limit)  # type: ignore[arg-type]
    assert exc_info.value.code == "INVALID_LIMIT"
