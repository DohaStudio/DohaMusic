"""DohaMusic-owned trusted staging payload locator and resolver contract."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID, uuid4

from backend.storage.artifact_media import (
    SUPPORTED_ARTIFACT_KINDS,
    ArtifactMediaValidationError,
    validate_artifact_media,
)
from backend.storage.artifact_resolver import (
    ArtifactStorageError,
    assert_safe_local_path,
    open_regular_local_file,
    validate_local_root,
)

TRUSTED_PAYLOAD_LOCATOR_NAMESPACE = "payloadref"
TRUSTED_PAYLOAD_LOCATOR_VERSION = 1

_LOCATOR_PATTERN = re.compile(r"payloadref:v1:([0-9a-f]{32})")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
_CREDENTIAL_LIKE = re.compile(
    r"(?:user:[^/\\]*@|"
    r"(?:authorization|bearer|api[_-]?key|credential|password|secret|token)\s*[:=])",
    re.IGNORECASE,
)


class TrustedPayloadErrorCode(StrEnum):
    CONFIGURATION_ERROR = "TRUSTED_PAYLOAD_CONFIGURATION_ERROR"
    MALFORMED_REFERENCE = "TRUSTED_PAYLOAD_MALFORMED_REFERENCE"
    UNKNOWN_REFERENCE = "TRUSTED_PAYLOAD_UNKNOWN_REFERENCE"
    EXPIRED_REFERENCE = "TRUSTED_PAYLOAD_EXPIRED_REFERENCE"
    PAYLOAD_MISSING = "TRUSTED_PAYLOAD_MISSING"
    PAYLOAD_OUTSIDE_TRUSTED_ROOT = "TRUSTED_PAYLOAD_OUTSIDE_TRUSTED_ROOT"
    PAYLOAD_NOT_REGULAR_FILE = "TRUSTED_PAYLOAD_NOT_REGULAR_FILE"
    PAYLOAD_METADATA_MISMATCH = "TRUSTED_PAYLOAD_METADATA_MISMATCH"
    DUPLICATE_REFERENCE = "TRUSTED_PAYLOAD_DUPLICATE_REFERENCE"
    INVALID_EXPIRY = "TRUSTED_PAYLOAD_INVALID_EXPIRY"
    INVALID_ARTIFACT_KIND = "TRUSTED_PAYLOAD_INVALID_ARTIFACT_KIND"


_SAFE_ERROR_MESSAGES = {
    TrustedPayloadErrorCode.CONFIGURATION_ERROR: (
        "Trusted payload configuration is invalid."
    ),
    TrustedPayloadErrorCode.MALFORMED_REFERENCE: (
        "Trusted payload reference is malformed."
    ),
    TrustedPayloadErrorCode.UNKNOWN_REFERENCE: "Trusted payload reference is unknown.",
    TrustedPayloadErrorCode.EXPIRED_REFERENCE: "Trusted payload reference has expired.",
    TrustedPayloadErrorCode.PAYLOAD_MISSING: "Trusted payload is unavailable.",
    TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT: (
        "Trusted payload boundary was rejected."
    ),
    TrustedPayloadErrorCode.PAYLOAD_NOT_REGULAR_FILE: (
        "Trusted payload is not a regular file."
    ),
    TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH: (
        "Trusted payload integrity verification failed."
    ),
    TrustedPayloadErrorCode.DUPLICATE_REFERENCE: (
        "Trusted payload reference already exists."
    ),
    TrustedPayloadErrorCode.INVALID_EXPIRY: "Trusted payload expiry is invalid.",
    TrustedPayloadErrorCode.INVALID_ARTIFACT_KIND: (
        "Trusted payload artifact kind is invalid."
    ),
}


class TrustedPayloadError(RuntimeError):
    """Path- and credential-free trusted payload contract error."""

    def __init__(self, code: TrustedPayloadErrorCode) -> None:
        super().__init__(_SAFE_ERROR_MESSAGES[code])
        self.code = code


@dataclass(frozen=True, slots=True)
class TrustedPayloadReference:
    """Opaque, versioned capability identifier plus byte-derived integrity metadata."""

    locator_id: str
    checksum_algorithm: Literal["sha256"]
    payload_checksum: str

    def __post_init__(self) -> None:
        if (
            not isinstance(self.locator_id, str)
            or _LOCATOR_PATTERN.fullmatch(self.locator_id) is None
        ):
            raise TrustedPayloadError(TrustedPayloadErrorCode.MALFORMED_REFERENCE)
        if (
            self.checksum_algorithm != "sha256"
            or not isinstance(self.payload_checksum, str)
            or _SHA256_PATTERN.fullmatch(self.payload_checksum) is None
        ):
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)

    @property
    def namespace(self) -> str:
        return TRUSTED_PAYLOAD_LOCATOR_NAMESPACE

    @property
    def version(self) -> int:
        return TRUSTED_PAYLOAD_LOCATOR_VERSION

    @property
    def opaque_id(self) -> str:
        return self.locator_id.rsplit(":", 1)[1]


@dataclass(frozen=True, slots=True)
class ResolvedTrustedPayload:
    """Resolver output safe for a future internal Completion adapter."""

    reference: TrustedPayloadReference
    temporary_path: Path
    artifact_kind: str
    media_type: str
    size_bytes: int
    checksum_algorithm: Literal["sha256"]
    payload_checksum: str
    created_at: datetime
    expires_at: datetime | None


class TrustedPayloadIssuer(Protocol):
    def register_trusted_payload(
        self,
        trusted_runtime_path: Path,
        *,
        artifact_kind: str,
        expires_at: datetime | None = None,
    ) -> TrustedPayloadReference: ...


class TrustedPayloadResolver(Protocol):
    def resolve(self, reference: TrustedPayloadReference) -> ResolvedTrustedPayload: ...


@dataclass(frozen=True, slots=True)
class _PayloadBinding:
    descriptor: ResolvedTrustedPayload
    file_identity: tuple[int, int, int, int]


@dataclass(frozen=True, slots=True)
class _InspectedPayload:
    path: Path
    file_identity: tuple[int, int, int, int]
    size_bytes: int
    payload_checksum: str


class InMemoryTrustedPayloadRegistry:
    """Deterministic process-local issuer/resolver fake for the Foundation boundary.

    The binding registry is deliberately not durable and is not a production
    cross-process handoff. Cleanup remains owned by Completion/artifact ingestion.
    """

    def __init__(
        self,
        staging_root: Path | None,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], UUID] | None = None,
    ) -> None:
        if staging_root is None:
            raise TrustedPayloadError(TrustedPayloadErrorCode.CONFIGURATION_ERROR)
        try:
            self._staging_root = validate_local_root(staging_root)
        except ArtifactStorageError:
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.CONFIGURATION_ERROR
            ) from None
        self._clock = clock or _utc_now
        self._id_factory = id_factory or uuid4
        self._bindings: dict[str, _PayloadBinding] = {}

    def register_trusted_payload(
        self,
        trusted_runtime_path: Path,
        *,
        artifact_kind: str,
        expires_at: datetime | None = None,
    ) -> TrustedPayloadReference:
        if artifact_kind not in SUPPORTED_ARTIFACT_KINDS:
            raise TrustedPayloadError(TrustedPayloadErrorCode.INVALID_ARTIFACT_KIND)
        now = self._now()
        normalized_expiry = _normalize_expiry(expires_at)
        if normalized_expiry is not None and normalized_expiry <= now:
            raise TrustedPayloadError(TrustedPayloadErrorCode.INVALID_EXPIRY)

        inspected = self._inspect(trusted_runtime_path)
        try:
            media = validate_artifact_media(
                inspected.path,
                artifact_kind=artifact_kind,
                size_bytes=inspected.size_bytes,
            )
        except (ArtifactMediaValidationError, OSError):
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH
            ) from None
        verified = self._inspect(inspected.path)
        if verified != inspected:
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)

        try:
            opaque_id = self._id_factory()
            if not isinstance(opaque_id, UUID):
                raise TypeError
        except Exception:
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.CONFIGURATION_ERROR
            ) from None
        locator_id = (
            f"{TRUSTED_PAYLOAD_LOCATOR_NAMESPACE}:"
            f"v{TRUSTED_PAYLOAD_LOCATOR_VERSION}:{opaque_id.hex}"
        )
        if locator_id in self._bindings:
            raise TrustedPayloadError(TrustedPayloadErrorCode.DUPLICATE_REFERENCE)
        reference = TrustedPayloadReference(
            locator_id=locator_id,
            checksum_algorithm="sha256",
            payload_checksum=inspected.payload_checksum,
        )
        descriptor = ResolvedTrustedPayload(
            reference=reference,
            temporary_path=inspected.path,
            artifact_kind=artifact_kind,
            media_type=media.media_type,
            size_bytes=inspected.size_bytes,
            checksum_algorithm="sha256",
            payload_checksum=inspected.payload_checksum,
            created_at=now,
            expires_at=normalized_expiry,
        )
        self._bindings[locator_id] = _PayloadBinding(
            descriptor=descriptor,
            file_identity=inspected.file_identity,
        )
        return reference

    def resolve(self, reference: TrustedPayloadReference) -> ResolvedTrustedPayload:
        if not isinstance(reference, TrustedPayloadReference):
            raise TrustedPayloadError(TrustedPayloadErrorCode.MALFORMED_REFERENCE)
        binding = self._bindings.get(reference.locator_id)
        if binding is None:
            raise TrustedPayloadError(TrustedPayloadErrorCode.UNKNOWN_REFERENCE)
        if reference != binding.descriptor.reference:
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)
        if (
            binding.descriptor.expires_at is not None
            and self._now() >= binding.descriptor.expires_at
        ):
            raise TrustedPayloadError(TrustedPayloadErrorCode.EXPIRED_REFERENCE)

        inspected = self._inspect(binding.descriptor.temporary_path)
        if (
            inspected.file_identity != binding.file_identity
            or inspected.size_bytes != binding.descriptor.size_bytes
            or inspected.payload_checksum != binding.descriptor.payload_checksum
        ):
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)
        try:
            media = validate_artifact_media(
                inspected.path,
                artifact_kind=binding.descriptor.artifact_kind,
                size_bytes=inspected.size_bytes,
            )
        except (ArtifactMediaValidationError, OSError):
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH
            ) from None
        verified = self._inspect(inspected.path)
        if verified != inspected or media.media_type != binding.descriptor.media_type:
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_METADATA_MISMATCH)
        return binding.descriptor

    def _now(self) -> datetime:
        try:
            value = _normalize_expiry(self._clock())
        except TrustedPayloadError:
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.CONFIGURATION_ERROR
            ) from None
        if value is None:
            raise TrustedPayloadError(TrustedPayloadErrorCode.CONFIGURATION_ERROR)
        return value

    def _inspect(self, requested_path: Path) -> _InspectedPayload:
        if not isinstance(requested_path, Path) or not requested_path.is_absolute():
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT
            )
        if any(
            part in {".", ".."} for part in requested_path.parts
        ) or _CREDENTIAL_LIKE.search(str(requested_path)):
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT
            )
        try:
            requested_path.relative_to(self._staging_root)
            assert_safe_local_path(self._staging_root, requested_path)
            resolved = requested_path.resolve(strict=True)
            resolved.relative_to(self._staging_root)
            assert_safe_local_path(self._staging_root, resolved)
        except FileNotFoundError:
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_MISSING) from None
        except (ArtifactStorageError, OSError, RuntimeError, ValueError):
            raise TrustedPayloadError(
                TrustedPayloadErrorCode.PAYLOAD_OUTSIDE_TRUSTED_ROOT
            ) from None
        try:
            if not stat.S_ISREG(resolved.stat(follow_symlinks=False).st_mode):
                raise TrustedPayloadError(
                    TrustedPayloadErrorCode.PAYLOAD_NOT_REGULAR_FILE
                )
        except TrustedPayloadError:
            raise
        except OSError:
            raise TrustedPayloadError(TrustedPayloadErrorCode.PAYLOAD_MISSING) from None
        try:
            descriptor, descriptor_stat = open_regular_local_file(
                self._staging_root, resolved
            )
        except ArtifactStorageError:
            if not resolved.exists():
                code = TrustedPayloadErrorCode.PAYLOAD_MISSING
            else:
                code = TrustedPayloadErrorCode.PAYLOAD_NOT_REGULAR_FILE
            raise TrustedPayloadError(code) from None

        digest = hashlib.sha256()
        size_bytes = 0
        with os.fdopen(descriptor, "rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
                size_bytes += len(chunk)
        return _InspectedPayload(
            path=resolved,
            file_identity=(
                descriptor_stat.st_dev,
                descriptor_stat.st_ino,
                descriptor_stat.st_ctime_ns,
                descriptor_stat.st_mtime_ns,
            ),
            size_bytes=size_bytes,
            payload_checksum=digest.hexdigest(),
        )


def _normalize_expiry(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise TrustedPayloadError(TrustedPayloadErrorCode.INVALID_EXPIRY)
    return value.astimezone(UTC)


def _utc_now() -> datetime:
    return datetime.now(UTC)
