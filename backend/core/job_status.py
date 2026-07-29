"""Backend job states and legal transitions."""

from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    GENERATING = "GENERATING"
    STEM_SEPARATING = "STEM_SEPARATING"
    VOICE_CONVERTING = "VOICE_CONVERTING"
    MIXING = "MIXING"
    EXPORTING = "EXPORTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {
        JobStatus.VALIDATING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.VALIDATING: {
        JobStatus.GENERATING,
        JobStatus.STEM_SEPARATING,
        JobStatus.VOICE_CONVERTING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.GENERATING: {
        JobStatus.STEM_SEPARATING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.STEM_SEPARATING: {
        JobStatus.VOICE_CONVERTING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.VOICE_CONVERTING: {
        JobStatus.MIXING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.MIXING: {
        JobStatus.EXPORTING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.EXPORTING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
    },
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCELLED: set(),
}
