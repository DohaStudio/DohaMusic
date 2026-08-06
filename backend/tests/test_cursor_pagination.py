"""HMAC cursor와 Workspace·Project keyset pagination 검증."""

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

from backend.core.config import Settings
from backend.core.cursor_pagination import CursorCodec, filter_fingerprint
from backend.core.exceptions import (
    CursorConfigurationError,
    InvalidCursorError,
    InvalidLimitError,
    ResourceNotFoundError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import MusicProject, Workspace
from backend.services.workspace import WorkspaceService

TEST_KEY = "cursor-test-signing-key-with-32-bytes-minimum"
OTHER_KEY = "other-cursor-signing-key-with-32-bytes-minimum"
CREATED_AT = datetime(2026, 8, 6, 3, 0, tzinfo=timezone.utc)


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'cursor-pagination.db').as_posix()}"
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    assert engine.pool.checkedout() == 0
    engine.dispose()


def _workspace(identifier: int, *, deleted: bool = False) -> Workspace:
    return Workspace(
        workspace_id=UUID(int=identifier),
        owner_id=UUID(int=10_000 + identifier),
        name=f"Workspace {identifier}",
        lifecycle_status="active",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        deleted_at=CREATED_AT + timedelta(days=1) if deleted else None,
    )


def _project(
    workspace_id: UUID, identifier: int, *, deleted: bool = False
) -> MusicProject:
    return MusicProject(
        project_id=UUID(int=identifier),
        workspace_id=workspace_id,
        title=f"Project {identifier}",
        description=None,
        lifecycle_status="active",
        created_by=UUID(int=20_000 + identifier),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
        deleted_at=CREATED_AT + timedelta(days=1) if deleted else None,
    )


def _filter_hash() -> str:
    return filter_fingerprint({"include_deleted": False, "sort": "created_at_desc"})


def _signed_token(payload: dict[str, object], key: str = TEST_KEY) -> str:
    payload_bytes = json.dumps(
        payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    signature = hmac.new(key.encode(), payload_bytes, hashlib.sha256).digest()

    def encode(value: bytes) -> str:
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode()

    return f"{encode(payload_bytes)}.{encode(signature)}"


def _valid_payload() -> dict[str, object]:
    return {
        "direction": "next",
        "filter_hash": _filter_hash(),
        "last_created_at": "2026-08-06T03:00:00Z",
        "last_id": str(UUID(int=1)),
        "limit": 50,
        "resource": "workspace",
        "sort": "created_at_desc",
        "v": 1,
    }


def test_codec_round_trip_is_canonical_and_opaque() -> None:
    codec = CursorCodec(TEST_KEY)
    values = {
        "resource": "workspace",
        "last_created_at": CREATED_AT,
        "last_id": UUID(int=1),
        "filter_hash": _filter_hash(),
        "limit": 50,
    }

    first = codec.encode(**values)
    second = codec.encode(**values)
    position = codec.decode(
        first,
        expected_resource="workspace",
        expected_filter_hash=_filter_hash(),
        expected_limit=50,
    )

    assert first == second
    assert first.count(".") == 1
    assert "created_at" not in first
    encoded_payload = first.split(".")[0]
    decoded_payload = json.loads(
        base64.urlsafe_b64decode(encoded_payload + "=" * (-len(encoded_payload) % 4))
    )
    assert set(decoded_payload) == {
        "v",
        "resource",
        "direction",
        "sort",
        "last_created_at",
        "last_id",
        "filter_hash",
        "limit",
    }
    assert not {
        "owner_id",
        "workspace_id",
        "name",
        "title",
        "database_url",
    } & set(decoded_payload)
    assert position.last_created_at == CREATED_AT
    assert position.last_id == UUID(int=1)


def test_codec_rejects_invalid_format_signature_and_payload_tampering() -> None:
    codec = CursorCodec(TEST_KEY)
    token = codec.encode(
        resource="workspace",
        last_created_at=CREATED_AT,
        last_id=UUID(int=1),
        filter_hash=_filter_hash(),
        limit=50,
    )
    payload, signature = token.split(".")
    tampered_payload = ("A" if payload[0] != "A" else "B") + payload[1:]

    for invalid in [
        "invalid",
        f"{payload}.invalid!",
        f"{tampered_payload}.{signature}",
    ]:
        with pytest.raises(InvalidCursorError) as error:
            codec.decode(
                invalid,
                expected_resource="workspace",
                expected_filter_hash=_filter_hash(),
                expected_limit=50,
            )
        assert error.value.code == "INVALID_CURSOR"

    with pytest.raises(InvalidCursorError):
        CursorCodec(OTHER_KEY).decode(
            token,
            expected_resource="workspace",
            expected_filter_hash=_filter_hash(),
            expected_limit=50,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("v", 2),
        ("direction", "previous"),
        ("sort", "created_at_asc"),
        ("last_created_at", "not-a-datetime"),
        ("last_id", "not-a-uuid"),
        ("limit", 0),
    ],
)
def test_codec_rejects_invalid_signed_payload(field: str, value: object) -> None:
    payload = _valid_payload()
    payload[field] = value
    with pytest.raises(InvalidCursorError):
        CursorCodec(TEST_KEY).decode(
            _signed_token(payload),
            expected_resource="workspace",
            expected_filter_hash=_filter_hash(),
            expected_limit=50,
        )


def test_codec_rejects_resource_filter_and_limit_reuse() -> None:
    token = _signed_token(_valid_payload())
    codec = CursorCodec(TEST_KEY)
    with pytest.raises(InvalidCursorError):
        codec.decode(
            token,
            expected_resource="project",
            expected_filter_hash=_filter_hash(),
            expected_limit=50,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode(
            token,
            expected_resource="workspace",
            expected_filter_hash="0" * 64,
            expected_limit=50,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode(
            token,
            expected_resource="workspace",
            expected_filter_hash=_filter_hash(),
            expected_limit=25,
        )


def test_codec_rejects_unexpected_signed_payload_field() -> None:
    payload = _valid_payload()
    payload["unexpected"] = "value"
    with pytest.raises(InvalidCursorError):
        CursorCodec(TEST_KEY).decode(
            _signed_token(payload),
            expected_resource="workspace",
            expected_filter_hash=_filter_hash(),
            expected_limit=50,
        )


def test_cursor_secret_is_required_redacted_and_loaded_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(CursorConfigurationError) as error:
        CursorCodec("too-short")
    assert TEST_KEY not in str(error.value)

    monkeypatch.setenv("DOHAMUSIC_CURSOR_SIGNING_KEY", TEST_KEY)
    settings = Settings.from_environment()
    assert settings.cursor_signing_key.get_secret_value() == TEST_KEY
    assert TEST_KEY not in repr(settings)


def test_workspace_pages_have_no_duplicates_or_omissions(session_factory) -> None:
    with session_factory.begin() as session:
        session.add_all([_workspace(index) for index in range(1, 6)])
        session.add(_workspace(99, deleted=True))
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    first = service.list_workspace_page(limit=2)
    second = service.list_workspace_page(limit=2, cursor=first.next_cursor)
    third = service.list_workspace_page(limit=2, cursor=second.next_cursor)
    identifiers = [
        item.workspace_id for page in (first, second, third) for item in page.items
    ]

    assert [len(first.items), len(second.items), len(third.items)] == [2, 2, 1]
    assert first.has_more and first.next_cursor
    assert second.has_more and second.next_cursor
    assert third.has_more is False and third.next_cursor is None
    assert identifiers == [UUID(int=index) for index in range(5, 0, -1)]
    assert len(set(identifiers)) == 5


def test_workspace_page_handles_empty_exact_limit_and_owner_filter(
    session_factory,
) -> None:
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    empty = service.list_workspace_page(limit=2)
    assert empty.items == ()
    assert empty.has_more is False
    assert empty.next_cursor is None

    owner_id = uuid4()
    with session_factory.begin() as session:
        first = _workspace(1)
        second = _workspace(2)
        first.owner_id = owner_id
        second.owner_id = owner_id
        session.add_all([first, second, _workspace(3)])
    exact = service.list_workspace_page(limit=2, owner_id=owner_id)
    assert [item.workspace_id for item in exact.items] == [UUID(int=2), UUID(int=1)]
    assert exact.has_more is False
    assert exact.next_cursor is None


def test_workspace_cursor_is_bound_to_owner_filter(session_factory) -> None:
    first_owner = uuid4()
    second_owner = uuid4()
    with session_factory.begin() as session:
        workspaces = [_workspace(index) for index in range(1, 4)]
        for workspace in workspaces:
            workspace.owner_id = first_owner
        other = _workspace(4)
        other.owner_id = second_owner
        session.add_all([*workspaces, other])
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    first = service.list_workspace_page(limit=1, owner_id=first_owner)

    with pytest.raises(InvalidCursorError):
        service.list_workspace_page(
            limit=1, owner_id=second_owner, cursor=first.next_cursor
        )


def test_project_pages_bind_cursor_to_workspace_and_exclude_deleted(
    session_factory,
) -> None:
    first_workspace = _workspace(100)
    second_workspace = _workspace(200)
    with session_factory.begin() as session:
        session.add_all([first_workspace, second_workspace])
        session.add_all(
            [_project(first_workspace.workspace_id, index) for index in range(1, 5)]
        )
        session.add(_project(first_workspace.workspace_id, 99, deleted=True))
        session.add(_project(second_workspace.workspace_id, 101))
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    first = service.list_project_page(first_workspace.workspace_id, limit=2)
    second = service.list_project_page(
        first_workspace.workspace_id, limit=2, cursor=first.next_cursor
    )
    identifiers = [item.project_id for item in first.items + second.items]

    assert identifiers == [UUID(int=index) for index in range(4, 0, -1)]
    assert first.has_more and first.next_cursor
    assert second.has_more is False and second.next_cursor is None
    with pytest.raises(InvalidCursorError):
        service.list_project_page(
            second_workspace.workspace_id, limit=2, cursor=first.next_cursor
        )


def test_project_page_rejects_missing_workspace(session_factory) -> None:
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    with pytest.raises(ResourceNotFoundError):
        service.list_project_page(uuid4(), limit=10)


def test_project_page_returns_empty_for_existing_workspace(session_factory) -> None:
    workspace = _workspace(1)
    with session_factory.begin() as session:
        session.add(workspace)
    page = WorkspaceService(
        session_factory, cursor_codec=CursorCodec(TEST_KEY)
    ).list_project_page(workspace.workspace_id, limit=10)
    assert page.items == ()
    assert page.has_more is False
    assert page.next_cursor is None


def test_page_methods_require_codec_and_valid_limit(session_factory) -> None:
    with pytest.raises(CursorConfigurationError):
        WorkspaceService(session_factory).list_workspace_page()
    service = WorkspaceService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    for invalid_limit in [0, 101, True]:
        with pytest.raises(InvalidLimitError):
            service.list_workspace_page(limit=invalid_limit)
