"""PayloadLocator CAS와 verified durable staging I/O를 짧은 transaction 밖에서 조정한다."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorErrorCode,
    PayloadLocatorRecord,
    PayloadLocatorStatus,
)
from backend.services.workspace.payload_locator_service import PayloadLocatorService
from backend.storage.verified_payload_staging import (
    ExpectedPayloadFacts,
    VerifiedPayloadStagingError,
    VerifiedPayloadStagingErrorCode,
    VerifiedPayloadStagingPort,
    VerifiedStagedPayload,
)


class PayloadStagingServiceErrorCode(StrEnum):
    CLAIM_REQUIRED = "PAYLOAD_STAGING_ACTIVE_CLAIM_REQUIRED"
    CANCELLATION_REQUESTED = "PAYLOAD_STAGING_CANCELLATION_REQUESTED"
    INVALID_AUTHORITY = "PAYLOAD_STAGING_INVALID_AUTHORITY"
    ORPHAN_CLEANUP_FAILED = "PAYLOAD_STAGING_ORPHAN_CLEANUP_FAILED"


class PayloadStagingServiceError(RuntimeError):
    def __init__(self, code: PayloadStagingServiceErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class PayloadStagingAuthority:
    workspace_job_id: UUID
    rights_granted: bool
    claim_active: bool
    cancellation_requested: bool

    def __post_init__(self) -> None:
        if (
            not isinstance(self.workspace_job_id, UUID)
            or type(self.rights_granted) is not bool
            or type(self.claim_active) is not bool
            or type(self.cancellation_requested) is not bool
        ):
            raise PayloadStagingServiceError(PayloadStagingServiceErrorCode.INVALID_AUTHORITY)


class PayloadStagingService:
    """권한을 I/O 전후 재검증하고 source_bound→verified_staged CAS를 수행한다."""

    def __init__(
        self,
        locator_service: PayloadLocatorService,
        staging: VerifiedPayloadStagingPort,
    ) -> None:
        self._locators = locator_service
        self._staging = staging

    def stage(
        self,
        locator_id: object,
        chunks: Iterable[bytes],
        authority_provider: Callable[[], PayloadStagingAuthority],
    ) -> PayloadLocatorRecord:
        before = self._require_authority(authority_provider)
        source_bound = self._locators.resolve_for_acquisition(
            locator_id,
            workspace_job_id=before.workspace_job_id,
            rights_granted=before.rights_granted,
        )
        expected = ExpectedPayloadFacts(
            checksum_algorithm=source_bound.issue.expected_checksum_algorithm,
            payload_checksum=source_bound.issue.expected_payload_checksum,
            size_bytes=source_bound.issue.expected_size_bytes,
            media_type=source_bound.issue.expected_media_type,
        )
        staged = self._staging.stage_verified(source_bound.locator_uuid, chunks, expected)

        try:
            after = self._require_authority(authority_provider)
            if after.workspace_job_id != before.workspace_job_id:
                raise PayloadStagingServiceError(PayloadStagingServiceErrorCode.INVALID_AUTHORITY)
        except PayloadStagingServiceError:
            self._cleanup_unadopted(locator_id, staged)
            raise

        try:
            return self._locators.transition_to_verified_staged(
                locator_id,
                expected_revision=source_bound.lifecycle_revision,
                facts=staged.as_locator_facts(),
            )
        except PayloadLocatorError:
            current = self._locators.get(locator_id)
            if _record_references(current, staged):
                return current
            self._delete_or_raise(staged)
            if current.revoked:
                raise PayloadLocatorError(PayloadLocatorErrorCode.REVOKED) from None
            raise

    def _cleanup_unadopted(self, locator_id: object, staged: VerifiedStagedPayload) -> None:
        current = self._locators.get(locator_id)
        if not _record_references(current, staged):
            self._delete_or_raise(staged)

    def _delete_or_raise(self, staged: VerifiedStagedPayload) -> None:
        try:
            self._staging.delete_verified(staged)
        except VerifiedPayloadStagingError as cleanup_error:
            if cleanup_error.code is not VerifiedPayloadStagingErrorCode.CONTENT_MISSING:
                raise PayloadStagingServiceError(
                    PayloadStagingServiceErrorCode.ORPHAN_CLEANUP_FAILED
                ) from cleanup_error

    @staticmethod
    def _require_authority(
        authority_provider: Callable[[], PayloadStagingAuthority],
    ) -> PayloadStagingAuthority:
        try:
            authority = authority_provider()
        except PayloadStagingServiceError:
            raise
        except Exception:
            raise PayloadStagingServiceError(
                PayloadStagingServiceErrorCode.INVALID_AUTHORITY
            ) from None
        if not isinstance(authority, PayloadStagingAuthority):
            raise PayloadStagingServiceError(PayloadStagingServiceErrorCode.INVALID_AUTHORITY)
        if not authority.claim_active:
            raise PayloadStagingServiceError(PayloadStagingServiceErrorCode.CLAIM_REQUIRED)
        if authority.cancellation_requested:
            raise PayloadStagingServiceError(PayloadStagingServiceErrorCode.CANCELLATION_REQUESTED)
        return authority


def staged_payload_from_record(record: PayloadLocatorRecord) -> VerifiedStagedPayload:
    """검증 완료 DB record를 storage port의 안전한 값 객체로 변환한다."""

    if (
        record.staging_status is not PayloadLocatorStatus.VERIFIED_STAGED
        or record.staging_backend is None
        or record.staging_key is None
        or record.actual_checksum_algorithm is None
        or record.actual_payload_checksum is None
        or record.actual_size_bytes is None
        or record.actual_media_type is None
        or record.verified_at is None
    ):
        raise PayloadStagingServiceError(PayloadStagingServiceErrorCode.INVALID_AUTHORITY)
    return VerifiedStagedPayload(
        staging_backend=record.staging_backend,
        staging_key=record.staging_key,
        checksum_algorithm=record.actual_checksum_algorithm,
        payload_checksum=record.actual_payload_checksum,
        size_bytes=record.actual_size_bytes,
        media_type=record.actual_media_type,
        verified_at=record.verified_at,
    )


def _record_references(record: PayloadLocatorRecord, staged: VerifiedStagedPayload) -> bool:
    return (
        record.staging_status is PayloadLocatorStatus.VERIFIED_STAGED
        and record.staging_backend == staged.staging_backend
        and record.staging_key == staged.staging_key
        and record.actual_checksum_algorithm == staged.checksum_algorithm
        and record.actual_payload_checksum == staged.payload_checksum
        and record.actual_size_bytes == staged.size_bytes
        and record.actual_media_type == staged.media_type
    )
