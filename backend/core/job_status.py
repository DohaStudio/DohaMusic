"""Backend Foundation job states and legal transitions."""

from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "PENDING"
    VALIDATING = "VALIDATING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


ALLOWED_TRANSITIONS: dict[JobStatus, set[JobStatus]] = {
    JobStatus.PENDING: {JobStatus.VALIDATING, JobStatus.FAILED},
    JobStatus.VALIDATING: {JobStatus.GENERATING, JobStatus.FAILED},
    JobStatus.GENERATING: {JobStatus.COMPLETED, JobStatus.FAILED},
    JobStatus.COMPLETED: set(),
    JobStatus.FAILED: set(),
}
