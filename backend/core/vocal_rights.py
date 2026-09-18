"""ADR-075 persistence vocabulary (not an authorization API)."""

from enum import StrEnum


class VocalRightsSubjectType(StrEnum):
    WORKSPACE = "WORKSPACE"
    ASSET_VERSION = "ASSET_VERSION"
    ARTIFACT = "ARTIFACT"


class VocalRightsOperation(StrEnum):
    VOCAL_GENERATE = "VOCAL_GENERATE"
    VOCAL_TRANSFORM = "VOCAL_TRANSFORM"
    VOCAL_CORRECT = "VOCAL_CORRECT"
    VOCAL_ANALYZE = "VOCAL_ANALYZE"
    OUTPUT_READ = "OUTPUT_READ"


class VocalRightsUsageRole(StrEnum):
    CREATE_OUTPUT = "CREATE_OUTPUT"
    LYRICS_REFERENCE = "LYRICS_REFERENCE"
    MELODY_REFERENCE = "MELODY_REFERENCE"
    TIMING_REFERENCE = "TIMING_REFERENCE"
    VOICE_REFERENCE = "VOICE_REFERENCE"
    SOURCE_VOCAL = "SOURCE_VOCAL"
    PARENT_VOCAL = "PARENT_VOCAL"
    OUTPUT = "OUTPUT"


class VocalRightsTransition(StrEnum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class VocalRightsGrantState(StrEnum):
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"
    SUPERSEDED = "SUPERSEDED"


class VocalRightsPersistenceError(Exception):
    """Safe persistence conflict; no database/evidence detail is exposed."""

    def __init__(self, code: str = "AUTHORITY_CONFLICT") -> None:
        self.code = code
        super().__init__(code)
