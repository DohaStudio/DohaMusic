"""Application lifecycle for durable PayloadLocator reconciliation facts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorErrorCode,
    PayloadLocatorIssue,
    PayloadLocatorRecord,
    PayloadLocatorRevocationReason,
    PayloadLocatorStatus,
    VerifiedStagingFacts,
    parse_locator_id,
)
from backend.repositories.workspace.payload_locator_port import (
    PayloadLocatorPersistencePort,
)

MAX_LOCATOR_ID_ATTEMPTS = 3


class PayloadLocatorService:
    """Owns short DB transactions; performs no network or file I/O."""

    def __init__(
        self,
        persistence: PayloadLocatorPersistencePort,
        *,
        id_factory: Callable[[], UUID] = uuid4,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._persistence = persistence
        self._id_factory = id_factory
        self._clock = clock or (lambda: datetime.now(UTC))

    def issue(self, issue: PayloadLocatorIssue) -> PayloadLocatorRecord:
        last_collision: PayloadLocatorError | None = None
        for _ in range(MAX_LOCATOR_ID_ATTEMPTS):
            locator_uuid = self._new_uuid()
            try:
                with self._persistence.transaction() as repository:
                    return repository.issue(issue, locator_uuid=locator_uuid)
            except PayloadLocatorError as error:
                if error.code is not PayloadLocatorErrorCode.LOCATOR_ID_COLLISION:
                    raise
                last_collision = error
        raise last_collision or PayloadLocatorError(PayloadLocatorErrorCode.LOCATOR_ID_COLLISION)

    def get(self, locator_id: object) -> PayloadLocatorRecord:
        locator_uuid = parse_locator_id(locator_id)
        with self._persistence.transaction() as repository:
            record = repository.get_by_locator_uuid(locator_uuid)
        if record is None:
            raise PayloadLocatorError(PayloadLocatorErrorCode.NOT_FOUND)
        return record

    def get_for_binding(self, provider_job_binding_id: UUID) -> tuple[PayloadLocatorRecord, ...]:
        with self._persistence.transaction() as repository:
            return repository.get_for_binding(provider_job_binding_id)

    def resolve_for_acquisition(
        self,
        locator_id: object,
        *,
        workspace_job_id: UUID,
        rights_granted: bool,
    ) -> PayloadLocatorRecord:
        record = self.get(locator_id)
        self._require_access_context(record, workspace_job_id, rights_granted)
        if record.staging_status is not PayloadLocatorStatus.SOURCE_BOUND:
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        now = self._now()
        if (
            record.issue.source_available_until is not None
            and now >= record.issue.source_available_until
        ):
            raise PayloadLocatorError(PayloadLocatorErrorCode.SOURCE_EXPIRED)
        self._require_policy_active(record, now)
        return record

    def resolve_verified_staging(
        self,
        locator_id: object,
        *,
        workspace_job_id: UUID,
        rights_granted: bool,
    ) -> PayloadLocatorRecord:
        record = self.get(locator_id)
        self._require_access_context(record, workspace_job_id, rights_granted)
        if record.staging_status is not PayloadLocatorStatus.VERIFIED_STAGED:
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        self._require_policy_active(record, self._now())
        return record

    def transition_to_verified_staged(
        self,
        locator_id: object,
        *,
        expected_revision: int,
        facts: VerifiedStagingFacts,
    ) -> PayloadLocatorRecord:
        self._validate_revision(expected_revision)
        locator_uuid = parse_locator_id(locator_id)
        with self._persistence.transaction() as repository:
            current = self._require_record(repository.get_by_locator_uuid(locator_uuid))
            if current.lifecycle_revision != expected_revision:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)
            if current.staging_status is not PayloadLocatorStatus.SOURCE_BOUND:
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            if current.revoked:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED)
            self._require_policy_active(current, self._now())
            if (
                facts.actual_checksum_algorithm != current.issue.expected_checksum_algorithm
                or facts.actual_payload_checksum != current.issue.expected_payload_checksum
                or facts.actual_size_bytes != current.issue.expected_size_bytes
                or facts.actual_media_type != current.issue.expected_media_type
            ):
                raise PayloadLocatorError(PayloadLocatorErrorCode.INTEGRITY_MISMATCH)
            return repository.compare_and_set(
                locator_uuid,
                expected_revision=expected_revision,
                expected_status=PayloadLocatorStatus.SOURCE_BOUND,
                require_not_revoked=True,
                values={
                    "staging_status": PayloadLocatorStatus.VERIFIED_STAGED.value,
                    "staging_backend": facts.staging_backend,
                    "staging_key": facts.staging_key,
                    "actual_checksum_algorithm": facts.actual_checksum_algorithm,
                    "actual_payload_checksum": facts.actual_payload_checksum,
                    "actual_size_bytes": facts.actual_size_bytes,
                    "actual_media_type": facts.actual_media_type,
                    "verified_at": facts.verified_at,
                },
            )

    def mark_ingested(
        self,
        locator_id: object,
        *,
        expected_revision: int,
        ingested_artifact_id: UUID,
        ingested_at: datetime,
    ) -> PayloadLocatorRecord:
        self._validate_revision(expected_revision)
        if not isinstance(ingested_artifact_id, UUID) or not _is_utc(ingested_at):
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        locator_uuid = parse_locator_id(locator_id)
        with self._persistence.transaction() as repository:
            current = self._require_record(repository.get_by_locator_uuid(locator_uuid))
            if current.lifecycle_revision != expected_revision:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)
            if current.staging_status is not PayloadLocatorStatus.VERIFIED_STAGED:
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            if current.revoked:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED)
            self._require_policy_active(current, self._now())
            if current.verified_at is None or ingested_at < current.verified_at:
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            return repository.compare_and_set(
                locator_uuid,
                expected_revision=expected_revision,
                expected_status=PayloadLocatorStatus.VERIFIED_STAGED,
                require_not_revoked=True,
                values={
                    "staging_status": PayloadLocatorStatus.INGESTED.value,
                    "ingested_artifact_id": ingested_artifact_id,
                    "ingested_at": ingested_at,
                },
            )

    def mark_cleanup_pending(
        self,
        locator_id: object,
        *,
        expected_revision: int,
        requested_at: datetime,
    ) -> PayloadLocatorRecord:
        self._validate_revision(expected_revision)
        if not _is_utc(requested_at):
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        locator_uuid = parse_locator_id(locator_id)
        with self._persistence.transaction() as repository:
            current = self._require_record(repository.get_by_locator_uuid(locator_uuid))
            if current.lifecycle_revision != expected_revision:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)
            allowed = current.staging_status is PayloadLocatorStatus.INGESTED or (
                current.staging_status is PayloadLocatorStatus.VERIFIED_STAGED and current.revoked
            )
            if not allowed:
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            lower_bound = current.ingested_at or current.verified_at
            if lower_bound is None or requested_at < lower_bound:
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            return repository.compare_and_set(
                locator_uuid,
                expected_revision=expected_revision,
                expected_status=current.staging_status,
                require_not_revoked=False,
                values={
                    "staging_status": PayloadLocatorStatus.CLEANUP_PENDING.value,
                    "cleanup_requested_at": requested_at,
                },
            )

    def mark_cleaned(
        self,
        locator_id: object,
        *,
        expected_revision: int,
        completed_at: datetime,
    ) -> PayloadLocatorRecord:
        self._validate_revision(expected_revision)
        if not _is_utc(completed_at):
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        locator_uuid = parse_locator_id(locator_id)
        with self._persistence.transaction() as repository:
            current = self._require_record(repository.get_by_locator_uuid(locator_uuid))
            if current.lifecycle_revision != expected_revision:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)
            if (
                current.staging_status is not PayloadLocatorStatus.CLEANUP_PENDING
                or current.cleanup_requested_at is None
                or completed_at < current.cleanup_requested_at
            ):
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            return repository.compare_and_set(
                locator_uuid,
                expected_revision=expected_revision,
                expected_status=PayloadLocatorStatus.CLEANUP_PENDING,
                require_not_revoked=False,
                values={
                    "staging_status": PayloadLocatorStatus.CLEANED.value,
                    "cleanup_completed_at": completed_at,
                },
            )

    def revoke(
        self,
        locator_id: object,
        *,
        expected_revision: int,
        reason: PayloadLocatorRevocationReason,
        revoked_at: datetime,
    ) -> PayloadLocatorRecord:
        self._validate_revision(expected_revision)
        if not isinstance(reason, PayloadLocatorRevocationReason) or not _is_utc(revoked_at):
            raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
        locator_uuid = parse_locator_id(locator_id)
        with self._persistence.transaction() as repository:
            current = self._require_record(repository.get_by_locator_uuid(locator_uuid))
            if current.revoked:
                if current.revocation_reason is reason:
                    return current
                raise PayloadLocatorError(PayloadLocatorErrorCode.ILLEGAL_TRANSITION)
            return repository.compare_and_set(
                locator_uuid,
                expected_revision=expected_revision,
                expected_status=current.staging_status,
                require_not_revoked=True,
                values={"revoked_at": revoked_at, "revocation_reason": reason.value},
            )

    @staticmethod
    def _require_record(
        record: PayloadLocatorRecord | None,
    ) -> PayloadLocatorRecord:
        if record is None:
            raise PayloadLocatorError(PayloadLocatorErrorCode.NOT_FOUND)
        return record

    @staticmethod
    def _validate_revision(value: object) -> None:
        if type(value) is not int or value < 0:
            raise PayloadLocatorError(PayloadLocatorErrorCode.REVISION_CONFLICT)

    @staticmethod
    def _require_access_context(
        record: PayloadLocatorRecord,
        workspace_job_id: UUID,
        rights_granted: bool,
    ) -> None:
        if type(rights_granted) is not bool or not rights_granted:
            raise PayloadLocatorError(PayloadLocatorErrorCode.RIGHTS_REQUIRED)
        if record.issue.workspace_job_id != workspace_job_id:
            raise PayloadLocatorError(PayloadLocatorErrorCode.WORKSPACE_BINDING_MISMATCH)
        if record.revoked:
            raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED)

    @staticmethod
    def _require_policy_active(record: PayloadLocatorRecord, now: datetime) -> None:
        if record.issue.locator_expires_at is not None and now >= record.issue.locator_expires_at:
            raise PayloadLocatorError(PayloadLocatorErrorCode.LOCATOR_EXPIRED)

    def _new_uuid(self) -> UUID:
        try:
            value = self._id_factory()
        except Exception:
            raise PayloadLocatorError(PayloadLocatorErrorCode.LOCATOR_ID_COLLISION) from None
        if not isinstance(value, UUID):
            raise PayloadLocatorError(PayloadLocatorErrorCode.LOCATOR_ID_COLLISION)
        return value

    def _now(self) -> datetime:
        value = self._clock()
        if not _is_utc(value):
            raise PayloadLocatorError(PayloadLocatorErrorCode.INVALID_ISSUE)
        return value


def _is_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
        and value.utcoffset().total_seconds() == 0
    )
