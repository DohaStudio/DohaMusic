"""Artifact ID를 승인된 local root 내부의 안전한 Payload로 해석한다."""

from __future__ import annotations

import os
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import BinaryIO, Protocol
from uuid import UUID

from backend.models.workspace.storage import ArtifactStorageLocation

APPROVED_STORAGE_DOMAINS = frozenset({"lm", "audio", "vocal", "music"})
APPROVED_MUSIC_NAMESPACES = frozenset(
    {"mixes", "exports", "previews", "snapshots", "runs"}
)
SUPPORTED_STORAGE_BACKEND = "local"
SUPPORTED_LOCATOR_VERSION = 1

_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)


class ArtifactStorageErrorCode(StrEnum):
    LOCATION_NOT_FOUND = "ARTIFACT_STORAGE_LOCATION_NOT_FOUND"
    CONTENT_UNAVAILABLE = "ARTIFACT_CONTENT_UNAVAILABLE"
    UNSUPPORTED_BACKEND = "UNSUPPORTED_STORAGE_BACKEND"
    UNSUPPORTED_LOCATOR_VERSION = "UNSUPPORTED_STORAGE_LOCATOR_VERSION"
    INVALID_DOMAIN = "INVALID_STORAGE_DOMAIN"
    INVALID_KEY = "INVALID_STORAGE_KEY"
    STORAGE_ESCAPE = "ARTIFACT_STORAGE_ESCAPE"
    CONFIGURATION_ERROR = "ARTIFACT_STORAGE_CONFIGURATION_ERROR"


_SAFE_ERROR_MESSAGES = {
    ArtifactStorageErrorCode.LOCATION_NOT_FOUND: "Artifact storage location is unavailable.",
    ArtifactStorageErrorCode.CONTENT_UNAVAILABLE: "Artifact content is unavailable.",
    ArtifactStorageErrorCode.UNSUPPORTED_BACKEND: "Artifact storage backend is unsupported.",
    ArtifactStorageErrorCode.UNSUPPORTED_LOCATOR_VERSION: (
        "Artifact storage locator version is unsupported."
    ),
    ArtifactStorageErrorCode.INVALID_DOMAIN: "Artifact storage domain is invalid.",
    ArtifactStorageErrorCode.INVALID_KEY: "Artifact storage key is invalid.",
    ArtifactStorageErrorCode.STORAGE_ESCAPE: "Artifact storage boundary was rejected.",
    ArtifactStorageErrorCode.CONFIGURATION_ERROR: (
        "Artifact storage configuration is invalid."
    ),
}


class ArtifactStorageError(RuntimeError):
    """내부 경로를 노출하지 않는 Resolver 오류."""

    def __init__(self, code: ArtifactStorageErrorCode) -> None:
        super().__init__(_SAFE_ERROR_MESSAGES[code])
        self.code = code


class ArtifactStorageLocationReader(Protocol):
    """Resolver가 요구하는 최소 Catalog 조회 계약."""

    def get_storage_location(
        self, artifact_id: UUID
    ) -> ArtifactStorageLocation | None: ...


@dataclass(frozen=True, slots=True)
class ResolvedArtifactPayload:
    """공개 DTO로 사용하지 않는 검증된 local Payload 참조."""

    artifact_id: UUID
    path: Path
    size_bytes: int
    modified_ns: int
    storage_backend: str
    storage_domain: str
    file_identity: tuple[int, int]


@dataclass(frozen=True, slots=True)
class ArtifactStorageRoots:
    """승인된 domain별 local root의 불변 매핑."""

    roots: Mapping[str, Path]

    @classmethod
    def from_base_root(cls, artifact_root: Path | None) -> ArtifactStorageRoots:
        if artifact_root is None:
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONFIGURATION_ERROR)
        return cls(
            {
                domain: artifact_root / domain
                for domain in sorted(APPROVED_STORAGE_DOMAINS)
            }
        )

    def __post_init__(self) -> None:
        if set(self.roots) != APPROVED_STORAGE_DOMAINS:
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONFIGURATION_ERROR)
        validated = {
            domain: _validate_root(root) for domain, root in self.roots.items()
        }
        object.__setattr__(self, "roots", MappingProxyType(validated))


class ArtifactStorageResolver:
    """Catalog locator를 검증하고 승인 root 내부 regular file만 반환한다."""

    def __init__(
        self,
        repository: ArtifactStorageLocationReader,
        roots: ArtifactStorageRoots,
    ) -> None:
        self._repository = repository
        self._roots = roots

    @classmethod
    def from_base_root(
        cls,
        repository: ArtifactStorageLocationReader,
        artifact_root: Path | None,
    ) -> ArtifactStorageResolver:
        return cls(repository, ArtifactStorageRoots.from_base_root(artifact_root))

    def resolve(self, artifact_id: UUID) -> ResolvedArtifactPayload:
        location = self._repository.get_storage_location(artifact_id)
        if location is None:
            raise ArtifactStorageError(ArtifactStorageErrorCode.LOCATION_NOT_FOUND)
        if location.storage_backend != SUPPORTED_STORAGE_BACKEND:
            raise ArtifactStorageError(ArtifactStorageErrorCode.UNSUPPORTED_BACKEND)
        if location.locator_version != SUPPORTED_LOCATOR_VERSION:
            raise ArtifactStorageError(
                ArtifactStorageErrorCode.UNSUPPORTED_LOCATOR_VERSION
            )
        if location.storage_domain not in APPROVED_STORAGE_DOMAINS:
            raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_DOMAIN)

        key = _validate_storage_key(location.storage_key, location.storage_domain)
        root = self._roots.roots[location.storage_domain]
        candidate = root.joinpath(*key.parts)
        _assert_no_link_or_reparse(root, candidate)

        try:
            resolved_path = candidate.resolve(strict=True)
        except (OSError, RuntimeError):
            raise ArtifactStorageError(
                ArtifactStorageErrorCode.CONTENT_UNAVAILABLE
            ) from None

        try:
            resolved_path.relative_to(root)
        except ValueError:
            raise ArtifactStorageError(
                ArtifactStorageErrorCode.STORAGE_ESCAPE
            ) from None

        descriptor, descriptor_stat = _open_regular_file(root, resolved_path)
        os.close(descriptor)
        return ResolvedArtifactPayload(
            artifact_id=artifact_id,
            path=resolved_path,
            size_bytes=descriptor_stat.st_size,
            modified_ns=descriptor_stat.st_mtime_ns,
            storage_backend=location.storage_backend,
            storage_domain=location.storage_domain,
            file_identity=(descriptor_stat.st_dev, descriptor_stat.st_ino),
        )

    @contextmanager
    def open_payload(
        self, artifact_id: UUID
    ) -> Iterator[tuple[ResolvedArtifactPayload, BinaryIO]]:
        """재검증한 동일 file descriptor를 content 계층에 제공한다."""

        resolved = self.resolve(artifact_id)
        root = self._roots.roots[resolved.storage_domain]
        descriptor, descriptor_stat = _open_regular_file(root, resolved.path)
        if (
            descriptor_stat.st_size != resolved.size_bytes
            or descriptor_stat.st_mtime_ns != resolved.modified_ns
            or (descriptor_stat.st_dev, descriptor_stat.st_ino)
            != resolved.file_identity
        ):
            os.close(descriptor)
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONTENT_UNAVAILABLE)

        stream = os.fdopen(descriptor, "rb", closefd=True)
        try:
            yield resolved, stream
        finally:
            stream.close()


def _validate_storage_key(value: object, storage_domain: str) -> PurePosixPath:
    if type(value) is not str or not value:
        raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_KEY)
    key = value
    if (
        "\x00" in key
        or "\\" in key
        or "%" in key
        or ":" in key
        or key.startswith("/")
        or any(ord(character) < 32 or ord(character) == 127 for character in key)
    ):
        raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_KEY)

    raw_parts = key.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_KEY)
    if any(_is_windows_reserved_segment(part) for part in raw_parts):
        raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_KEY)

    parsed = PurePosixPath(key)
    if parsed.is_absolute() or parsed.as_posix() != key:
        raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_KEY)
    if storage_domain == "music" and parsed.parts[0] not in APPROVED_MUSIC_NAMESPACES:
        raise ArtifactStorageError(ArtifactStorageErrorCode.INVALID_KEY)
    return parsed


def _is_windows_reserved_segment(segment: str) -> bool:
    if segment.endswith((" ", ".")):
        return True
    stem = segment.split(".", 1)[0].upper()
    return stem in _WINDOWS_RESERVED_NAMES


def _validate_root(root: Path) -> Path:
    try:
        absolute = root.expanduser().absolute()
        if not absolute.exists() or not absolute.is_dir():
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONFIGURATION_ERROR)
        _assert_path_components_are_directories(absolute)
        resolved = absolute.resolve(strict=True)
    except ArtifactStorageError:
        raise
    except (OSError, RuntimeError):
        raise ArtifactStorageError(
            ArtifactStorageErrorCode.CONFIGURATION_ERROR
        ) from None
    if _is_link_or_reparse(absolute):
        raise ArtifactStorageError(ArtifactStorageErrorCode.CONFIGURATION_ERROR)
    return resolved


def _assert_path_components_are_directories(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if _is_link_or_reparse(current):
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONFIGURATION_ERROR)


def _assert_no_link_or_reparse(root: Path, candidate: Path) -> None:
    try:
        relative_parts = candidate.relative_to(root).parts
    except ValueError:
        raise ArtifactStorageError(ArtifactStorageErrorCode.STORAGE_ESCAPE) from None

    current = root
    for part in relative_parts:
        current /= part
        if os.path.lexists(current) and _is_link_or_reparse(current):
            raise ArtifactStorageError(ArtifactStorageErrorCode.STORAGE_ESCAPE)


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _open_regular_file(root: Path, path: Path) -> tuple[int, os.stat_result]:
    _assert_no_link_or_reparse(root, path)
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        raise ArtifactStorageError(
            ArtifactStorageErrorCode.CONTENT_UNAVAILABLE
        ) from None

    try:
        descriptor_stat = os.fstat(descriptor)
        if not stat.S_ISREG(descriptor_stat.st_mode):
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONTENT_UNAVAILABLE)
        path_stat = path.stat(follow_symlinks=False)
        if (
            path_stat.st_dev,
            path_stat.st_ino,
        ) != (
            descriptor_stat.st_dev,
            descriptor_stat.st_ino,
        ):
            raise ArtifactStorageError(ArtifactStorageErrorCode.CONTENT_UNAVAILABLE)
        _assert_no_link_or_reparse(root, path)
        return descriptor, descriptor_stat
    except Exception:
        os.close(descriptor)
        raise
