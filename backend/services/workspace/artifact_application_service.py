"""Owner·retention·무결성 Gate를 소유하는 Artifact Application Service."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import BinaryIO
from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.workspace import Artifact
from backend.repositories.workspace import ArtifactStorageRepository, AssetRepository
from backend.storage.artifact_integrity import calculate_artifact_integrity
from backend.storage.artifact_resolver import (
    ArtifactStorageError,
    ArtifactStorageResolver,
    ArtifactStorageRoots,
)

RETENTION_STATUSES = frozenset(
    {"active", "quarantined", "expired", "pending_delete", "deleted"}
)


class ArtifactAccessErrorCode(StrEnum):
    NOT_FOUND = "ARTIFACT_NOT_FOUND"
    CONTENT_UNAVAILABLE = "ARTIFACT_CONTENT_UNAVAILABLE"
    QUARANTINED = "ARTIFACT_QUARANTINED"
    GONE = "ARTIFACT_GONE"
    INTEGRITY_ERROR = "ARTIFACT_INTEGRITY_ERROR"


_SAFE_MESSAGES = {
    ArtifactAccessErrorCode.NOT_FOUND: "Artifact was not found.",
    ArtifactAccessErrorCode.CONTENT_UNAVAILABLE: "Artifact content is unavailable.",
    ArtifactAccessErrorCode.QUARANTINED: "Artifact is quarantined.",
    ArtifactAccessErrorCode.GONE: "Artifact is no longer available.",
    ArtifactAccessErrorCode.INTEGRITY_ERROR: "Artifact integrity verification failed.",
}


class ArtifactAccessError(RuntimeError):
    def __init__(self, code: ArtifactAccessErrorCode) -> None:
        super().__init__(_SAFE_MESSAGES[code])
        self.code = code


@dataclass(frozen=True, slots=True)
class ArtifactMetadata:
    artifact_id: UUID
    asset_version_id: UUID
    artifact_kind: str
    media_type: str
    size_bytes: int
    checksum_algorithm: str
    artifact_checksum: str
    producer_type: str
    producer_id: str | None
    run_id: str | None
    retention_status: str


@dataclass(frozen=True, slots=True)
class ArtifactContentHandle:
    """공개 Path 없이 검증 완료된 content 전달에 필요한 내부 값."""

    artifact_id: UUID
    asset_version_id: UUID
    artifact_kind: str
    media_type: str
    size_bytes: int
    checksum_algorithm: str
    artifact_checksum: str


class ArtifactApplicationService:
    """공개 Router 아래에서 Owner·retention·content integrity를 조정한다."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        artifact_roots: ArtifactStorageRoots,
    ) -> None:
        self._session_factory = session_factory
        self._artifact_roots = artifact_roots

    def get_artifact_for_owner(
        self,
        artifact_id: UUID,
        *,
        effective_owner_id: UUID,
    ) -> ArtifactMetadata:
        _validate_identifiers(artifact_id, effective_owner_id)
        with self._session_factory() as session:
            artifact = _owned_artifact(
                session,
                artifact_id=artifact_id,
                effective_owner_id=effective_owner_id,
            )
            _validate_retention_status(artifact.retention_status)
            return _to_metadata(artifact)

    @contextmanager
    def open_content_for_owner(
        self,
        artifact_id: UUID,
        *,
        effective_owner_id: UUID,
    ) -> Iterator[tuple[ArtifactContentHandle, BinaryIO]]:
        """Owner·retention·full SHA-256 검증 후 같은 descriptor를 반환한다."""

        _validate_identifiers(artifact_id, effective_owner_id)
        with self._session_factory() as session:
            artifact = _owned_artifact(
                session,
                artifact_id=artifact_id,
                effective_owner_id=effective_owner_id,
            )
            _require_content_retention(artifact.retention_status)
            if artifact.checksum_algorithm != "sha256":
                raise ArtifactAccessError(ArtifactAccessErrorCode.INTEGRITY_ERROR)
            resolver = ArtifactStorageResolver(
                ArtifactStorageRepository(session), self._artifact_roots
            )
            try:
                with resolver.open_payload(artifact_id) as (resolved, stream):
                    if resolved.size_bytes != artifact.size_bytes:
                        raise ArtifactAccessError(
                            ArtifactAccessErrorCode.INTEGRITY_ERROR
                        )
                    integrity = calculate_artifact_integrity(stream)
                    if (
                        integrity.size_bytes != artifact.size_bytes
                        or integrity.checksum != artifact.artifact_checksum
                    ):
                        raise ArtifactAccessError(
                            ArtifactAccessErrorCode.INTEGRITY_ERROR
                        )
                    stream.seek(0)
                    yield _to_content_handle(artifact), stream
            except ArtifactAccessError:
                raise
            except (ArtifactStorageError, OSError):
                raise ArtifactAccessError(
                    ArtifactAccessErrorCode.CONTENT_UNAVAILABLE
                ) from None


def _owned_artifact(
    session: Session,
    *,
    artifact_id: UUID,
    effective_owner_id: UUID,
) -> Artifact:
    artifact = AssetRepository(session).get_artifact_for_owner(
        artifact_id, effective_owner_id
    )
    if artifact is None:
        raise ArtifactAccessError(ArtifactAccessErrorCode.NOT_FOUND)
    return artifact


def _validate_identifiers(artifact_id: UUID, effective_owner_id: UUID) -> None:
    if type(artifact_id) is not UUID or type(effective_owner_id) is not UUID:
        raise ArtifactAccessError(ArtifactAccessErrorCode.NOT_FOUND)


def _validate_retention_status(retention_status: str) -> None:
    if retention_status not in RETENTION_STATUSES:
        raise ArtifactAccessError(ArtifactAccessErrorCode.CONTENT_UNAVAILABLE)


def _require_content_retention(retention_status: str) -> None:
    _validate_retention_status(retention_status)
    if retention_status == "active":
        return
    if retention_status == "quarantined":
        raise ArtifactAccessError(ArtifactAccessErrorCode.QUARANTINED)
    raise ArtifactAccessError(ArtifactAccessErrorCode.GONE)


def _to_metadata(artifact: Artifact) -> ArtifactMetadata:
    return ArtifactMetadata(
        artifact_id=artifact.artifact_id,
        asset_version_id=artifact.asset_version_id,
        artifact_kind=artifact.artifact_kind,
        media_type=artifact.media_type,
        size_bytes=artifact.size_bytes,
        checksum_algorithm=artifact.checksum_algorithm,
        artifact_checksum=artifact.artifact_checksum,
        producer_type=artifact.producer_type,
        producer_id=artifact.producer_id,
        run_id=artifact.run_id,
        retention_status=artifact.retention_status,
    )


def _to_content_handle(artifact: Artifact) -> ArtifactContentHandle:
    return ArtifactContentHandle(
        artifact_id=artifact.artifact_id,
        asset_version_id=artifact.asset_version_id,
        artifact_kind=artifact.artifact_kind,
        media_type=artifact.media_type,
        size_bytes=artifact.size_bytes,
        checksum_algorithm=artifact.checksum_algorithm,
        artifact_checksum=artifact.artifact_checksum,
    )
