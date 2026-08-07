"""Asset HMAC cursor와 Owner scope keyset page 계약 검증."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy.orm import sessionmaker

import backend.models  # noqa: F401
from backend.core.cursor_pagination import CursorCodec, filter_fingerprint
from backend.core.exceptions import (
    InvalidCursorError,
    InvalidLimitError,
    ResourceNotFoundError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import Asset, AssetType, Workspace
from backend.services.workspace import AssetService

TEST_KEY = "asset-cursor-signing-key-with-at-least-32-bytes"


def _id(namespace: int, value: int) -> UUID:
    return UUID(f"{namespace:02x}{value:030x}")


@pytest.fixture
def session_factory(tmp_path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'asset-cursor.db').as_posix()}"
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    yield factory
    engine.dispose()


def _seed(session_factory) -> tuple[UUID, UUID, UUID, list[Asset]]:
    owner_id = _id(1, 1)
    other_owner_id = _id(1, 2)
    first_workspace_id = _id(2, 1)
    second_workspace_id = _id(2, 2)
    origin = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)
    with session_factory.begin() as session:
        session.add_all(
            [
                Workspace(
                    workspace_id=first_workspace_id,
                    owner_id=owner_id,
                    name="첫 Workspace",
                    lifecycle_status="active",
                ),
                Workspace(
                    workspace_id=second_workspace_id,
                    owner_id=owner_id,
                    name="두 번째 Workspace",
                    lifecycle_status="active",
                ),
                Workspace(
                    workspace_id=_id(2, 3),
                    owner_id=other_owner_id,
                    name="다른 Owner Workspace",
                    lifecycle_status="active",
                ),
            ]
        )
        assets = [
            Asset(
                asset_id=_id(3, index),
                owner_id=owner_id,
                workspace_id=(
                    None
                    if index == 1
                    else first_workspace_id
                    if index <= 5
                    else second_workspace_id
                ),
                asset_type=(AssetType.MUSIC if index % 2 else AssetType.VOCAL),
                lifecycle_status="active",
                created_at=origin - timedelta(minutes=index // 3),
                updated_at=origin - timedelta(minutes=index // 3),
                deleted_at=(origin if index == 7 else None),
            )
            for index in range(1, 9)
        ]
        assets.append(
            Asset(
                asset_id=_id(3, 99),
                owner_id=other_owner_id,
                workspace_id=_id(2, 3),
                asset_type=AssetType.MUSIC,
                lifecycle_status="active",
                created_at=origin,
                updated_at=origin,
            )
        )
        session.add_all(assets)
    return owner_id, first_workspace_id, second_workspace_id, assets


def _decode_payload(token: str) -> dict[str, object]:
    payload_part = token.split(".", maxsplit=1)[0]
    padding = "=" * (-len(payload_part) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_part + padding))


def test_asset_cursor_reuses_created_at_v1_payload() -> None:
    codec = CursorCodec(TEST_KEY)
    owner_id = _id(1, 1)
    fingerprint = filter_fingerprint(
        {
            "asset_type": None,
            "include_deleted": False,
            "owner_id": str(owner_id),
            "sort": "created_at_desc",
            "workspace_id": None,
        }
    )
    position_time = datetime(2026, 8, 8, 12, 0, tzinfo=UTC)

    token = codec.encode(
        resource="asset",
        last_created_at=position_time,
        last_id=_id(3, 1),
        filter_hash=fingerprint,
        limit=20,
    )
    position = codec.decode(
        token,
        expected_resource="asset",
        expected_filter_hash=fingerprint,
        expected_limit=20,
    )

    payload = _decode_payload(token)
    assert payload == {
        "direction": "next",
        "filter_hash": fingerprint,
        "last_created_at": "2026-08-08T12:00:00Z",
        "last_id": str(_id(3, 1)),
        "limit": 20,
        "resource": "asset",
        "sort": "created_at_desc",
        "v": 1,
    }
    assert position.last_created_at == position_time
    assert position.last_id == _id(3, 1)


def test_asset_cursor_rejects_tampering_resource_limit_and_oversize() -> None:
    codec = CursorCodec(TEST_KEY)
    fingerprint = "a" * 64
    token = codec.encode(
        resource="asset",
        last_created_at=datetime(2026, 8, 8, tzinfo=UTC),
        last_id=_id(3, 1),
        filter_hash=fingerprint,
        limit=20,
    )

    with pytest.raises(InvalidCursorError):
        codec.decode(
            token[:-1] + ("A" if token[-1] != "A" else "B"),
            expected_resource="asset",
            expected_filter_hash=fingerprint,
            expected_limit=20,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode(
            token,
            expected_resource="workspace",
            expected_filter_hash=fingerprint,
            expected_limit=20,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode(
            token,
            expected_resource="asset",
            expected_filter_hash=fingerprint,
            expected_limit=21,
        )
    with pytest.raises(InvalidCursorError):
        codec.decode(
            "x" * 2049,
            expected_resource="asset",
            expected_filter_hash=fingerprint,
            expected_limit=20,
        )


def test_asset_page_is_owner_scoped_stable_and_excludes_deleted(
    session_factory,
) -> None:
    owner_id, _, _, assets = _seed(session_factory)
    service = AssetService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    collected: list[Asset] = []
    cursor = None

    for _ in range(10):
        page = service.list_asset_page(owner_id=owner_id, cursor=cursor, limit=2)
        collected.extend(page.items)
        if not page.has_more:
            assert page.next_cursor is None
            break
        assert page.next_cursor is not None
        cursor = page.next_cursor
    else:
        pytest.fail("Asset cursor가 종료되지 않았습니다.")

    expected = sorted(
        [
            item
            for item in assets
            if item.owner_id == owner_id and item.deleted_at is None
        ],
        key=lambda item: (item.created_at, item.asset_id),
        reverse=True,
    )
    assert [item.asset_id for item in collected] == [item.asset_id for item in expected]
    assert len({item.asset_id for item in collected}) == len(collected)
    assert any(item.workspace_id is None for item in collected)


def test_asset_page_returns_terminal_empty_page(session_factory) -> None:
    service = AssetService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    page = service.list_asset_page(owner_id=_id(1, 1), limit=20)

    assert page.items == ()
    assert page.has_more is False
    assert page.next_cursor is None
    assert page.limit == 20


def test_asset_page_filters_workspace_and_type_and_binds_cursor(
    session_factory,
) -> None:
    owner_id, first_workspace_id, second_workspace_id, _ = _seed(session_factory)
    service = AssetService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    first = service.list_asset_page(
        owner_id=owner_id,
        workspace_id=first_workspace_id,
        asset_type=AssetType.MUSIC,
        limit=1,
    )
    assert all(item.workspace_id == first_workspace_id for item in first.items)
    assert all(item.asset_type is AssetType.MUSIC for item in first.items)
    assert first.next_cursor is not None

    with pytest.raises(InvalidCursorError):
        service.list_asset_page(
            owner_id=owner_id,
            workspace_id=second_workspace_id,
            asset_type=AssetType.MUSIC,
            cursor=first.next_cursor,
            limit=1,
        )
    with pytest.raises(InvalidCursorError):
        service.list_asset_page(
            owner_id=owner_id,
            workspace_id=first_workspace_id,
            asset_type=AssetType.VOCAL,
            cursor=first.next_cursor,
            limit=1,
        )
    with pytest.raises(InvalidCursorError):
        service.list_asset_page(
            owner_id=_id(1, 2),
            workspace_id=first_workspace_id,
            asset_type=AssetType.MUSIC,
            cursor=first.next_cursor,
            limit=1,
        )


def test_asset_page_rejects_cross_owner_workspace_and_invalid_limit(
    session_factory,
) -> None:
    owner_id, _, _, _ = _seed(session_factory)
    service = AssetService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    with pytest.raises(ResourceNotFoundError, match="Workspace"):
        service.list_asset_page(
            owner_id=owner_id,
            workspace_id=_id(2, 3),
        )
    for invalid_limit in (True, False, 0, 101, 1.0, "10"):
        with pytest.raises(InvalidLimitError):
            service.list_asset_page(owner_id=owner_id, limit=invalid_limit)  # type: ignore[arg-type]


def test_asset_page_handles_insert_and_soft_delete_between_pages(
    session_factory,
) -> None:
    owner_id, first_workspace_id, _, _ = _seed(session_factory)
    service = AssetService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    first = service.list_asset_page(owner_id=owner_id, limit=2)
    assert first.next_cursor is not None
    first_ids = {item.asset_id for item in first.items}

    with session_factory.begin() as session:
        session.add(
            Asset(
                asset_id=_id(3, 100),
                owner_id=owner_id,
                workspace_id=first_workspace_id,
                asset_type=AssetType.MUSIC,
                lifecycle_status="active",
                created_at=datetime(2026, 8, 9, tzinfo=UTC),
                updated_at=datetime(2026, 8, 9, tzinfo=UTC),
            )
        )
        next_candidate = session.get(Asset, _id(3, 4))
        assert next_candidate is not None
        next_candidate.deleted_at = datetime(2026, 8, 9, tzinfo=UTC)

    following = service.list_asset_page(
        owner_id=owner_id,
        cursor=first.next_cursor,
        limit=2,
    )
    following_ids = {item.asset_id for item in following.items}
    assert _id(3, 100) not in following_ids
    assert _id(3, 4) not in following_ids
    assert first_ids.isdisjoint(following_ids)
