"""Clip Service가 소비하는 trusted Artifact media metadata authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from backend.models.workspace import Artifact


class TrustedMediaMetadataErrorCode(StrEnum):
    SOURCE_ARTIFACT_NOT_FOUND = "SOURCE_ARTIFACT_NOT_FOUND"
    SOURCE_ARTIFACT_AMBIGUOUS = "SOURCE_ARTIFACT_AMBIGUOUS"
    SOURCE_DURATION_UNAVAILABLE = "SOURCE_DURATION_UNAVAILABLE"


_SAFE_MESSAGES = {
    TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_NOT_FOUND: (
        "Clip source Artifact is unavailable."
    ),
    TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_AMBIGUOUS: ("Clip source Artifact is ambiguous."),
    TrustedMediaMetadataErrorCode.SOURCE_DURATION_UNAVAILABLE: (
        "Clip source duration is unavailable."
    ),
}


class TrustedMediaMetadataError(RuntimeError):
    def __init__(self, code: TrustedMediaMetadataErrorCode) -> None:
        super().__init__(_SAFE_MESSAGES[code])
        self.code = code


@dataclass(frozen=True, slots=True)
class TrustedClipSourceMetadata:
    asset_version_id: UUID
    artifact_id: UUID
    media_type: str
    duration_us: int


class ClipSourceArtifactReader(Protocol):
    def list_clip_source_artifact_candidates(self, asset_version_id: UUID) -> list[Artifact]: ...


class TrustedMediaMetadataService:
    """Exactly-one trusted Artifact의 persisted duration만 반환한다."""

    def __init__(self, repository: ClipSourceArtifactReader) -> None:
        self._repository = repository

    def resolve_clip_source(self, asset_version_id: UUID) -> TrustedClipSourceMetadata:
        candidates = self._repository.list_clip_source_artifact_candidates(asset_version_id)
        if not candidates:
            raise TrustedMediaMetadataError(TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_NOT_FOUND)
        if len(candidates) != 1:
            raise TrustedMediaMetadataError(TrustedMediaMetadataErrorCode.SOURCE_ARTIFACT_AMBIGUOUS)
        artifact = candidates[0]
        if artifact.duration_us is None or artifact.duration_us < 1:
            raise TrustedMediaMetadataError(
                TrustedMediaMetadataErrorCode.SOURCE_DURATION_UNAVAILABLE
            )
        return TrustedClipSourceMetadata(
            asset_version_id=asset_version_id,
            artifact_id=artifact.artifact_id,
            media_type=artifact.media_type,
            duration_us=artifact.duration_us,
        )
