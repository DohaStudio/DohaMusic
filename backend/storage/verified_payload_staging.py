"""Verified provider payloads를 durable local staging에 불변 publish한다."""

from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Callable, Iterable, Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager, suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Protocol
from uuid import UUID, uuid4

from backend.core.payload_locator import (
    EXPECTED_MEDIA_TYPES,
    SHA256_PATTERN,
    VerifiedStagingFacts,
    is_safe_staging_key,
)
from backend.storage.artifact_media import ArtifactMediaValidationError, validate_artifact_media
from backend.storage.artifact_resolver import (
    ArtifactStorageError,
    ArtifactStorageRoots,
    assert_safe_local_path,
    open_regular_local_file,
    validate_local_root,
)

STAGING_BACKEND = "local"
COPY_CHUNK_SIZE = 1024 * 1024
_MEDIA_EXTENSIONS: Mapping[str, str] = {
    "audio/wav": "wav",
    "audio/flac": "flac",
    "application/json": "json",
}
_WINDOWS_RESERVED_NAMES = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{number}" for number in range(1, 10)}
    | {f"LPT{number}" for number in range(1, 10)}
)
_PARTIAL_NAME_PATTERN = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\."
    r"([0-9a-f]{32})\.partial"
)


class VerifiedPayloadStagingErrorCode(StrEnum):
    CONFIGURATION_ERROR = "VERIFIED_PAYLOAD_STAGING_CONFIGURATION_ERROR"
    INVALID_INPUT = "VERIFIED_PAYLOAD_STAGING_INVALID_INPUT"
    INVALID_KEY = "VERIFIED_PAYLOAD_STAGING_INVALID_KEY"
    WRITE_FAILED = "VERIFIED_PAYLOAD_STAGING_WRITE_FAILED"
    INTEGRITY_MISMATCH = "VERIFIED_PAYLOAD_STAGING_INTEGRITY_MISMATCH"
    MEDIA_MISMATCH = "VERIFIED_PAYLOAD_STAGING_MEDIA_MISMATCH"
    PUBLISH_CONFLICT = "VERIFIED_PAYLOAD_STAGING_PUBLISH_CONFLICT"
    PUBLISH_FAILED = "VERIFIED_PAYLOAD_STAGING_PUBLISH_FAILED"
    CONTENT_MISSING = "VERIFIED_PAYLOAD_STAGING_CONTENT_MISSING"
    CONTENT_TAMPERED = "VERIFIED_PAYLOAD_STAGING_CONTENT_TAMPERED"
    CLEANUP_FAILED = "VERIFIED_PAYLOAD_STAGING_CLEANUP_FAILED"


_SAFE_MESSAGES = {
    VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR: (
        "Payload staging configuration is invalid."
    ),
    VerifiedPayloadStagingErrorCode.INVALID_INPUT: "Payload staging input is invalid.",
    VerifiedPayloadStagingErrorCode.INVALID_KEY: "Payload staging key is invalid.",
    VerifiedPayloadStagingErrorCode.WRITE_FAILED: "Payload staging write failed.",
    VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH: "Payload integrity verification failed.",
    VerifiedPayloadStagingErrorCode.MEDIA_MISMATCH: "Payload media verification failed.",
    VerifiedPayloadStagingErrorCode.PUBLISH_CONFLICT: (
        "Payload staging publish conflict was detected."
    ),
    VerifiedPayloadStagingErrorCode.PUBLISH_FAILED: "Payload staging publish failed.",
    VerifiedPayloadStagingErrorCode.CONTENT_MISSING: "Verified staged payload is unavailable.",
    VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED: (
        "Verified staged payload changed after verification."
    ),
    VerifiedPayloadStagingErrorCode.CLEANUP_FAILED: "Verified staged payload cleanup failed.",
}


class VerifiedPayloadStagingError(RuntimeError):
    """경로나 외부 source 정보를 노출하지 않는 stable 내부 오류."""

    def __init__(self, code: VerifiedPayloadStagingErrorCode) -> None:
        super().__init__(_SAFE_MESSAGES[code])
        self.code = code


@dataclass(frozen=True, slots=True)
class ExpectedPayloadFacts:
    checksum_algorithm: str
    payload_checksum: str
    size_bytes: int
    media_type: str

    def __post_init__(self) -> None:
        if (
            self.checksum_algorithm != "sha256"
            or SHA256_PATTERN.fullmatch(self.payload_checksum) is None
            or type(self.size_bytes) is not int
            or self.size_bytes <= 0
            or self.media_type not in EXPECTED_MEDIA_TYPES
        ):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_INPUT)


@dataclass(frozen=True, slots=True)
class VerifiedStagedPayload:
    staging_backend: str
    staging_key: str
    checksum_algorithm: str
    payload_checksum: str
    size_bytes: int
    media_type: str
    verified_at: datetime

    def __post_init__(self) -> None:
        if (
            self.staging_backend != STAGING_BACKEND
            or not is_safe_staging_key(self.staging_key)
            or self.checksum_algorithm != "sha256"
            or SHA256_PATTERN.fullmatch(self.payload_checksum) is None
            or type(self.size_bytes) is not int
            or self.size_bytes <= 0
            or self.media_type not in EXPECTED_MEDIA_TYPES
            or not isinstance(self.verified_at, datetime)
            or self.verified_at.tzinfo is None
            or self.verified_at.utcoffset() is None
            or self.verified_at.utcoffset().total_seconds() != 0
        ):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_INPUT)

    def as_locator_facts(self) -> VerifiedStagingFacts:
        return VerifiedStagingFacts(
            staging_backend=self.staging_backend,
            staging_key=self.staging_key,
            actual_checksum_algorithm=self.checksum_algorithm,
            actual_payload_checksum=self.payload_checksum,
            actual_size_bytes=self.size_bytes,
            actual_media_type=self.media_type,
            verified_at=self.verified_at,
        )


class VerifiedPayloadStagingPort(Protocol):
    def recover_published(
        self,
        locator_uuid: UUID,
        expected: ExpectedPayloadFacts,
    ) -> VerifiedStagedPayload | None: ...

    def stage_verified(
        self,
        locator_uuid: UUID,
        chunks: Iterable[bytes],
        expected: ExpectedPayloadFacts,
    ) -> VerifiedStagedPayload: ...

    def open_verified(self, payload: VerifiedStagedPayload) -> AbstractContextManager[BinaryIO]: ...

    def delete_verified(self, payload: VerifiedStagedPayload) -> bool: ...


@dataclass(frozen=True, slots=True)
class _InspectedPayload:
    checksum: str
    size_bytes: int
    media_type: str
    identity: tuple[int, int]


class LocalFilesystemStagingAdapter:
    """Random partial을 검증한 뒤 deterministic final key로 원자 publish한다."""

    def __init__(
        self,
        staging_root: Path | None,
        *,
        artifact_roots: ArtifactStorageRoots | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if staging_root is None:
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR)
        try:
            root = validate_local_root(staging_root)
        except ArtifactStorageError:
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR
            ) from None
        if artifact_roots is not None and any(
            _paths_overlap(root, artifact_root) for artifact_root in artifact_roots.roots.values()
        ):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR)
        self._root = root
        self._clock = clock or (lambda: datetime.now(UTC))

    def stage_verified(
        self,
        locator_uuid: UUID,
        chunks: Iterable[bytes],
        expected: ExpectedPayloadFacts,
    ) -> VerifiedStagedPayload:
        if not isinstance(locator_uuid, UUID) or not isinstance(expected, ExpectedPayloadFacts):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_INPUT)
        final_key = self.final_key(locator_uuid, expected.media_type)
        final_path = self._path_for_key(final_key)
        recovered = self.recover_published(locator_uuid, expected)
        if recovered is not None:
            return recovered

        partial_key = self._partial_key(locator_uuid)
        partial_path = self._path_for_key(partial_key)
        _ensure_directory(self._root, partial_path.parent)
        _ensure_directory(self._root, final_path.parent)
        partial_identity: tuple[int, int] | None = None
        published_by_attempt = False
        try:
            write_checksum, write_size, partial_identity = self._write_partial(
                partial_path, chunks, expected.size_bytes
            )
            if write_checksum != expected.payload_checksum or write_size != expected.size_bytes:
                raise VerifiedPayloadStagingError(
                    VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH
                )
            inspected = self._inspect(partial_path, expected.media_type)
            self._require_expected(partial_key, inspected, expected)
            if inspected.identity != partial_identity:
                raise VerifiedPayloadStagingError(
                    VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH
                )

            try:
                os.link(partial_path, final_path)
                published_by_attempt = True
            except FileExistsError:
                existing = self._inspect_if_present(final_path, expected.media_type)
                if existing is None:
                    raise VerifiedPayloadStagingError(
                        VerifiedPayloadStagingErrorCode.PUBLISH_FAILED
                    ) from None
                return self._require_expected(final_key, existing, expected)
            except OSError:
                raise VerifiedPayloadStagingError(
                    VerifiedPayloadStagingErrorCode.PUBLISH_FAILED
                ) from None

            published = self._inspect(final_path, expected.media_type)
            self._require_expected(final_key, published, expected)
            if published.identity != partial_identity:
                raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.PUBLISH_FAILED)
            _sync_directory(final_path.parent)
            return self._verified(final_key, published)
        except Exception:
            if published_by_attempt and partial_identity is not None:
                _unlink_if_identity_matches(final_path, partial_identity)
            raise
        finally:
            if partial_identity is not None:
                _unlink_if_identity_matches(partial_path, partial_identity)

    def recover_published(
        self,
        locator_uuid: UUID,
        expected: ExpectedPayloadFacts,
    ) -> VerifiedStagedPayload | None:
        if not isinstance(locator_uuid, UUID) or not isinstance(expected, ExpectedPayloadFacts):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_INPUT)
        final_key = self.final_key(locator_uuid, expected.media_type)
        final_path = self._path_for_key(final_key)
        existing = self._inspect_if_present(final_path, expected.media_type)
        if existing is None:
            return None
        return self._require_expected(final_key, existing, expected)

    @contextmanager
    def open_verified(self, payload: VerifiedStagedPayload) -> Iterator[BinaryIO]:
        expected = _expected_from_verified(payload)
        path = self._path_for_key(payload.staging_key)
        inspected = self._inspect(path, expected.media_type)
        self._require_expected(payload.staging_key, inspected, expected, tampered=True)
        try:
            descriptor, descriptor_stat = open_regular_local_file(self._root, path)
        except ArtifactStorageError:
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
            ) from None
        if (descriptor_stat.st_dev, descriptor_stat.st_ino) != inspected.identity:
            os.close(descriptor)
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED)
        stream = os.fdopen(descriptor, "rb", closefd=True)
        try:
            digest = hashlib.sha256()
            size_bytes = 0
            while chunk := stream.read(COPY_CHUNK_SIZE):
                digest.update(chunk)
                size_bytes += len(chunk)
            if digest.hexdigest() != expected.payload_checksum or size_bytes != expected.size_bytes:
                raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED)
            stream.seek(0)
            yield stream
        finally:
            stream.close()

    def delete_verified(self, payload: VerifiedStagedPayload) -> bool:
        expected = _expected_from_verified(payload)
        path = self._path_for_key(payload.staging_key)
        try:
            inspected = self._inspect(path, expected.media_type)
        except VerifiedPayloadStagingError as error:
            if error.code is VerifiedPayloadStagingErrorCode.CONTENT_MISSING:
                return False
            raise
        self._require_expected(payload.staging_key, inspected, expected, tampered=True)
        if not _unlink_if_identity_matches(path, inspected.identity):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CLEANUP_FAILED)
        _sync_directory(path.parent)
        return True

    def cleanup_partial(self, partial_key: str) -> bool:
        """Staleness 판정은 하지 않고 승인된 partial identity만 안전하게 제거한다."""

        parsed = _validate_key(partial_key)
        if not _is_partial_key(parsed):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_KEY)
        path = self._path_for_key(partial_key)
        try:
            descriptor, payload_stat = open_regular_local_file(self._root, path)
        except ArtifactStorageError:
            if not os.path.lexists(path):
                return False
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
            ) from None
        os.close(descriptor)
        identity = (payload_stat.st_dev, payload_stat.st_ino)
        if not _unlink_if_identity_matches(path, identity):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CLEANUP_FAILED)
        _sync_directory(path.parent)
        return True

    @staticmethod
    def final_key(locator_uuid: UUID, media_type: str) -> str:
        extension = _MEDIA_EXTENSIONS.get(media_type)
        if not isinstance(locator_uuid, UUID) or extension is None:
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_INPUT)
        return f"payload-staging/v1/{locator_uuid.hex[:2]}/{locator_uuid}.{extension}"

    def _partial_key(self, locator_uuid: UUID) -> str:
        return f".partial/v1/{locator_uuid.hex[:2]}/{locator_uuid}.{uuid4().hex}.partial"

    def _path_for_key(self, key: str) -> Path:
        parsed = _validate_key(key)
        candidate = self._root.joinpath(*parsed.parts)
        try:
            assert_safe_local_path(self._root, candidate)
            candidate.resolve(strict=False).relative_to(self._root)
        except (ArtifactStorageError, OSError, RuntimeError, ValueError):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_KEY) from None
        return candidate

    def _write_partial(
        self, path: Path, chunks: Iterable[bytes], expected_size: int
    ) -> tuple[str, int, tuple[int, int]]:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(path, flags, 0o600)
        except OSError:
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.WRITE_FAILED
            ) from None
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            opened_stat = os.fstat(descriptor)
            opened_identity = (opened_stat.st_dev, opened_stat.st_ino)
        except OSError:
            os.close(descriptor)
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.WRITE_FAILED
            ) from None
        try:
            with os.fdopen(descriptor, "wb", closefd=True) as destination:
                for chunk in chunks:
                    if not isinstance(chunk, bytes) or not chunk:
                        raise VerifiedPayloadStagingError(
                            VerifiedPayloadStagingErrorCode.INVALID_INPUT
                        )
                    size_bytes += len(chunk)
                    if size_bytes > expected_size:
                        raise VerifiedPayloadStagingError(
                            VerifiedPayloadStagingErrorCode.INTEGRITY_MISMATCH
                        )
                    destination.write(chunk)
                    digest.update(chunk)
                destination.flush()
                os.fsync(destination.fileno())
            payload_stat = path.stat(follow_symlinks=False)
            return digest.hexdigest(), size_bytes, (payload_stat.st_dev, payload_stat.st_ino)
        except VerifiedPayloadStagingError:
            _unlink_if_identity_matches(path, opened_identity)
            raise
        except Exception:
            _unlink_if_identity_matches(path, opened_identity)
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.WRITE_FAILED
            ) from None

    def _inspect_if_present(self, path: Path, expected_media_type: str) -> _InspectedPayload | None:
        try:
            return self._inspect(path, expected_media_type)
        except VerifiedPayloadStagingError as error:
            if error.code is VerifiedPayloadStagingErrorCode.CONTENT_MISSING:
                return None
            raise

    def _inspect(self, path: Path, expected_media_type: str) -> _InspectedPayload:
        try:
            descriptor, descriptor_stat = open_regular_local_file(self._root, path)
        except ArtifactStorageError:
            if not os.path.lexists(path):
                raise VerifiedPayloadStagingError(
                    VerifiedPayloadStagingErrorCode.CONTENT_MISSING
                ) from None
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
            ) from None
        digest = hashlib.sha256()
        size_bytes = 0
        try:
            with os.fdopen(descriptor, "rb", closefd=True) as source:
                while chunk := source.read(COPY_CHUNK_SIZE):
                    digest.update(chunk)
                    size_bytes += len(chunk)
        except OSError:
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
            ) from None
        try:
            media = validate_artifact_media(
                path,
                artifact_kind="manifest" if expected_media_type == "application/json" else "audio",
                size_bytes=size_bytes,
            )
        except (ArtifactMediaValidationError, OSError):
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.MEDIA_MISMATCH
            ) from None
        identity = (descriptor_stat.st_dev, descriptor_stat.st_ino)
        try:
            descriptor2, descriptor_stat2 = open_regular_local_file(self._root, path)
        except ArtifactStorageError:
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
            ) from None
        digest2 = hashlib.sha256()
        size2 = 0
        with os.fdopen(descriptor2, "rb", closefd=True) as source:
            while chunk := source.read(COPY_CHUNK_SIZE):
                digest2.update(chunk)
                size2 += len(chunk)
        if (
            (descriptor_stat2.st_dev, descriptor_stat2.st_ino) != identity
            or size2 != size_bytes
            or digest2.digest() != digest.digest()
        ):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED)
        return _InspectedPayload(digest.hexdigest(), size_bytes, media.media_type, identity)

    def _require_expected(
        self,
        key: str,
        inspected: _InspectedPayload,
        expected: ExpectedPayloadFacts,
        *,
        tampered: bool = False,
    ) -> VerifiedStagedPayload:
        if inspected.media_type != expected.media_type:
            code = (
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
                if tampered
                else VerifiedPayloadStagingErrorCode.MEDIA_MISMATCH
            )
            raise VerifiedPayloadStagingError(code)
        if (
            inspected.checksum != expected.payload_checksum
            or inspected.size_bytes != expected.size_bytes
        ):
            code = (
                VerifiedPayloadStagingErrorCode.CONTENT_TAMPERED
                if tampered
                else VerifiedPayloadStagingErrorCode.PUBLISH_CONFLICT
            )
            raise VerifiedPayloadStagingError(code)
        return self._verified(key, inspected)

    def _verified(self, key: str, inspected: _InspectedPayload) -> VerifiedStagedPayload:
        verified_at = self._clock()
        if (
            not isinstance(verified_at, datetime)
            or verified_at.tzinfo is None
            or verified_at.utcoffset() is None
            or verified_at.utcoffset().total_seconds() != 0
        ):
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.CONFIGURATION_ERROR)
        return VerifiedStagedPayload(
            staging_backend=STAGING_BACKEND,
            staging_key=key,
            checksum_algorithm="sha256",
            payload_checksum=inspected.checksum,
            size_bytes=inspected.size_bytes,
            media_type=inspected.media_type,
            verified_at=verified_at,
        )


def _expected_from_verified(payload: VerifiedStagedPayload) -> ExpectedPayloadFacts:
    if not isinstance(payload, VerifiedStagedPayload) or payload.staging_backend != STAGING_BACKEND:
        raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_INPUT)
    return ExpectedPayloadFacts(
        checksum_algorithm=payload.checksum_algorithm,
        payload_checksum=payload.payload_checksum,
        size_bytes=payload.size_bytes,
        media_type=payload.media_type,
    )


def _validate_key(value: object) -> PurePosixPath:
    if type(value) is not str or not value or len(value) > 512:
        raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_KEY)
    if (
        "\x00" in value
        or "\\" in value
        or "%" in value
        or ":" in value
        or value.startswith("/")
        or not value.isascii()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_KEY)
    parts = value.split("/")
    if any(part in {"", ".", ".."} or _is_windows_reserved(part) for part in parts):
        raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_KEY)
    parsed = PurePosixPath(value)
    if parsed.is_absolute() or parsed.as_posix() != value:
        raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.INVALID_KEY)
    return parsed


def _is_windows_reserved(segment: str) -> bool:
    return (
        segment.endswith((" ", ".")) or segment.split(".", 1)[0].upper() in _WINDOWS_RESERVED_NAMES
    )


def _is_partial_key(key: PurePosixPath) -> bool:
    if len(key.parts) != 4 or key.parts[:2] != (".partial", "v1"):
        return False
    shard = key.parts[2]
    matched = _PARTIAL_NAME_PATTERN.fullmatch(key.parts[3])
    if (
        matched is None
        or len(shard) != 2
        or any(character not in "0123456789abcdef" for character in shard)
    ):
        return False
    try:
        locator_uuid = UUID(matched.group(1))
    except ValueError:
        return False
    return locator_uuid.hex[:2] == shard


def _ensure_directory(root: Path, target: Path) -> None:
    try:
        parts = target.relative_to(root).parts
    except ValueError:
        raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.WRITE_FAILED) from None
    current = root
    for part in parts:
        current /= part
        with suppress(FileExistsError):
            current.mkdir(mode=0o700)
        try:
            assert_safe_local_path(root, current)
        except ArtifactStorageError:
            raise VerifiedPayloadStagingError(
                VerifiedPayloadStagingErrorCode.WRITE_FAILED
            ) from None
        if not current.is_dir():
            raise VerifiedPayloadStagingError(VerifiedPayloadStagingErrorCode.WRITE_FAILED)


def _unlink_if_identity_matches(path: Path, identity: tuple[int, int]) -> bool:
    try:
        payload_stat = path.stat(follow_symlinks=False)
        if (
            stat.S_ISREG(payload_stat.st_mode)
            and (
                payload_stat.st_dev,
                payload_stat.st_ino,
            )
            == identity
        ):
            path.unlink()
            return True
    except OSError:
        pass
    return False


def _paths_overlap(left: Path, right: Path) -> bool:
    try:
        left.relative_to(right)
        return True
    except ValueError:
        pass
    try:
        right.relative_to(left)
        return True
    except ValueError:
        return False


def _sync_directory(path: Path) -> None:
    if os.name == "nt":
        return
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except OSError:
        pass
