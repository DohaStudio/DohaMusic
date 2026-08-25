"""Transaction-participating idempotency record operations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.idempotency_completion import (
    IdempotencyCompletionResult,
    IdempotencyResultType,
)
from backend.models.idempotency_record import IdempotencyRecord


@dataclass(frozen=True, slots=True)
class IdempotencyClaim:
    record: IdempotencyRecord
    replayed: bool
    completion_result: IdempotencyCompletionResult | None = None


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
            return IdempotencyClaim(
                existing,
                replayed=True,
                completion_result=_read_completion_result(existing),
            )

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

    def claim_with_result(
        self,
        *,
        scope: str,
        key: str,
        fingerprint: str,
        now: datetime,
        ttl_hours: int = 24,
    ) -> IdempotencyClaim:
        """Claim a new mutation or replay a complete versioned result."""

        claim = self.claim(
            scope=scope,
            key=key,
            fingerprint=fingerprint,
            now=now,
            ttl_hours=ttl_hours,
        )
        if claim.replayed and claim.completion_result is None:
            raise ValueError("IDEMPOTENCY_RESULT_REQUIRED")
        return claim

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

    def complete_with_result(
        self,
        record: IdempotencyRecord,
        *,
        resource_type: str,
        resource_id: str,
        response_status: int,
        completion_result: IdempotencyCompletionResult,
    ) -> None:
        """Persist a canonical replay result without committing the transaction."""

        if not isinstance(completion_result, IdempotencyCompletionResult):
            raise TypeError("completion_result must be IdempotencyCompletionResult")
        self.complete(
            record,
            resource_type=resource_type,
            resource_id=resource_id,
            response_status=response_status,
        )
        record.completed_revision = completion_result.completed_revision
        record.result_type = completion_result.result_type.value
        record.result_version = completion_result.result_version
        record.result_payload = completion_result.payload_for_storage()

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


def _read_completion_result(
    record: IdempotencyRecord,
) -> IdempotencyCompletionResult | None:
    fields = (
        record.completed_revision,
        record.result_type,
        record.result_version,
        record.result_payload,
    )
    if all(value is None for value in fields):
        return None
    if any(value is None for value in fields):
        raise ValueError("IDEMPOTENCY_RESULT_INCOMPLETE")
    try:
        result_type = IdempotencyResultType(str(record.result_type))
        return IdempotencyCompletionResult(
            result_version=record.result_version,
            completed_revision=record.completed_revision,
            result_type=result_type,
            result_payload=record.result_payload,
        )
    except (TypeError, ValueError):
        raise ValueError("IDEMPOTENCY_RESULT_INVALID") from None
