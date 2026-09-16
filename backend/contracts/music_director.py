from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import StrEnum


class MusicDirectorAction(StrEnum):
    GENERATE_VARIATION = "generate_variation"


class TimelineSelectionScope(StrEnum):
    COMPOSITION = "composition"


@dataclass(frozen=True, slots=True)
class TimelineSelection:
    scope: TimelineSelectionScope = TimelineSelectionScope.COMPOSITION


@dataclass(frozen=True, slots=True)
class MusicIntent:
    instruction: str
    candidate_count: int = 2
    action: MusicDirectorAction = MusicDirectorAction.GENERATE_VARIATION
    selection: TimelineSelection = TimelineSelection()

    def __post_init__(self) -> None:
        instruction = self.instruction.strip()
        if not instruction or len(instruction) > 2000:
            raise ValueError("instruction must contain between 1 and 2000 characters")
        if not 1 <= self.candidate_count <= 4:
            raise ValueError("candidate_count must be between 1 and 4")
        object.__setattr__(self, "instruction", instruction)

    def request_fingerprint(self) -> str:
        encoded = json.dumps(asdict(self), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
