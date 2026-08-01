"""Transaction-participating idempotency record operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.idempotency_record import IdempotencyRecord


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    replayed: bool


class IdempotencyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def hash_key(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def claim(
        self,
        *,
        scope: str,
        key: str,
        fingerprint: str,
        now: datetime,
        ttl_hours: int = 24,
    ) -> IdempotencyClaim:
        key_hash = self.hash_key(key)
        existing = self.session.scalar(
            select(IdempotencyRecord).where(
                IdempotencyRecord.scope == scope,
                IdempotencyRecord.key_hash == key_hash,
            )
        )
        if existing is not None and _as_utc(existing.expires_at) <= now:
            self.session.delete(existing)
            self.session.flush()
            existing = None
        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise ValueError("IDEMPOTENCY_CONFLICT")
            if existing.status != "COMPLETED" or existing.resource_id is None:
                raise ValueError("IDEMPOTENCY_IN_PROGRESS")
            return IdempotencyClaim(existing, replayed=True)

        record = IdempotencyRecord(
            scope=scope,
            key_hash=key_hash,
            request_fingerprint=fingerprint,
            status="IN_PROGRESS",
            expires_at=now + timedelta(hours=ttl_hours),
        )
        self.session.add(record)
        self.session.flush()
        return IdempotencyClaim(record, replayed=False)

    def complete(
        self,
        record: IdempotencyRecord,
        *,
        resource_type: str,
        resource_id: str,
        response_status: int,
    ) -> None:
        record.status = "COMPLETED"
        record.resource_type = resource_type
        record.resource_id = resource_id
        record.response_status = response_status

    def release(self, record: IdempotencyRecord) -> None:
        self.session.delete(record)

    def release_in_progress_for_scope_prefix(self, prefix: str) -> int:
        records = list(
            self.session.scalars(
                select(IdempotencyRecord).where(
                    IdempotencyRecord.status == "IN_PROGRESS",
                    IdempotencyRecord.scope.startswith(prefix),
                )
            )
        )
        for record in records:
            self.session.delete(record)
        return len(records)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
