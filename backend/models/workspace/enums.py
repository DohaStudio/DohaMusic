"""공통 명세에서 값이 확정된 Workspace Entity Enum."""

from enum import StrEnum


class AssetType(StrEnum):
    LYRICS = "lyrics"
    MUSIC = "music"
    VOCAL = "vocal"
    STEM = "stem"
    RECORDING = "recording"
    MIX = "mix"
    EXPORT = "export"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
