from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from backend.contracts.music_director import MusicIntent


class MusicDirectorProviderStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class MusicDirectorProviderRequest:
    client_execution_key: str
    source_snapshot_id: UUID
    intent: MusicIntent
    model_id: str | None = None


@dataclass(frozen=True, slots=True)
class MusicDirectorProviderSubmission:
    external_execution_id: str


@dataclass(frozen=True, slots=True)
class MusicDirectorProviderCandidate:
    ordinal: int
    proposal: object


@dataclass(frozen=True, slots=True)
class MusicDirectorProviderResult:
    external_execution_id: str
    candidates: tuple[MusicDirectorProviderCandidate, ...]


class MusicDirectorProvider(Protocol):
    provider_id: str

    def submit(self, request: MusicDirectorProviderRequest) -> MusicDirectorProviderSubmission: ...

    def read_status(self, external_execution_id: str) -> MusicDirectorProviderStatus: ...

    def read_result(self, external_execution_id: str) -> MusicDirectorProviderResult: ...

    def cancel(self, external_execution_id: str) -> MusicDirectorProviderStatus: ...
