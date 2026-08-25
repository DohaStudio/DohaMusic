"""SQLAlchemy/SQLite adapter for durable PayloadLocator persistence."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorErrorCode,
    PayloadLocatorIssue,
    PayloadLocatorRecord,
    PayloadLocatorRevocationReason,
    PayloadLocatorStatus,
)
from backend.models.workspace.payload_locator import PayloadLocator
from backend.models.workspace.provider_job import ProviderJobBinding
from backend.repositories.workspace.payload_locator_port import (
    PayloadLocatorRepositoryPort,
)


class PayloadLocatorRepository(PayloadLocatorRepositoryPort):
    """Flush-only adapter; transaction completion belongs to the calling Service."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def issue(
        self,
        issue: PayloadLocatorIssue,
        *,
        locator_uuid: UUID,
    ) -> PayloadLocatorRecord:
        binding = self.session.get(ProviderJobBinding, issue.provider_job_binding_id)
        if binding is None or binding.workspace_job_id != issue.workspace_job_id:
            raise PayloadLocatorError(PayloadLocatorErrorCode.WORKSPACE_BINDING_MISMATCH)

        replay = self._find_replay_candidate(issue)
        if replay is not None:
            return _require_exact_replay(replay, issue)
        if self.session.get(PayloadLocator, locator_uuid) is not None:
            raise PayloadLocatorError(PayloadLocatorErrorCode.LOCATOR_ID_COLLISION)

        row = PayloadLocator(
            payload_locator_id=locator_uuid,
            workspace_job_id=issue.workspace_job_id,
            provider_job_binding_id=issue.provider_job_binding_id,
            payload_ordinal=issue.payload_ordinal,
            provider_artifact_id=issue.provider_artifact_id,
            role=issue.role,
            source_kind=issue.source_kind,
            source_id=issue.source_id,
            artifact_kind=issue.artifact_kind,
            expected_checksum_algorithm=issue.expected_checksum_algorithm,
            expected_payload_checksum=issue.expected_payload_checksum,
            expected_size_bytes=issue.expected_size_bytes,
            expected_media_type=issue.expected_media_type,
            source_available_until=issue.source_available_until,
            locator_expires_at=issue.locator_expires_at,
            staging_status=PayloadLocatorStatus.SOURCE_BOUND.value,
            lifecycle_revision=0,
        )
        try:
            with self.session.begin_nested():
                self.session.add(row)
                self.session.flush()
        except IntegrityError:
            replay = self._find_replay_candidate(issue)
            if replay is not None:
                return _require_exact_replay(replay, issue)
            if self.session.get(PayloadLocator, locator_uuid) is not None:
                raise PayloadLocatorError(PayloadLocatorErrorCode.LOCATOR_ID_COLLISION) from None
            raise PayloadLocatorError(PayloadLocatorErrorCode.RESULT_REPLAY_CONFLICT) from None
        return _to_record(row)

    def get_by_locator_uuid(self, locator_uuid: UUID) -> PayloadLocatorRecord | None:
        row = self.session.get(PayloadLocator, locator_uuid)
        return _to_record(row) if row is not None else None

    def get_for_binding(self, provider_job_binding_id: UUID) -> tuple[PayloadLocatorRecord, ...]:
        rows = self.session.scalars(
            select(PayloadLocator)
            .where(PayloadLocator.provider_job_binding_id == provider_job_binding_id)
            .order_by(PayloadLocator.payload_ordinal)
        )
        return tuple(_to_record(row) for row in rows)

    def get_by_binding_and_ordinal(
        self, provider_job_binding_id: UUID, payload_ordinal: int
    ) -> PayloadLocatorRecord | None:
        row = self.session.scalar(
            select(PayloadLocator).where(
                PayloadLocator.provider_job_binding_id == provider_job_binding_id,
                PayloadLocator.payload_ordinal == payload_ordinal,
            )
        )
        return _to_record(row) if row is not None else None

    def compare_and_set(
        self,
        locator_uuid: UUID,
        *,
        expected_revision: int,
        expected_status: PayloadLocatorStatus,
        require_not_revoked: bool,
        values: dict[str, object],
    ) -> PayloadLocatorRecord:
        predicates = [
            PayloadLocator.payload_locator_id == locator_uuid,
            PayloadLocator.lifecycle_revision == expected_revision,
            PayloadLocator.staging_status == expected_status.value,
        ]
        if require_not_revoked:
            predicates.append(PayloadLocator.revoked_at.is_(None))
        statement = (
            update(PayloadLocator)
            .where(*predicates)
            .values(
                **values,
                lifecycle_revision=expected_revision + 1,
                updated_at=datetime.now(UTC),
            )
        )
        result = self.session.execute(statement)
        self.session.flush()
        if result.rowcount != 1:
            current = self.session.get(PayloadLocator, locator_uuid)
            if current is None:
                raise PayloadLocatorError(PayloadLocatorErrorCode.NOT_FOUND)
            if current.lifecycle_revision != expected_revision:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)
            if require_not_revoked and current.revoked_at is not None:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED)
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        row = self.session.get(PayloadLocator, locator_uuid)
        if row is None:  # pragma: no cover - guarded by successful UPDATE
            raise PayloadLocatorError(PayloadLocatorErrorCode.NOT_FOUND)
        self.session.refresh(row)
        return _to_record(row)

    def _find_replay_candidate(self, issue: PayloadLocatorIssue) -> PayloadLocator | None:
        by_ordinal = self.session.scalar(
            select(PayloadLocator).where(
                PayloadLocator.provider_job_binding_id == issue.provider_job_binding_id,
                PayloadLocator.payload_ordinal == issue.payload_ordinal,
            )
        )
        by_source = self.session.scalar(
            select(PayloadLocator).where(
                PayloadLocator.provider_job_binding_id == issue.provider_job_binding_id,
                PayloadLocator.provider_artifact_id == issue.provider_artifact_id,
                PayloadLocator.role == issue.role,
                PayloadLocator.source_id == issue.source_id,
            )
        )
        if by_ordinal is not None and by_source is not None:
            if by_ordinal.payload_locator_id != by_source.payload_locator_id:
                raise PayloadLocatorError(PayloadLocatorErrorCode.RESULT_REPLAY_CONFLICT)
            return by_ordinal
        return by_ordinal or by_source


class SqlAlchemyPayloadLocatorPersistence:
    """Creates short SQLAlchemy transactions without exposing them to the Service."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    @contextmanager
    def transaction(self) -> Iterator[PayloadLocatorRepositoryPort]:
        with self._session_factory() as session, session.begin():
            yield PayloadLocatorRepository(session)


def _require_exact_replay(row: PayloadLocator, issue: PayloadLocatorIssue) -> PayloadLocatorRecord:
    record = _to_record(row)
    if record.immutable_facts != issue.immutable_facts:
        raise PayloadLocatorError(PayloadLocatorErrorCode.RESULT_REPLAY_CONFLICT)
    return record


def _to_record(row: PayloadLocator) -> PayloadLocatorRecord:
    issue = PayloadLocatorIssue(
        workspace_job_id=row.workspace_job_id,
        provider_job_binding_id=row.provider_job_binding_id,
        payload_ordinal=row.payload_ordinal,
        provider_artifact_id=row.provider_artifact_id,
        role=row.role,
        source_kind=row.source_kind,
        source_id=row.source_id,
        artifact_kind=row.artifact_kind,
        expected_checksum_algorithm=row.expected_checksum_algorithm,
        expected_payload_checksum=row.expected_payload_checksum,
        expected_size_bytes=row.expected_size_bytes,
        expected_media_type=row.expected_media_type,
        source_available_until=_as_utc(row.source_available_until),
        locator_expires_at=_as_utc(row.locator_expires_at),
    )
    return PayloadLocatorRecord(
        locator_uuid=row.payload_locator_id,
        issue=issue,
        staging_status=PayloadLocatorStatus(row.staging_status),
        staging_backend=row.staging_backend,
        staging_key=row.staging_key,
        actual_checksum_algorithm=row.actual_checksum_algorithm,
        actual_payload_checksum=row.actual_payload_checksum,
        actual_size_bytes=row.actual_size_bytes,
        actual_media_type=row.actual_media_type,
        verified_at=_as_utc(row.verified_at),
        ingested_artifact_id=row.ingested_artifact_id,
        ingested_at=_as_utc(row.ingested_at),
        revoked_at=_as_utc(row.revoked_at),
        revocation_reason=(
            PayloadLocatorRevocationReason(row.revocation_reason)
            if row.revocation_reason is not None
            else None
        ),
        cleanup_requested_at=_as_utc(row.cleanup_requested_at),
        cleanup_completed_at=_as_utc(row.cleanup_completed_at),
        lifecycle_revision=row.lifecycle_revision,
        created_at=_as_utc(row.created_at),
        updated_at=_as_utc(row.updated_at),
    )


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
