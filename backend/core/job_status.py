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
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {
        JobStatus.VALIDATING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.VALIDATING: {
        JobStatus.GENERATING,
        JobStatus.STEM_SEPARATING,
        JobStatus.VOICE_CONVERTING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.GENERATING: {
        JobStatus.STEM_SEPARATING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.STEM_SEPARATING: {
        JobStatus.VOICE_CONVERTING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.VOICE_CONVERTING: {
        JobStatus.MIXING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.MIXING: {
        JobStatus.EXPORTING,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.EXPORTING: {
        JobStatus.COMPLETED,
        JobStatus.FAILED,
        JobStatus.CANCELLED,
        JobStatus.CANCEL_REQUESTED,
    },
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
    JobStatus.CANCEL_REQUESTED: {JobStatus.CANCELLED},
    JobStatus.CANCELLED: set(),
}
