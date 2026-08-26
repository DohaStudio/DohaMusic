"""Durable PayloadLocator domain values and fail-closed validation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import PurePosixPath
from uuid import UUID

PAYLOAD_LOCATOR_PREFIX = "payloadref:v1:"
PAYLOAD_LOCATOR_PATTERN = re.compile(r"payloadref:v1:([0-9a-f]{32})")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
OPAQUE_ID_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?")
SAFE_BACKEND_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9_-]*[a-z0-9])?")
URI_SCHEME_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
SENSITIVE_PATTERN = re.compile(
    r"(?:authorization|bearer|api[_-]?key|credential|cookie|password|secret|token)",
    re.IGNORECASE,
)

PAYLOAD_ROLES = frozenset(
    {
        "generated_vocal_candidate",
        "converted_vocal_candidate",
        "corrected_vocal_candidate",
        "vocal_analysis_result",
    }
)
EXPECTED_MEDIA_TYPES = frozenset({"audio/wav", "audio/flac", "application/json"})


class PayloadLocatorStatus(StrEnum):
    SOURCE_BOUND = "source_bound"
    VERIFIED_STAGED = "verified_staged"
    INGESTED = "ingested"
    CLEANUP_PENDING = "cleanup_pending"
    CLEANED = "cleaned"


class PayloadLocatorRevocationReason(StrEnum):
    WORKSPACE_CANCELLED = "workspace_cancelled"
    WORKSPACE_DELETED = "workspace_deleted"
    RIGHTS_REVOKED = "rights_revoked"
    SOURCE_INVALIDATED = "source_invalidated"
    INTEGRITY_FAILURE = "integrity_failure"
    SECURITY_INCIDENT = "security_incident"


class PayloadLocatorErrorCode(StrEnum):
    INVALID_ISSUE = "INVALID_PAYLOAD_LOCATOR_ISSUE"
    MALFORMED_LOCATOR_ID = "MALFORMED_PAYLOAD_LOCATOR_ID"
    RESULT_REPLAY_CONFLICT = "RESULT_REPLAY_CONFLICT"
    LOCATOR_ID_COLLISION = "PAYLOAD_LOCATOR_ID_COLLISION"
    NOT_FOUND = "PAYLOAD_LOCATOR_NOT_FOUND"
    WORKSPACE_BINDING_MISMATCH = "PAYLOAD_LOCATOR_WORKSPACE_BINDING_MISMATCH"
    REVISION_CONFLICT = "PAYLOAD_LOCATOR_REVISION_CONFLICT"
    ILLEGAL_TRANSITION = "PAYLOAD_LOCATOR_ILLEGAL_TRANSITION"
    REVOKED = "PAYLOAD_LOCATOR_REVOKED"
    SOURCE_EXPIRED = "PAYLOAD_LOCATOR_SOURCE_EXPIRED"
    LOCATOR_EXPIRED = "PAYLOAD_LOCATOR_POLICY_EXPIRED"
    RIGHTS_REQUIRED = "PAYLOAD_LOCATOR_RIGHTS_REQUIRED"
    INVALID_STAGING_KEY = "INVALID_PAYLOAD_LOCATOR_STAGING_KEY"
    INTEGRITY_MISMATCH = "PAYLOAD_LOCATOR_INTEGRITY_MISMATCH"


class PayloadLocatorError(RuntimeError):
    """Stable internal failure that never exposes stored source details."""

    def __init__(self, code: PayloadLocatorErrorCode) -> None:
        super().__init__(code.value)
        self.code = code


@dataclass(frozen=True, slots=True)
class PayloadLocatorIssue:
    workspace_job_id: UUID
    provider_job_binding_id: UUID
    payload_ordinal: int
    provider_artifact_id: str
    role: str
    source_kind: str
    source_id: str
    artifact_kind: str
    expected_checksum_algorithm: str
    expected_payload_checksum: str
    expected_size_bytes: int
    expected_media_type: str
    source_available_until: datetime | None = None
    locator_expires_at: datetime | None = None

    def __post_init__(self) -> None:
        valid = (
            isinstance(self.workspace_job_id, UUID)
            and isinstance(self.provider_job_binding_id, UUID)
            and type(self.payload_ordinal) is int
            and self.payload_ordinal >= 0
            and _safe_opaque(self.provider_artifact_id, 200)
            and self.role in PAYLOAD_ROLES
            and self.source_kind == "provider_subresource"
            and _safe_opaque(self.source_id, 200)
            and self.artifact_kind in {"audio", "analysis"}
            and self.expected_checksum_algorithm == "sha256"
            and SHA256_PATTERN.fullmatch(self.expected_payload_checksum) is not None
            and type(self.expected_size_bytes) is int
            and self.expected_size_bytes > 0
            and self.expected_media_type in EXPECTED_MEDIA_TYPES
            and _valid_role_media_kind(self.role, self.artifact_kind, self.expected_media_type)
            and _is_utc_or_none(self.source_available_until)
            and _is_utc_or_none(self.locator_expires_at)
        )
        if not valid:
            raise PayloadLocatorError(PayloadLocatorErrorCode.INVALID_ISSUE)

    @property
    def immutable_facts(self) -> tuple[object, ...]:
        return (
            self.workspace_job_id,
            self.provider_job_binding_id,
            self.payload_ordinal,
            self.provider_artifact_id,
            self.role,
            self.source_kind,
            self.source_id,
            self.artifact_kind,
            self.expected_checksum_algorithm,
            self.expected_payload_checksum,
            self.expected_size_bytes,
            self.expected_media_type,
            self.source_available_until,
            self.locator_expires_at,
        )


@dataclass(frozen=True, slots=True)
class VerifiedStagingFacts:
    staging_backend: str
    staging_key: str
    actual_checksum_algorithm: str
    actual_payload_checksum: str
    actual_size_bytes: int
    actual_media_type: str
    verified_at: datetime

    def __post_init__(self) -> None:
        if (
            not isinstance(self.staging_backend, str)
            or len(self.staging_backend) > 32
            or SAFE_BACKEND_PATTERN.fullmatch(self.staging_backend) is None
            or not is_safe_staging_key(self.staging_key)
            or self.actual_checksum_algorithm != "sha256"
            or SHA256_PATTERN.fullmatch(self.actual_payload_checksum) is None
            or type(self.actual_size_bytes) is not int
            or self.actual_size_bytes <= 0
            or self.actual_media_type not in EXPECTED_MEDIA_TYPES
            or not _is_utc(self.verified_at)
        ):
            raise PayloadLocatorError(PayloadLocatorErrorCode.INVALID_STAGING_KEY)


@dataclass(frozen=True, slots=True)
class PayloadLocatorRecord:
    locator_uuid: UUID
    issue: PayloadLocatorIssue
    staging_status: PayloadLocatorStatus
    staging_backend: str | None
    staging_key: str | None
    actual_checksum_algorithm: str | None
    actual_payload_checksum: str | None
    actual_size_bytes: int | None
    actual_media_type: str | None
    verified_at: datetime | None
    ingested_artifact_id: UUID | None
    ingested_at: datetime | None
    revoked_at: datetime | None
    revocation_reason: PayloadLocatorRevocationReason | None
    cleanup_requested_at: datetime | None
    cleanup_completed_at: datetime | None
    lifecycle_revision: int
    created_at: datetime
    updated_at: datetime

    @property
    def locator_id(self) -> str:
        return format_locator_id(self.locator_uuid)

    @property
    def immutable_facts(self) -> tuple[object, ...]:
        return self.issue.immutable_facts

    @property
    def revoked(self) -> bool:
        return self.revoked_at is not None


def format_locator_id(locator_uuid: UUID) -> str:
    if not isinstance(locator_uuid, UUID):
        raise PayloadLocatorError(PayloadLocatorErrorCode.MALFORMED_LOCATOR_ID)
    return f"{PAYLOAD_LOCATOR_PREFIX}{locator_uuid.hex}"


def parse_locator_id(locator_id: object) -> UUID:
    if not isinstance(locator_id, str):
        raise PayloadLocatorError(PayloadLocatorErrorCode.MALFORMED_LOCATOR_ID)
    matched = PAYLOAD_LOCATOR_PATTERN.fullmatch(locator_id)
    if matched is None:
        raise PayloadLocatorError(PayloadLocatorErrorCode.MALFORMED_LOCATOR_ID)
    return UUID(hex=matched.group(1))


def is_safe_staging_key(value: object) -> bool:
    if not isinstance(value, str) or not value or len(value) > 512:
        return False
    if not value.isascii() or "\\" in value or value.startswith("/"):
        return False
    if URI_SCHEME_PATTERN.match(value) or SENSITIVE_PATTERN.search(value):
        return False
    path = PurePosixPath(value)
    return (
        str(path) == value
        and not path.is_absolute()
        and all(part not in {"", ".", ".."} for part in path.parts)
    )


def _safe_opaque(value: object, maximum: int) -> bool:
    return (
        isinstance(value, str)
        and value.isascii()
        and 0 < len(value) <= maximum
        and OPAQUE_ID_PATTERN.fullmatch(value) is not None
        and ".." not in value
        and URI_SCHEME_PATTERN.match(value) is None
        and SENSITIVE_PATTERN.search(value) is None
    )


def _valid_role_media_kind(role: str, artifact_kind: str, media_type: str) -> bool:
    if role == "vocal_analysis_result":
        return artifact_kind == "analysis" and media_type == "application/json"
    return artifact_kind == "audio" and media_type in {"audio/wav", "audio/flac"}


def _is_utc(value: object) -> bool:
    return (
        isinstance(value, datetime)
        and value.tzinfo is not None
        and value.utcoffset() is not None
        and value.astimezone(UTC).utcoffset() == value.utcoffset()
        and value.utcoffset().total_seconds() == 0
    )


def _is_utc_or_none(value: object) -> bool:
    return value is None or _is_utc(value)
