"""Local Artifact Catalog와 filesystem drift를 읽기 전용으로 분류한다."""

from __future__ import annotations

import os
import stat
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from uuid import UUID

from sqlalchemy.orm import Session

from backend.repositories.workspace import ArtifactStorageRepository, AssetRepository
from backend.storage.artifact_integrity import calculate_artifact_integrity
from backend.storage.artifact_resolver import (
    APPROVED_MUSIC_NAMESPACES,
    APPROVED_STORAGE_DOMAINS,
    SUPPORTED_STORAGE_BACKEND,
    ArtifactStorageError,
    ArtifactStorageErrorCode,
    ArtifactStorageResolver,
    ArtifactStorageRoots,
    assert_safe_local_path,
    is_link_or_reparse,
    open_regular_local_file,
)

DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_ISSUES = 10_000
DEFAULT_PENDING_GRACE_SECONDS = 3600
_DOMAIN_NAMESPACES = {
    "lm": ("payloads",),
    "audio": ("payloads",),
    "vocal": ("payloads",),
    "music": tuple(sorted(APPROVED_MUSIC_NAMESPACES)),
}


class ArtifactReconciliationIssueType(StrEnum):
    MISSING_PAYLOAD = "missing_payload"
    UNREFERENCED_PAYLOAD = "unreferenced_payload"
    SIZE_MISMATCH = "size_mismatch"
    CHECKSUM_MISMATCH = "checksum_mismatch"
    INVALID_LOCATOR = "invalid_locator"
    CATALOG_WITHOUT_ARTIFACT = "catalog_without_artifact"
    PENDING_PAYLOAD = "pending_payload"
    UNSAFE_FILESYSTEM_ENTRY = "unsafe_filesystem_entry"


@dataclass(frozen=True, slots=True)
class ArtifactReconciliationIssue:
    artifact_id: UUID | None
    storage_domain: str
    storage_key: str | None
    issue_type: ArtifactReconciliationIssueType
    reason_code: str


@dataclass(frozen=True, slots=True)
class ArtifactReconciliationReport:
    dry_run: bool
    scanned_catalog_count: int
    scanned_file_count: int
    healthy_count: int
    missing_payload_count: int
    unreferenced_payload_count: int
    integrity_mismatch_count: int
    invalid_locator_count: int
    catalog_without_artifact_count: int
    pending_candidate_count: int
    unsafe_entry_count: int
    issues: tuple[ArtifactReconciliationIssue, ...]
    issues_truncated: bool


class ArtifactReconciliationError(RuntimeError):
    pass


class _IssueCollector:
    def __init__(self, max_issues: int) -> None:
        self.max_issues = max_issues
        self.issues: list[ArtifactReconciliationIssue] = []
        self.truncated = False
        self.counts = {issue_type: 0 for issue_type in ArtifactReconciliationIssueType}

    def add(self, issue: ArtifactReconciliationIssue) -> None:
        self.counts[issue.issue_type] += 1
        if len(self.issues) < self.max_issues:
            self.issues.append(issue)
        else:
            self.truncated = True


class ArtifactReconciliationService:
    """승인 root와 Catalog만 batch scan하며 어떠한 repair도 수행하지 않는다."""

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        artifact_roots: ArtifactStorageRoots,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_issues: int = DEFAULT_MAX_ISSUES,
        pending_grace_seconds: int = DEFAULT_PENDING_GRACE_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if (
            type(batch_size) is not int
            or batch_size < 1
            or type(max_issues) is not int
            or max_issues < 1
            or type(pending_grace_seconds) is not int
            or pending_grace_seconds < 0
        ):
            raise ArtifactReconciliationError("Reconciliation configuration is invalid.")
        self._session_factory = session_factory
        self._artifact_roots = artifact_roots
        self._batch_size = batch_size
        self._max_issues = max_issues
        self._pending_grace_seconds = pending_grace_seconds
        self._clock = clock

    def scan(self, *, dry_run: bool = True) -> ArtifactReconciliationReport:
        if dry_run is not True:
            raise ArtifactReconciliationError(
                "Destructive Artifact reconciliation is not implemented."
            )
        collector = _IssueCollector(self._max_issues)
        scanned_catalog, healthy = self._scan_catalog(collector)
        scanned_files = self._scan_filesystem(collector)
        counts = collector.counts
        return ArtifactReconciliationReport(
            dry_run=True,
            scanned_catalog_count=scanned_catalog,
            scanned_file_count=scanned_files,
            healthy_count=healthy,
            missing_payload_count=counts[ArtifactReconciliationIssueType.MISSING_PAYLOAD],
            unreferenced_payload_count=counts[ArtifactReconciliationIssueType.UNREFERENCED_PAYLOAD],
            integrity_mismatch_count=(
                counts[ArtifactReconciliationIssueType.SIZE_MISMATCH]
                + counts[ArtifactReconciliationIssueType.CHECKSUM_MISMATCH]
            ),
            invalid_locator_count=counts[ArtifactReconciliationIssueType.INVALID_LOCATOR],
            catalog_without_artifact_count=counts[
                ArtifactReconciliationIssueType.CATALOG_WITHOUT_ARTIFACT
            ],
            pending_candidate_count=counts[ArtifactReconciliationIssueType.PENDING_PAYLOAD],
            unsafe_entry_count=counts[ArtifactReconciliationIssueType.UNSAFE_FILESYSTEM_ENTRY],
            issues=tuple(collector.issues),
            issues_truncated=collector.truncated,
        )

    def _scan_catalog(self, collector: _IssueCollector) -> tuple[int, int]:
        scanned = 0
        healthy = 0
        after_id: UUID | None = None
        with self._session_factory() as session:
            storage_repository = ArtifactStorageRepository(session)
            asset_repository = AssetRepository(session)
            resolver = ArtifactStorageResolver(storage_repository, self._artifact_roots)
            while True:
                rows = storage_repository.list_storage_locations_batch(
                    after_id=after_id, limit=self._batch_size
                )
                if not rows:
                    break
                for location in rows:
                    scanned += 1
                    after_id = location.storage_location_id
                    artifact = asset_repository.get_artifact(location.artifact_id)
                    if artifact is None:
                        collector.add(
                            _issue(
                                location.artifact_id,
                                location.storage_domain,
                                location.storage_key,
                                ArtifactReconciliationIssueType.CATALOG_WITHOUT_ARTIFACT,
                                "CATALOG_ARTIFACT_MISSING",
                            )
                        )
                        continue
                    row_healthy = self._verify_catalog_payload(
                        resolver,
                        artifact,
                        location.storage_domain,
                        location.storage_key,
                        collector,
                    )
                    if row_healthy:
                        healthy += 1
                if len(rows) < self._batch_size:
                    break
        return scanned, healthy

    def _verify_catalog_payload(
        self,
        resolver: ArtifactStorageResolver,
        artifact: object,
        storage_domain: str,
        storage_key: str,
        collector: _IssueCollector,
    ) -> bool:
        artifact_id = artifact.artifact_id
        try:
            with resolver.open_payload(artifact_id) as (resolved, stream):
                row_healthy = True
                integrity = calculate_artifact_integrity(stream)
                if (
                    resolved.size_bytes != artifact.size_bytes
                    or integrity.size_bytes != artifact.size_bytes
                ):
                    collector.add(
                        _issue(
                            artifact_id,
                            storage_domain,
                            storage_key,
                            ArtifactReconciliationIssueType.SIZE_MISMATCH,
                            "PAYLOAD_SIZE_MISMATCH",
                        )
                    )
                    row_healthy = False
                if (
                    artifact.checksum_algorithm != "sha256"
                    or integrity.checksum != artifact.artifact_checksum
                ):
                    collector.add(
                        _issue(
                            artifact_id,
                            storage_domain,
                            storage_key,
                            ArtifactReconciliationIssueType.CHECKSUM_MISMATCH,
                            "PAYLOAD_CHECKSUM_MISMATCH",
                        )
                    )
                    row_healthy = False
                return row_healthy
        except ArtifactStorageError as error:
            issue_type = (
                ArtifactReconciliationIssueType.MISSING_PAYLOAD
                if error.code == ArtifactStorageErrorCode.CONTENT_UNAVAILABLE
                else ArtifactReconciliationIssueType.INVALID_LOCATOR
            )
            collector.add(
                _issue(
                    artifact_id,
                    storage_domain,
                    storage_key,
                    issue_type,
                    error.code.value,
                )
            )
            return False
        except OSError:
            collector.add(
                _issue(
                    artifact_id,
                    storage_domain,
                    storage_key,
                    ArtifactReconciliationIssueType.MISSING_PAYLOAD,
                    "PAYLOAD_READ_FAILED",
                )
            )
            return False

    def _scan_filesystem(self, collector: _IssueCollector) -> int:
        scanned_files = 0
        with self._session_factory() as session:
            repository = ArtifactStorageRepository(session)
            for domain in sorted(APPROVED_STORAGE_DOMAINS):
                root = self._artifact_roots.roots[domain]
                scanned_files += self._scan_pending(root, domain, collector)
                for namespace in _DOMAIN_NAMESPACES[domain]:
                    namespace_path = root / namespace
                    for storage_key, payload, safe in _walk_namespace(root, namespace_path):
                        scanned_files += 1
                        if not safe:
                            collector.add(
                                _issue(
                                    None,
                                    domain,
                                    storage_key,
                                    ArtifactReconciliationIssueType.UNSAFE_FILESYSTEM_ENTRY,
                                    "FILESYSTEM_LINK_OR_NONREGULAR",
                                )
                            )
                            continue
                        try:
                            self._artifact_roots.candidate_path(domain, storage_key)
                            descriptor, _ = open_regular_local_file(root, payload)
                            os.close(descriptor)
                        except (ArtifactStorageError, OSError):
                            collector.add(
                                _issue(
                                    None,
                                    domain,
                                    storage_key,
                                    ArtifactReconciliationIssueType.UNSAFE_FILESYSTEM_ENTRY,
                                    "FILESYSTEM_ENTRY_REJECTED",
                                )
                            )
                            continue
                        location = repository.get_storage_location_by_locator(
                            storage_backend=SUPPORTED_STORAGE_BACKEND,
                            storage_domain=domain,
                            storage_key=storage_key,
                        )
                        if location is None:
                            collector.add(
                                _issue(
                                    None,
                                    domain,
                                    storage_key,
                                    ArtifactReconciliationIssueType.UNREFERENCED_PAYLOAD,
                                    "CATALOG_LOCATION_MISSING",
                                )
                            )
        return scanned_files

    def _scan_pending(
        self,
        root: Path,
        domain: str,
        collector: _IssueCollector,
    ) -> int:
        pending_root = root / ".ingestion"
        if not os.path.lexists(pending_root):
            return 0
        scanned = 0
        for storage_key, payload, safe in _walk_namespace(root, pending_root):
            scanned += 1
            if not safe:
                collector.add(
                    _issue(
                        None,
                        domain,
                        storage_key,
                        ArtifactReconciliationIssueType.UNSAFE_FILESYSTEM_ENTRY,
                        "PENDING_ENTRY_REJECTED",
                    )
                )
                continue
            try:
                age = self._clock() - payload.stat(follow_symlinks=False).st_mtime
            except OSError:
                collector.add(
                    _issue(
                        None,
                        domain,
                        storage_key,
                        ArtifactReconciliationIssueType.UNSAFE_FILESYSTEM_ENTRY,
                        "PENDING_STAT_FAILED",
                    )
                )
                continue
            if age >= self._pending_grace_seconds:
                collector.add(
                    _issue(
                        None,
                        domain,
                        storage_key,
                        ArtifactReconciliationIssueType.PENDING_PAYLOAD,
                        "PENDING_GRACE_EXPIRED",
                    )
                )
        return scanned


def _walk_namespace(
    root: Path,
    namespace_path: Path,
) -> Iterator[tuple[str, Path, bool]]:
    if not os.path.lexists(namespace_path):
        return
    stack = [namespace_path]
    while stack:
        current = stack.pop()
        if is_link_or_reparse(current):
            yield _relative_key(root, current), current, False
            continue
        try:
            assert_safe_local_path(root, current)
            current.resolve(strict=True).relative_to(root)
            entries = list(os.scandir(current))
            assert_safe_local_path(root, current)
        except (ArtifactStorageError, OSError, RuntimeError, ValueError):
            yield _relative_key(root, current), current, False
            continue
        for entry in entries:
            path = Path(entry.path)
            key = _relative_key(root, path)
            if is_link_or_reparse(path):
                yield key, path, False
                continue
            try:
                entry_stat = entry.stat(follow_symlinks=False)
            except OSError:
                yield key, path, False
                continue
            if stat.S_ISDIR(entry_stat.st_mode):
                stack.append(path)
            elif stat.S_ISREG(entry_stat.st_mode):
                yield key, path, True
            else:
                yield key, path, False


def _relative_key(root: Path, path: Path) -> str:
    try:
        value = path.relative_to(root).as_posix()
    except ValueError:
        return "invalid"
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        return "invalid"
    return value


def _issue(
    artifact_id: UUID | None,
    storage_domain: str,
    storage_key: str | None,
    issue_type: ArtifactReconciliationIssueType,
    reason_code: str,
) -> ArtifactReconciliationIssue:
    return ArtifactReconciliationIssue(
        artifact_id=artifact_id,
        storage_domain=(
            storage_domain if storage_domain in APPROVED_STORAGE_DOMAINS else "invalid"
        ),
        storage_key=_safe_report_key(storage_key),
        issue_type=issue_type,
        reason_code=reason_code,
    )


def _safe_report_key(storage_key: object) -> str | None:
    if type(storage_key) is not str or not storage_key:
        return None
    if (
        "\\" in storage_key
        or ":" in storage_key
        or storage_key.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in storage_key)
    ):
        return None
    parts = storage_key.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    parsed = PurePosixPath(storage_key)
    if parsed.is_absolute() or parsed.as_posix() != storage_key:
        return None
    return storage_key
