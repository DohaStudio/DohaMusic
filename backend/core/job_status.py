"""Backend Foundation job states and legal transitions."""

from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    GENERATING = "GENERATING"
    STEM_SEPARATING = "STEM_SEPARATING"
    VOICE_CONVERTING = "VOICE_CONVERTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.VALIDATING, JobStatus.FAILED},
    JobStatus.VALIDATING: {
        JobStatus.GENERATING,
        JobStatus.STEM_SEPARATING,
        JobStatus.VOICE_CONVERTING,
        JobStatus.FAILED,
    },
    JobStatus.GENERATING: {
        JobStatus.STEM_SEPARATING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
    },
    JobStatus.STEM_SEPARATING: {
        JobStatus.VOICE_CONVERTING,
        JobStatus.COMPLETED,
        JobStatus.FAILED,
    },
    JobStatus.VOICE_CONVERTING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}
