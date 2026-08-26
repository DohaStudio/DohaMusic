"""Trusted DohaVocal payload acquisition을 verified durable staging까지 조정한다."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum

from pydantic import ValidationError

from backend.core.payload_locator import (
    PayloadLocatorError,
    PayloadLocatorErrorCode,
    PayloadLocatorRecord,
    PayloadLocatorStatus,
)
from backend.providers.vocal import (
    DOHAVOCAL_PROVIDER_ID,
    VerifiedVocalPayload,
    VocalPayloadAcquisitionError,
    VocalPayloadAcquisitionErrorCode,
    VocalPayloadAcquisitionPort,
    VocalPayloadAcquisitionRequest,
    VocalPayloadSource,
    VocalProviderPayloadEntry,
)
from backend.services.workspace.payload_locator_service import PayloadLocatorService
from backend.services.workspace.payload_staging_service import (
    PayloadStagingAuthority,
    PayloadStagingService,
    PayloadStagingServiceError,
    PayloadStagingServiceErrorCode,
    staged_payload_from_record,
)
from backend.services.workspace.provider_result_ingestion_service import (
    TrustedPayloadSourceCandidate,
    TrustedProviderResultCandidate,
)
from backend.storage.verified_payload_staging import (
    VerifiedPayloadStagingError,
    VerifiedPayloadStagingErrorCode,
    VerifiedPayloadStagingPort,
)


class VocalPayloadReconciliationErrorCode(StrEnum):
    INVALID_INPUT = "VOCAL_PAYLOAD_RECONCILIATION_INVALID_INPUT"
    BINDING_MISMATCH = "VOCAL_PAYLOAD_RECONCILIATION_BINDING_MISMATCH"
    PAYLOAD_UNAVAILABLE = "VOCAL_PAYLOAD_RECONCILIATION_PAYLOAD_UNAVAILABLE"
    PAYLOAD_EXPIRED = "VOCAL_PAYLOAD_RECONCILIATION_PAYLOAD_EXPIRED"
    ACCESS_DENIED = "VOCAL_PAYLOAD_RECONCILIATION_ACCESS_DENIED"
    TRANSFER_FAILED = "VOCAL_PAYLOAD_RECONCILIATION_TRANSFER_FAILED"
    INTEGRITY_FAILURE = "VOCAL_PAYLOAD_RECONCILIATION_INTEGRITY_FAILURE"
    STAGING_FAILURE = "VOCAL_PAYLOAD_RECONCILIATION_STAGING_FAILURE"
    RIGHTS_DENIED = "VOCAL_PAYLOAD_RECONCILIATION_RIGHTS_DENIED"
    CLAIM_LOST = "VOCAL_PAYLOAD_RECONCILIATION_CLAIM_LOST"
    CANCELLATION_REQUESTED = "VOCAL_PAYLOAD_RECONCILIATION_CANCELLATION_REQUESTED"
    LOCATOR_CONFLICT = "VOCAL_PAYLOAD_RECONCILIATION_LOCATOR_CONFLICT"


_SAFE_MESSAGES = {
    VocalPayloadReconciliationErrorCode.INVALID_INPUT: "Payload reconciliation input is invalid.",
    VocalPayloadReconciliationErrorCode.BINDING_MISMATCH: "Payload binding does not match.",
    VocalPayloadReconciliationErrorCode.PAYLOAD_UNAVAILABLE: "Provider payload is unavailable.",
    VocalPayloadReconciliationErrorCode.PAYLOAD_EXPIRED: "Provider payload has expired.",
    VocalPayloadReconciliationErrorCode.ACCESS_DENIED: "Provider payload access was denied.",
    VocalPayloadReconciliationErrorCode.TRANSFER_FAILED: "Provider payload transfer failed.",
    VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE: "Payload integrity verification failed.",
    VocalPayloadReconciliationErrorCode.STAGING_FAILURE: "Payload staging failed.",
    VocalPayloadReconciliationErrorCode.RIGHTS_DENIED: "Payload rights are not granted.",
    VocalPayloadReconciliationErrorCode.CLAIM_LOST: "The active payload claim is required.",
    VocalPayloadReconciliationErrorCode.CANCELLATION_REQUESTED: (
        "Payload reconciliation was cancelled."
    ),
    VocalPayloadReconciliationErrorCode.LOCATOR_CONFLICT: "Payload locator state conflicts.",
}


class VocalPayloadReconciliationError(RuntimeError):
    def __init__(self, code: VocalPayloadReconciliationErrorCode) -> None:
        super().__init__(_SAFE_MESSAGES[code])
        self.code = code


class VocalPayloadReconciliationService:
    """Provider network와 filesystem I/O를 짧은 locator transaction 밖에서 연결한다."""

    def __init__(
        self,
        acquisition: VocalPayloadAcquisitionPort,
        locators: PayloadLocatorService,
        staging_service: PayloadStagingService,
        verified_staging: VerifiedPayloadStagingPort,
        *,
        max_payload_size_bytes: int,
    ) -> None:
        if type(max_payload_size_bytes) is not int or max_payload_size_bytes <= 0:
            raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.INVALID_INPUT)
        self._acquisition = acquisition
        self._locators = locators
        self._staging_service = staging_service
        self._verified_staging = verified_staging
        self._max_payload_size_bytes = max_payload_size_bytes

    def reconcile(
        self,
        locator_id: object,
        candidate: TrustedProviderResultCandidate,
        authority_provider: Callable[[], PayloadStagingAuthority],
    ) -> PayloadLocatorRecord:
        """같은 locator를 network acquisition 또는 verified fast path로 수렴시킨다."""

        try:
            return self._reconcile(locator_id, candidate, authority_provider)
        except VocalPayloadReconciliationError:
            raise
        except VocalPayloadAcquisitionError as error:
            raise VocalPayloadReconciliationError(_map_acquisition_error(error.code)) from None
        except PayloadStagingServiceError as error:
            raise VocalPayloadReconciliationError(_map_staging_service_error(error.code)) from None
        except PayloadLocatorError as error:
            raise VocalPayloadReconciliationError(_map_locator_error(error.code)) from None
        except VerifiedPayloadStagingError as error:
            raise VocalPayloadReconciliationError(_map_verified_staging_error(error.code)) from None
        except ValidationError:
            raise VocalPayloadReconciliationError(
                VocalPayloadReconciliationErrorCode.INVALID_INPUT
            ) from None

    def _reconcile(
        self,
        locator_id: object,
        candidate: TrustedProviderResultCandidate,
        authority_provider: Callable[[], PayloadStagingAuthority],
    ) -> PayloadLocatorRecord:
        before = _require_authority(authority_provider)
        record = self._locators.get(locator_id)
        payload = _require_binding(record, candidate, before)
        if record.staging_status is PayloadLocatorStatus.VERIFIED_STAGED:
            return self._reuse_verified(locator_id, before)
        source_bound = self._locators.resolve_for_acquisition(
            locator_id,
            workspace_job_id=before.workspace_job_id,
            rights_granted=before.rights_granted,
        )

        acquired = self._acquisition.acquire_payload(
            VocalPayloadAcquisitionRequest(
                job_id=candidate.provider_job_id,
                payload=_provider_payload(payload),
                max_size_bytes=self._max_payload_size_bytes,
            )
        )

        after = _require_authority(authority_provider)
        if after.workspace_job_id != before.workspace_job_id:
            raise VocalPayloadReconciliationError(
                VocalPayloadReconciliationErrorCode.BINDING_MISMATCH
            )
        latest = self._locators.get(locator_id)
        _require_binding(latest, candidate, after)
        if latest.staging_status is PayloadLocatorStatus.VERIFIED_STAGED:
            return self._reuse_verified(locator_id, after)
        latest = self._locators.resolve_for_acquisition(
            locator_id,
            workspace_job_id=after.workspace_job_id,
            rights_granted=after.rights_granted,
        )
        if latest.lifecycle_revision != source_bound.lifecycle_revision:
            raise VocalPayloadReconciliationError(
                VocalPayloadReconciliationErrorCode.LOCATOR_CONFLICT
            )
        _require_acquired(acquired, candidate.provider_job_id, payload)
        return self._staging_service.stage(
            locator_id,
            (acquired.content,),
            authority_provider,
        )

    def _reuse_verified(
        self,
        locator_id: object,
        authority: PayloadStagingAuthority,
    ) -> PayloadLocatorRecord:
        record = self._locators.resolve_verified_staging(
            locator_id,
            workspace_job_id=authority.workspace_job_id,
            rights_granted=authority.rights_granted,
        )
        with self._verified_staging.open_verified(staged_payload_from_record(record)):
            pass
        return record


def _require_authority(
    authority_provider: Callable[[], PayloadStagingAuthority],
) -> PayloadStagingAuthority:
    try:
        authority = authority_provider()
    except VocalPayloadReconciliationError:
        raise
    except Exception:
        raise VocalPayloadReconciliationError(
            VocalPayloadReconciliationErrorCode.INVALID_INPUT
        ) from None
    if not isinstance(authority, PayloadStagingAuthority):
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.INVALID_INPUT)
    if not authority.claim_active:
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.CLAIM_LOST)
    if authority.cancellation_requested:
        raise VocalPayloadReconciliationError(
            VocalPayloadReconciliationErrorCode.CANCELLATION_REQUESTED
        )
    if not authority.rights_granted:
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.RIGHTS_DENIED)
    return authority


def _require_binding(
    record: PayloadLocatorRecord,
    candidate: TrustedProviderResultCandidate,
    authority: PayloadStagingAuthority,
) -> TrustedPayloadSourceCandidate:
    if not isinstance(candidate, TrustedProviderResultCandidate):
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.INVALID_INPUT)
    issue = record.issue
    if (
        issue.workspace_job_id != authority.workspace_job_id
        or issue.workspace_job_id != candidate.workspace_job_id
        or issue.provider_job_binding_id != candidate.provider_job_binding_id
        or candidate.provider_id != DOHAVOCAL_PROVIDER_ID
        or candidate.output_role != issue.role
        or candidate.provider_artifact_id != issue.provider_artifact_id
        or not candidate.payload_present
    ):
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.BINDING_MISMATCH)
    matches = tuple(
        payload
        for payload in candidate.payloads
        if (
            payload.provider_artifact_id == issue.provider_artifact_id
            and payload.role == issue.role
            and payload.source_kind == issue.source_kind
            and payload.source_id == issue.source_id
            and payload.checksum_algorithm == issue.expected_checksum_algorithm
            and payload.payload_checksum == issue.expected_payload_checksum
            and payload.expected_size_bytes == issue.expected_size_bytes
            and payload.expected_media_type == issue.expected_media_type
            and payload.available_until == issue.source_available_until
        )
    )
    if len(matches) != 1:
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.BINDING_MISMATCH)
    return matches[0]


def _provider_payload(payload: TrustedPayloadSourceCandidate) -> VocalProviderPayloadEntry:
    return VocalProviderPayloadEntry(
        provider_artifact_id=payload.provider_artifact_id,
        role=payload.role,
        source=VocalPayloadSource(kind="provider_subresource", source_id=payload.source_id),
        checksum_algorithm="sha256",
        payload_checksum=payload.payload_checksum,
        expected_size_bytes=payload.expected_size_bytes,
        expected_media_type=payload.expected_media_type,
        available_until=payload.available_until,
    )


def _require_acquired(
    acquired: VerifiedVocalPayload,
    provider_job_id: str,
    expected: TrustedPayloadSourceCandidate,
) -> None:
    if (
        not isinstance(acquired, VerifiedVocalPayload)
        or acquired.job_id != provider_job_id
        or acquired.provider_artifact_id != expected.provider_artifact_id
        or acquired.source_id != expected.source_id
        or acquired.checksum_algorithm != expected.checksum_algorithm
        or acquired.payload_checksum != expected.payload_checksum
        or acquired.size_bytes != expected.expected_size_bytes
        or acquired.media_type != expected.expected_media_type
        or type(acquired.content) is not bytes
        or len(acquired.content) != expected.expected_size_bytes
    ):
        raise VocalPayloadReconciliationError(VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE)


def _map_acquisition_error(
    code: VocalPayloadAcquisitionErrorCode,
) -> VocalPayloadReconciliationErrorCode:
    return {
        VocalPayloadAcquisitionErrorCode.PAYLOAD_UNAVAILABLE: (
            VocalPayloadReconciliationErrorCode.PAYLOAD_UNAVAILABLE
        ),
        VocalPayloadAcquisitionErrorCode.PAYLOAD_EXPIRED: (
            VocalPayloadReconciliationErrorCode.PAYLOAD_EXPIRED
        ),
        VocalPayloadAcquisitionErrorCode.PAYLOAD_ACCESS_DENIED: (
            VocalPayloadReconciliationErrorCode.ACCESS_DENIED
        ),
        VocalPayloadAcquisitionErrorCode.PAYLOAD_TRANSFER_FAILED: (
            VocalPayloadReconciliationErrorCode.TRANSFER_FAILED
        ),
        VocalPayloadAcquisitionErrorCode.PAYLOAD_INTEGRITY_MISMATCH: (
            VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE
        ),
        VocalPayloadAcquisitionErrorCode.RESULT_REPLAY_CONFLICT: (
            VocalPayloadReconciliationErrorCode.BINDING_MISMATCH
        ),
    }[code]


def _map_locator_error(code: PayloadLocatorErrorCode) -> VocalPayloadReconciliationErrorCode:
    if code is PayloadLocatorErrorCode.RIGHTS_REQUIRED:
        return VocalPayloadReconciliationErrorCode.RIGHTS_DENIED
    if code is PayloadLocatorErrorCode.SOURCE_EXPIRED:
        return VocalPayloadReconciliationErrorCode.PAYLOAD_EXPIRED
    return VocalPayloadReconciliationErrorCode.LOCATOR_CONFLICT


def _map_staging_service_error(
    code: PayloadStagingServiceErrorCode,
) -> VocalPayloadReconciliationErrorCode:
    return {
        PayloadStagingServiceErrorCode.CLAIM_REQUIRED: (
            VocalPayloadReconciliationErrorCode.CLAIM_LOST
        ),
        PayloadStagingServiceErrorCode.CANCELLATION_REQUESTED: (
            VocalPayloadReconciliationErrorCode.CANCELLATION_REQUESTED
        ),
        PayloadStagingServiceErrorCode.INVALID_AUTHORITY: (
            VocalPayloadReconciliationErrorCode.BINDING_MISMATCH
        ),
        PayloadStagingServiceErrorCode.ORPHAN_CLEANUP_FAILED: (
            VocalPayloadReconciliationErrorCode.STAGING_FAILURE
        ),
    }[code]


def _map_verified_staging_error(
    code: VerifiedPayloadStagingErrorCode,
) -> VocalPayloadReconciliationErrorCode:
    if code in {
        VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH,
        VerifiedPayloadStagingErrorCode.MEDIA_MISMATCH,
        VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED,
    }:
        return VocalPayloadReconciliationErrorCode.INTEGRITY_FAILURE
    return VocalPayloadReconciliationErrorCode.STAGING_FAILURE
