"""HMAC으로 서명한 Workspace REST API cursor 계약."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Mapping
from uuid import UUID

from backend.core.exceptions import CursorConfigurationError, InvalidCursorError

CreatedAtCursorResource = Literal["workspace", "project", "asset", "job"]
CursorResource = Literal[
    "workspace",
    "project",
    "project_asset",
    "asset",
    "composition_snapshot",
    "job",
]
CURSOR_VERSION = 1
CURSOR_DIRECTION = "next"
CURSOR_SORT = "created_at_desc"
PROJECT_ASSET_CURSOR_SORT = "display_order_asc"
COMPOSITION_SNAPSHOT_CURSOR_SORT = "snapshot_version_desc"
MIN_CURSOR_SIGNING_KEY_BYTES = 32
MIN_PAGE_LIMIT = 1
MAX_PAGE_LIMIT = 100
MAX_CURSOR_TOKEN_LENGTH = 2_048
_FILTER_HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
_CREATED_AT_PAYLOAD_FIELDS = {
    "v",
    "resource",
    "direction",
    "sort",
    "last_created_at",
    "last_id",
    "filter_hash",
    "limit",
}
_DISPLAY_ORDER_PAYLOAD_FIELDS = {
    "v",
    "resource",
    "direction",
    "sort",
    "last_display_order",
    "last_id",
    "filter_hash",
    "limit",
}
_SNAPSHOT_VERSION_PAYLOAD_FIELDS = {
    "v",
    "resource",
    "direction",
    "sort",
    "last_snapshot_version",
    "last_id",
    "filter_hash",
    "limit",
}


@dataclass(frozen=True, slots=True)
class CursorPosition:
    """검증을 마친 keyset 위치."""

    last_created_at: datetime
    last_id: UUID


@dataclass(frozen=True, slots=True)
class DisplayOrderCursorPosition:
    """ProjectAsset display order keyset 위치."""

    last_display_order: int
    last_id: UUID


@dataclass(frozen=True, slots=True)
class SnapshotVersionCursorPosition:
    """CompositionSnapshot version DESC keyset 위치."""

    last_snapshot_version: int
    last_id: UUID


class CursorCodec:
    """Canonical JSON payload를 HMAC-SHA256으로 서명한다."""

    def __init__(self, signing_key: str | bytes) -> None:
        key = (
            signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
        )
        if len(key) < MIN_CURSOR_SIGNING_KEY_BYTES:
            raise CursorConfigurationError()
        self._signing_key = key

    def encode(
        self,
        *,
        resource: CreatedAtCursorResource,
        last_created_at: datetime,
        last_id: UUID,
        filter_hash: str,
        limit: int,
    ) -> str:
        normalized_time = _normalize_datetime(last_created_at)
        _validate_created_at_resource(resource)
        _validate_filter_hash(filter_hash)
        _validate_limit(limit)
        payload = {
            "direction": CURSOR_DIRECTION,
            "filter_hash": filter_hash,
            "last_created_at": normalized_time.isoformat().replace("+00:00", "Z"),
            "last_id": str(last_id),
            "limit": limit,
            "resource": resource,
            "sort": CURSOR_SORT,
            "v": CURSOR_VERSION,
        }
        return self._encode_payload(payload)

    def decode(
        self,
        token: str,
        *,
        expected_resource: CreatedAtCursorResource,
        expected_filter_hash: str,
        expected_limit: int,
    ) -> CursorPosition:
        _validate_created_at_resource(expected_resource)
        _validate_filter_hash(expected_filter_hash)
        _validate_limit(expected_limit)
        payload = self._decode_payload(token)
        if set(payload) != _CREATED_AT_PAYLOAD_FIELDS:
            raise InvalidCursorError("payload_shape")
        payload_version = payload.get("v")
        if type(payload_version) is not int or payload_version != CURSOR_VERSION:
            raise InvalidCursorError("version")
        if payload.get("resource") != expected_resource:
            raise InvalidCursorError("resource")
        if payload.get("direction") != CURSOR_DIRECTION:
            raise InvalidCursorError("direction")
        if payload.get("sort") != CURSOR_SORT:
            raise InvalidCursorError("sort")
        if payload.get("filter_hash") != expected_filter_hash:
            raise InvalidCursorError("filter")
        payload_limit = payload.get("limit")
        if type(payload_limit) is not int or payload_limit != expected_limit:
            raise InvalidCursorError("limit")
        try:
            last_created_at = _parse_datetime(payload.get("last_created_at"))
            last_id = UUID(str(payload.get("last_id")))
        except (TypeError, ValueError):
            raise InvalidCursorError("position") from None
        return CursorPosition(last_created_at=last_created_at, last_id=last_id)

    def encode_project_asset(
        self,
        *,
        last_display_order: int,
        last_id: UUID,
        filter_hash: str,
        limit: int,
    ) -> str:
        """ProjectAsset ASC keyset 위치를 서명한다."""

        _validate_display_order(last_display_order)
        _validate_filter_hash(filter_hash)
        _validate_limit(limit)
        payload = {
            "direction": CURSOR_DIRECTION,
            "filter_hash": filter_hash,
            "last_display_order": last_display_order,
            "last_id": str(last_id),
            "limit": limit,
            "resource": "project_asset",
            "sort": PROJECT_ASSET_CURSOR_SORT,
            "v": CURSOR_VERSION,
        }
        return self._encode_payload(payload)

    def decode_project_asset(
        self,
        token: str,
        *,
        expected_filter_hash: str,
        expected_limit: int,
    ) -> DisplayOrderCursorPosition:
        """서명과 ProjectAsset 전용 payload를 엄격하게 검증한다."""

        _validate_filter_hash(expected_filter_hash)
        _validate_limit(expected_limit)
        payload = self._decode_payload(token)
        if set(payload) != _DISPLAY_ORDER_PAYLOAD_FIELDS:
            raise InvalidCursorError("payload_shape")
        payload_version = payload.get("v")
        if type(payload_version) is not int or payload_version != CURSOR_VERSION:
            raise InvalidCursorError("version")
        if payload.get("resource") != "project_asset":
            raise InvalidCursorError("resource")
        if payload.get("direction") != CURSOR_DIRECTION:
            raise InvalidCursorError("direction")
        if payload.get("sort") != PROJECT_ASSET_CURSOR_SORT:
            raise InvalidCursorError("sort")
        if payload.get("filter_hash") != expected_filter_hash:
            raise InvalidCursorError("filter")
        payload_limit = payload.get("limit")
        if type(payload_limit) is not int or payload_limit != expected_limit:
            raise InvalidCursorError("limit")
        last_display_order = payload.get("last_display_order")
        _validate_display_order(last_display_order)
        try:
            last_id = UUID(str(payload.get("last_id")))
        except (TypeError, ValueError):
            raise InvalidCursorError("position") from None
        return DisplayOrderCursorPosition(
            last_display_order=last_display_order,
            last_id=last_id,
        )

    def encode_composition_snapshot(
        self,
        *,
        last_snapshot_version: int,
        last_id: UUID,
        filter_hash: str,
        limit: int,
    ) -> str:
        """CompositionSnapshot DESC keyset 위치를 서명한다."""

        _validate_snapshot_version(last_snapshot_version)
        _validate_filter_hash(filter_hash)
        _validate_limit(limit)
        payload = {
            "direction": CURSOR_DIRECTION,
            "filter_hash": filter_hash,
            "last_id": str(last_id),
            "last_snapshot_version": last_snapshot_version,
            "limit": limit,
            "resource": "composition_snapshot",
            "sort": COMPOSITION_SNAPSHOT_CURSOR_SORT,
            "v": CURSOR_VERSION,
        }
        return self._encode_payload(payload)

    def decode_composition_snapshot(
        self,
        token: str,
        *,
        expected_filter_hash: str,
        expected_limit: int,
    ) -> SnapshotVersionCursorPosition:
        """서명과 CompositionSnapshot 전용 payload를 엄격하게 검증한다."""

        _validate_filter_hash(expected_filter_hash)
        _validate_limit(expected_limit)
        payload = self._decode_payload(token)
        if set(payload) != _SNAPSHOT_VERSION_PAYLOAD_FIELDS:
            raise InvalidCursorError("payload_shape")
        payload_version = payload.get("v")
        if type(payload_version) is not int or payload_version != CURSOR_VERSION:
            raise InvalidCursorError("version")
        if payload.get("resource") != "composition_snapshot":
            raise InvalidCursorError("resource")
        if payload.get("direction") != CURSOR_DIRECTION:
            raise InvalidCursorError("direction")
        if payload.get("sort") != COMPOSITION_SNAPSHOT_CURSOR_SORT:
            raise InvalidCursorError("sort")
        if payload.get("filter_hash") != expected_filter_hash:
            raise InvalidCursorError("filter")
        payload_limit = payload.get("limit")
        if type(payload_limit) is not int or payload_limit != expected_limit:
            raise InvalidCursorError("limit")
        last_snapshot_version = payload.get("last_snapshot_version")
        _validate_snapshot_version(last_snapshot_version)
        try:
            last_id = UUID(str(payload.get("last_id")))
        except (TypeError, ValueError):
            raise InvalidCursorError("position") from None
        return SnapshotVersionCursorPosition(
            last_snapshot_version=last_snapshot_version,
            last_id=last_id,
        )

    def _encode_payload(self, payload: Mapping[str, object]) -> str:
        payload_bytes = _canonical_json(payload)
        signature = hmac.new(self._signing_key, payload_bytes, hashlib.sha256).digest()
        return f"{_base64url_encode(payload_bytes)}.{_base64url_encode(signature)}"

    def _decode_payload(self, token: str) -> dict[str, object]:
        if not isinstance(token, str) or len(token) > MAX_CURSOR_TOKEN_LENGTH:
            raise InvalidCursorError("token_format")
        try:
            payload_part, signature_part = token.split(".")
            payload_bytes = _base64url_decode(payload_part)
            supplied_signature = _base64url_decode(signature_part)
        except (ValueError, UnicodeError, binascii.Error):
            raise InvalidCursorError("token_format") from None
        expected_signature = hmac.new(
            self._signing_key, payload_bytes, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(supplied_signature, expected_signature):
            raise InvalidCursorError("signature")
        try:
            payload = json.loads(payload_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError):
            raise InvalidCursorError("payload_json") from None
        if not isinstance(payload, dict):
            raise InvalidCursorError("payload_shape")
        return payload


def filter_fingerprint(filters: Mapping[str, object]) -> str:
    """민감한 filter 원문 대신 canonical JSON의 SHA-256을 반환한다."""

    try:
        serialized = _canonical_json(dict(filters))
    except (TypeError, ValueError):
        raise InvalidCursorError("filter_shape") from None
    return hashlib.sha256(serialized).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    if not value:
        raise ValueError("empty base64url value")
    padding = "=" * (-len(value) % 4)
    return base64.b64decode(
        (value + padding).encode("ascii"), altchars=b"-_", validate=True
    )


def _normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("datetime must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must include timezone")
    return parsed.astimezone(timezone.utc)


def _validate_created_at_resource(resource: object) -> None:
    if resource not in {"workspace", "project", "asset", "job"}:
        raise InvalidCursorError("resource")


def _validate_filter_hash(filter_hash: object) -> None:
    if not isinstance(filter_hash, str) or not _FILTER_HASH_PATTERN.fullmatch(
        filter_hash
    ):
        raise InvalidCursorError("filter_hash")


def _validate_limit(limit: object) -> None:
    if type(limit) is not int or not MIN_PAGE_LIMIT <= limit <= MAX_PAGE_LIMIT:
        raise InvalidCursorError("limit")


def _validate_display_order(value: object) -> None:
    if type(value) is not int or value < 0:
        raise InvalidCursorError("position")


def _validate_snapshot_version(value: object) -> None:
    if type(value) is not int or value < 1:
        raise InvalidCursorError("position")
