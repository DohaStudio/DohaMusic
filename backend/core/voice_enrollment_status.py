"""Persistent Voice Enrollment states and legal lifecycle transitions."""

from enum import StrEnum


class VoiceEnrollmentStatus(StrEnum):
    DRAFT = "DRAFT"
    READY_TO_SUBMIT = "READY_TO_SUBMIT"
    SUBMITTING = "SUBMITTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    DELETE_PENDING = "DELETE_PENDING"
    DELETE_FAILED = "DELETE_FAILED"


class VoiceSampleStatus(StrEnum):
    UPLOADED = "UPLOADED"
    VALIDATING = "VALIDATING"
    READY = "READY"
    FAILED = "FAILED"
    PROMOTED = "PROMOTED"
    DELETE_PENDING = "DELETE_PENDING"
    DELETE_FAILED = "DELETE_FAILED"
    DELETED = "DELETED"


class VoiceSampleSourceType(StrEnum):
    BROWSER_RECORDING = "BROWSER_RECORDING"
    FILE_UPLOAD = "FILE_UPLOAD"
    LEGACY_REFERENCE = "LEGACY_REFERENCE"


class VoiceQualityStatus(StrEnum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"


class VoiceCleanupStatus(StrEnum):
    NOT_REQUESTED = "NOT_REQUESTED"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


ENROLLMENT_TRANSITIONS: dict[VoiceEnrollmentStatus, set[VoiceEnrollmentStatus]] = {
    VoiceEnrollmentStatus.DRAFT: {
        VoiceEnrollmentStatus.READY_TO_SUBMIT,
        VoiceEnrollmentStatus.FAILED,
        VoiceEnrollmentStatus.CANCELLED,
        VoiceEnrollmentStatus.EXPIRED,
        VoiceEnrollmentStatus.DELETE_PENDING,
    },
    VoiceEnrollmentStatus.READY_TO_SUBMIT: {
        VoiceEnrollmentStatus.DRAFT,
        VoiceEnrollmentStatus.SUBMITTING,
        VoiceEnrollmentStatus.CANCELLED,
        VoiceEnrollmentStatus.EXPIRED,
        VoiceEnrollmentStatus.DELETE_PENDING,
    },
    VoiceEnrollmentStatus.SUBMITTING: {
        VoiceEnrollmentStatus.READY_TO_SUBMIT,
        VoiceEnrollmentStatus.COMPLETED,
        VoiceEnrollmentStatus.FAILED,
        VoiceEnrollmentStatus.DELETE_PENDING,
    },
    VoiceEnrollmentStatus.COMPLETED: set(),
    VoiceEnrollmentStatus.FAILED: {
        VoiceEnrollmentStatus.DRAFT,
        VoiceEnrollmentStatus.DELETE_PENDING,
    },
    VoiceEnrollmentStatus.CANCELLED: {VoiceEnrollmentStatus.DELETE_PENDING},
    VoiceEnrollmentStatus.EXPIRED: {VoiceEnrollmentStatus.DELETE_PENDING},
    VoiceEnrollmentStatus.DELETE_PENDING: {VoiceEnrollmentStatus.DELETE_FAILED},
    VoiceEnrollmentStatus.DELETE_FAILED: {VoiceEnrollmentStatus.DELETE_PENDING},
}


SAMPLE_TRANSITIONS: dict[VoiceSampleStatus, set[VoiceSampleStatus]] = {
    VoiceSampleStatus.UPLOADED: {
        VoiceSampleStatus.VALIDATING,
        VoiceSampleStatus.FAILED,
        VoiceSampleStatus.DELETE_PENDING,
    },
    VoiceSampleStatus.VALIDATING: {
        VoiceSampleStatus.READY,
        VoiceSampleStatus.FAILED,
        VoiceSampleStatus.DELETE_PENDING,
    },
    VoiceSampleStatus.READY: {
        VoiceSampleStatus.PROMOTED,
        VoiceSampleStatus.DELETE_PENDING,
    },
    VoiceSampleStatus.FAILED: {VoiceSampleStatus.DELETE_PENDING},
    VoiceSampleStatus.PROMOTED: {VoiceSampleStatus.DELETE_PENDING},
    VoiceSampleStatus.DELETE_PENDING: {
        VoiceSampleStatus.DELETE_FAILED,
        VoiceSampleStatus.DELETED,
    },
    VoiceSampleStatus.DELETE_FAILED: {VoiceSampleStatus.DELETE_PENDING},
    VoiceSampleStatus.DELETED: set(),
}


def validate_enrollment_transition(
    current: VoiceEnrollmentStatus, target: VoiceEnrollmentStatus
) -> None:
    if target != current and target not in ENROLLMENT_TRANSITIONS[current]:
        raise ValueError(
            f"Invalid voice enrollment transition: {current.value} -> {target.value}"
        )


def validate_sample_transition(
    current: VoiceSampleStatus, target: VoiceSampleStatus
) -> None:
    if target != current and target not in SAMPLE_TRANSITIONS[current]:
        raise ValueError(
            f"Invalid voice sample transition: {current.value} -> {target.value}"
        )
