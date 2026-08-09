"""Artifact Payload의 streaming SHA-256·크기 검증 helper."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import BinaryIO

INTEGRITY_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True, slots=True)
class ArtifactIntegrity:
    checksum: str
    size_bytes: int


def calculate_artifact_integrity(stream: BinaryIO) -> ArtifactIntegrity:
    """현재 stream 위치부터 EOF까지 메모리 적재 없이 무결성을 계산한다."""

    digest = hashlib.sha256()
    size_bytes = 0
    while chunk := stream.read(INTEGRITY_CHUNK_SIZE):
        digest.update(chunk)
        size_bytes += len(chunk)
    return ArtifactIntegrity(checksum=digest.hexdigest(), size_bytes=size_bytes)
