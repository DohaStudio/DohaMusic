"""검증된 임시 Payload를 불변 Artifact로 등록하는 내부 Application Service."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from backend.models.workspace import Artifact, ArtifactStorageLocation
from backend.models.workspace.identifiers import generate_uuid
from backend.repositories.workspace import ArtifactStorageRepository, AssetRepository
from backend.storage.artifact_media import SUPPORTED_ARTIFACT_KINDS
from backend.storage.artifact_publisher import (
    ArtifactPublishError,
    ArtifactPublishErrorCode,
    LocalArtifactPublisher,
    PublishedLocalPayload,
)
from backend.storage.artifact_resolver import (
    APPROVED_STORAGE_DOMAINS,
    SUPPORTED_LOCATOR_VERSION,
    SUPPORTED_STORAGE_BACKEND,
    ArtifactStorageError,
    ArtifactStorageResolver,
    ArtifactStorageRoots,
)

logger = logging.getLogger(__name__)

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
APPROVED_PRODUCER_TYPES = frozenset({"user", "provider", "workspace", "import"})
DOMAIN_ARTIFACT_KINDS = {
    "lm": frozenset({"lyrics_text", "manifest", "evaluation"}),
    "audio": frozenset({"audio", "stem", "manifest", "evaluation"}),
    "vocal": frozenset({"audio", "stem", "manifest", "evaluation"}),
    "music": frozenset(
        {"lyrics_text", "audio", "stem", "manifest", "evaluation", "snapshot"}
    ),
}


class ArtifactIngestionErrorCode(StrEnum):
    CONFIGURATION_ERROR = "ARTIFACT_INGESTION_CONFIGURATION_ERROR"
    INVALID_REQUEST = "INVALID_ARTIFACT_INGESTION_REQUEST"
    VERSION_NOT_FOUND = "ASSET_VERSION_NOT_FOUND"
    INVALID_KIND = "INVALID_ARTIFACT_KIND"
    INVALID_DOMAIN = "INVALID_STORAGE_DOMAIN"
    INVALID_PRODUCER = "INVALID_ARTIFACT_PRODUCER"
    INVALID_STAGING_PAYLOAD = "INVALID_STAGING_PAYLOAD"
    MEDIA_VALIDATION_FAILED = "ARTIFACT_MEDIA_VALIDATION_FAILED"
    CHECKSUM_MISMATCH = "ARTIFACT_CHECKSUM_MISMATCH"
    MEDIA_TYPE_MISMATCH = "ARTIFACT_MEDIA_TYPE_MISMATCH"
    PUBLISH_COLLISION = "ARTIFACT_PUBLISH_COLLISION"
    PUBLISH_FAILED = "ARTIFACT_PUBLISH_FAILED"
    REGISTRATION_FAILED = "ARTIFACT_REGISTRATION_FAILED"
    VERIFICATION_FAILED = "ARTIFACT_POST_PUBLISH_VERIFICATION_FAILED"


_SAFE_MESSAGES = {
    ArtifactIngestionErrorCode.CONFIGURATION_ERROR: (
        "Artifact ingestion configuration is invalid."
    ),
    ArtifactIngestionErrorCode.INVALID_REQUEST: "Artifact ingestion request is invalid.",
    ArtifactIngestionErrorCode.VERSION_NOT_FOUND: "AssetVersion was not found.",
    ArtifactIngestionErrorCode.INVALID_KIND: "Artifact kind is not allowed.",
    ArtifactIngestionErrorCode.INVALID_DOMAIN: "Artifact storage domain is invalid.",
    ArtifactIngestionErrorCode.INVALID_PRODUCER: "Artifact producer is invalid.",
    ArtifactIngestionErrorCode.INVALID_STAGING_PAYLOAD: (
        "Artifact staging payload is invalid."
    ),
    ArtifactIngestionErrorCode.MEDIA_VALIDATION_FAILED: (
        "Artifact media validation failed."
    ),
    ArtifactIngestionErrorCode.CHECKSUM_MISMATCH: (
        "Artifact checksum hint does not match the payload."
    ),
    ArtifactIngestionErrorCode.MEDIA_TYPE_MISMATCH: (
        "Artifact media type hint does not match the payload."
    ),
    ArtifactIngestionErrorCode.PUBLISH_COLLISION: (
        "Artifact immutable target already exists."
    ),
    ArtifactIngestionErrorCode.PUBLISH_FAILED: "Artifact publish failed.",
    ArtifactIngestionErrorCode.REGISTRATION_FAILED: (
        "Artifact metadata registration failed."
    ),
    ArtifactIngestionErrorCode.VERIFICATION_FAILED: (
        "Published Artifact verification failed."
    ),
}

_PUBLISH_ERROR_MAP = {
    ArtifactPublishErrorCode.CONFIGURATION_ERROR: (
        ArtifactIngestionErrorCode.CONFIGURATION_ERROR
    ),
    ArtifactPublishErrorCode.INVALID_STAGING_PAYLOAD: (
        ArtifactIngestionErrorCode.INVALID_STAGING_PAYLOAD
    ),
    ArtifactPublishErrorCode.MEDIA_VALIDATION_FAILED: (
        ArtifactIngestionErrorCode.MEDIA_VALIDATION_FAILED
    ),
    ArtifactPublishErrorCode.CHECKSUM_MISMATCH: (
        ArtifactIngestionErrorCode.CHECKSUM_MISMATCH
    ),
    ArtifactPublishErrorCode.MEDIA_TYPE_MISMATCH: (
        ArtifactIngestionErrorCode.MEDIA_TYPE_MISMATCH
    ),
    ArtifactPublishErrorCode.PUBLISH_COLLISION: (
        ArtifactIngestionErrorCode.PUBLISH_COLLISION
    ),
    ArtifactPublishErrorCode.PUBLISH_FAILED: (
        ArtifactIngestionErrorCode.PUBLISH_FAILED
    ),
    ArtifactPublishErrorCode.VERIFICATION_FAILED: (
        ArtifactIngestionErrorCode.VERIFICATION_FAILED
    ),
}


@dataclass(frozen=True, slots=True)
class ArtifactIngestionRequest:
    """공개 API가 아닌 trusted internal handoff 계약."""

    asset_version_id: UUID
    artifact_kind: str
    producer_type: str
    storage_domain: str
    temporary_path: Path
    producer_id: str | None = None
    run_id: str | None = None
    expected_media_type: str | None = None
    expected_sha256: str | None = None
    original_filename: str | None = None


@dataclass(frozen=True, slots=True)
class OrphanCandidate:
    """절대 경로를 포함하지 않는 reconciliation 입력."""

    artifact_id: UUID
    storage_domain: str
    storage_key: str | None
    category: str
    reason_code: str


@dataclass(frozen=True, slots=True)
class IngestedArtifact:
    """외부 DTO로 사용하지 않는 내부 ingestion 결과."""

    artifact_id: UUID
    asset_version_id: UUID
    artifact_checksum: str
    size_bytes: int
    media_type: str
    staging_cleanup_pending: bool


class OrphanReporter(Protocol):
    def __call__(self, candidate: OrphanCandidate) -> None: ...


class ArtifactIngestionError(RuntimeError):
    def __init__(
        self,
        code: ArtifactIngestionErrorCode,
        *,
        orphan_candidate: OrphanCandidate | None = None,
    ) -> None:
        super().__init__(_SAFE_MESSAGES[code])
        self.code = code
        self.orphan_candidate = orphan_candidate


class ArtifactIngestionService:
    """Artifact·Catalog transaction과 filesystem 실패 보상을 소유한다."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        artifact_roots: ArtifactStorageRoots,
        staging_root: Path | None,
        orphan_reporter: OrphanReporter | None = None,
        artifact_id_factory: Callable[[], UUID] = generate_uuid,
    ) -> None:
        try:
            publisher = LocalArtifactPublisher(artifact_roots, staging_root)
        except ArtifactPublishError:
            raise ArtifactIngestionError(
                ArtifactIngestionErrorCode.CONFIGURATION_ERROR
            ) from None
        self._session_factory = session_factory
        self._publisher = publisher
        self._orphan_reporter = orphan_reporter
        self._artifact_id_factory = artifact_id_factory

    @classmethod
    def from_base_roots(
        cls,
        session_factory: Callable[[], Session],
        *,
        artifact_root: Path | None,
        staging_root: Path | None,
        orphan_reporter: OrphanReporter | None = None,
    ) -> ArtifactIngestionService:
        try:
            roots = ArtifactStorageRoots.from_base_root(artifact_root)
        except ArtifactStorageError:
            raise ArtifactIngestionError(
                ArtifactIngestionErrorCode.CONFIGURATION_ERROR
            ) from None
        return cls(
            session_factory,
            artifact_roots=roots,
            staging_root=staging_root,
            orphan_reporter=orphan_reporter,
        )

    def ingest(self, request: ArtifactIngestionRequest) -> IngestedArtifact:
        normalized = _validate_request(request)
        artifact_id = self._artifact_id_factory()
        published: PublishedLocalPayload | None = None

        try:
            with self._session_factory() as session, session.begin():
                asset_repository = AssetRepository(session)
                if (
                    asset_repository.get_asset_version(normalized.asset_version_id)
                    is None
                ):
                    raise ArtifactIngestionError(
                        ArtifactIngestionErrorCode.VERSION_NOT_FOUND
                    )
                try:
                    published = self._publisher.publish(
                        normalized.temporary_path,
                        artifact_id=artifact_id,
                        artifact_kind=normalized.artifact_kind,
                        storage_domain=normalized.storage_domain,
                        expected_media_type=normalized.expected_media_type,
                        expected_sha256=normalized.expected_sha256,
                    )
                except ArtifactPublishError as error:
                    raise ArtifactIngestionError(
                        _PUBLISH_ERROR_MAP[error.code]
                    ) from error

                artifact = asset_repository.add_artifact(
                    Artifact(
                        artifact_id=artifact_id,
                        asset_version_id=normalized.asset_version_id,
                        artifact_kind=normalized.artifact_kind,
                        media_type=published.media.media_type,
                        size_bytes=published.size_bytes,
                        checksum_algorithm="sha256",
                        artifact_checksum=published.checksum,
                        producer_type=normalized.producer_type,
                        producer_id=normalized.producer_id,
                        run_id=normalized.run_id,
                        retention_status="active",
                    )
                )
                ArtifactStorageRepository(session).add_storage_location(
                    ArtifactStorageLocation(
                        artifact_id=artifact_id,
                        storage_backend=SUPPORTED_STORAGE_BACKEND,
                        storage_domain=normalized.storage_domain,
                        storage_key=published.storage_key,
                        locator_version=SUPPORTED_LOCATOR_VERSION,
                    )
                )
                resolver = ArtifactStorageResolver(
                    ArtifactStorageRepository(session),
                    self._publisher.artifact_roots,
                )
                resolved = resolver.resolve(artifact_id)
                if (
                    resolved.size_bytes != published.size_bytes
                    or resolved.file_identity != published.file_identity
                    or artifact.artifact_checksum != published.checksum
                ):
                    raise ArtifactIngestionError(
                        ArtifactIngestionErrorCode.VERIFICATION_FAILED
                    )
        except ArtifactIngestionError as error:
            if published is not None:
                candidate = self._compensate(
                    artifact_id,
                    normalized.storage_domain,
                    published,
                    reason_code=error.code.value,
                )
                if candidate is not None:
                    error.orphan_candidate = candidate
            raise
        except Exception as error:
            candidate = None
            if published is not None:
                candidate = self._compensate(
                    artifact_id,
                    normalized.storage_domain,
                    published,
                    reason_code=ArtifactIngestionErrorCode.REGISTRATION_FAILED.value,
                )
            raise ArtifactIngestionError(
                ArtifactIngestionErrorCode.REGISTRATION_FAILED,
                orphan_candidate=candidate,
            ) from error

        cleanup_pending = not self._publisher.cleanup_staging(published)
        if cleanup_pending:
            self._report_orphan(
                OrphanCandidate(
                    artifact_id=artifact_id,
                    storage_domain=normalized.storage_domain,
                    storage_key=None,
                    category="staging_payload",
                    reason_code="STAGING_CLEANUP_FAILED",
                )
            )
        return IngestedArtifact(
            artifact_id=artifact_id,
            asset_version_id=normalized.asset_version_id,
            artifact_checksum=published.checksum,
            size_bytes=published.size_bytes,
            media_type=published.media.media_type,
            staging_cleanup_pending=cleanup_pending,
        )

    def _compensate(
        self,
        artifact_id: UUID,
        storage_domain: str,
        published: PublishedLocalPayload,
        *,
        reason_code: str,
    ) -> OrphanCandidate | None:
        if self._publisher.compensate(published):
            return None
        candidate = OrphanCandidate(
            artifact_id=artifact_id,
            storage_domain=storage_domain,
            storage_key=published.storage_key,
            category="published_payload",
            reason_code=reason_code,
        )
        self._report_orphan(candidate)
        return candidate

    def _report_orphan(self, candidate: OrphanCandidate) -> None:
        logger.warning(
            "Artifact ingestion cleanup requires reconciliation.",
            extra={
                "artifact_id": str(candidate.artifact_id),
                "storage_domain": candidate.storage_domain,
                "reason_code": candidate.reason_code,
            },
        )
        if self._orphan_reporter is not None:
            try:
                self._orphan_reporter(candidate)
            except Exception:
                logger.exception(
                    "Artifact orphan reporter failed.",
                    extra={"artifact_id": str(candidate.artifact_id)},
                )


def _validate_request(request: ArtifactIngestionRequest) -> ArtifactIngestionRequest:
    if type(request.asset_version_id) is not UUID or not isinstance(
        request.temporary_path, Path
    ):
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_REQUEST)
    artifact_kind = _required_text(request.artifact_kind)
    storage_domain = _required_text(request.storage_domain)
    producer_type = _required_text(request.producer_type)
    if artifact_kind not in SUPPORTED_ARTIFACT_KINDS:
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_KIND)
    if storage_domain not in APPROVED_STORAGE_DOMAINS:
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_DOMAIN)
    if artifact_kind not in DOMAIN_ARTIFACT_KINDS[storage_domain]:
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_KIND)
    if producer_type not in APPROVED_PRODUCER_TYPES:
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_PRODUCER)

    expected_media_type = _optional_text(request.expected_media_type)
    expected_sha256 = _optional_text(request.expected_sha256)
    if expected_sha256 is not None:
        expected_sha256 = expected_sha256.lower()
        if not SHA256_PATTERN.fullmatch(expected_sha256):
            raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_REQUEST)
    original_filename = _optional_text(request.original_filename)
    if (
        original_filename is not None
        and Path(original_filename).name != original_filename
    ):
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_REQUEST)

    return ArtifactIngestionRequest(
        asset_version_id=request.asset_version_id,
        artifact_kind=artifact_kind,
        producer_type=producer_type,
        storage_domain=storage_domain,
        temporary_path=request.temporary_path,
        producer_id=_optional_text(request.producer_id),
        run_id=_optional_text(request.run_id),
        expected_media_type=expected_media_type.lower()
        if expected_media_type
        else None,
        expected_sha256=expected_sha256,
        original_filename=original_filename,
    )


def _required_text(value: object) -> str:
    if type(value) is not str or not value.strip():
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_REQUEST)
    return value.strip().lower()


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    if type(value) is not str or not value.strip():
        raise ArtifactIngestionError(ArtifactIngestionErrorCode.INVALID_REQUEST)
    return value.strip()
