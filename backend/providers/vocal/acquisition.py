"""Read-only, transient DohaVocal payload acquisition boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Protocol

from .contracts import VocalProviderPayloadEntry


class VocalPayloadAcquisitionErrorCode(StrEnum):
    PAYLOAD_UNAVAILABLE = "payload_unavailable"
    PAYLOAD_EXPIRED = "payload_expired"
    PAYLOAD_ACCESS_DENIED = "payload_access_denied"
    PAYLOAD_TRANSFER_FAILED = "payload_transfer_failed"
    PAYLOAD_INTEGRITY_MISMATCH = "payload_integrity_mismatch"
    RESULT_REPLAY_CONFLICT = "result_replay_conflict"


class VocalPayloadAcquisitionError(RuntimeError):
    def __init__(self, code: VocalPayloadAcquisitionErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class VocalPayloadAcquisitionRequest:
    job_id: str
    payload: VocalProviderPayloadEntry
    max_size_bytes: int

    def __post_init__(self) -> None:
        if self.max_size_bytes <= 0:
            raise ValueError("max_size_bytes must be positive")
        if self.payload.expected_size_bytes > self.max_size_bytes:
            raise VocalPayloadAcquisitionError(
                VocalPayloadAcquisitionErrorCode.PAYLOAD_INTEGRITY_MISMATCH
            )
        expires_at = self.payload.available_until
        if expires_at is not None and expires_at <= datetime.now(UTC):
            raise VocalPayloadAcquisitionError(
                VocalPayloadAcquisitionErrorCode.PAYLOAD_EXPIRED
            )


@dataclass(frozen=True, slots=True)
class VerifiedVocalPayload:
    job_id: str
    provider_artifact_id: str
    source_id: str
    media_type: str
    size_bytes: int
    checksum_algorithm: str
    payload_checksum: str
    content: bytes


class VocalPayloadAcquisitionPort(Protocol):
    """Returns verified bounded bytes; it never returns URLs or raw responses."""

    def acquire_payload(
        self, request: VocalPayloadAcquisitionRequest
    ) -> VerifiedVocalPayload: ...
