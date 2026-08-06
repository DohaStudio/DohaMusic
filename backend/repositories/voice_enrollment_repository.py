"""Persistence operations for Guided Voice Enrollment sessions."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from backend.core.voice_enrollment_status import (
    VoiceCleanupStatus,
    VoiceEnrollmentStatus,
    validate_enrollment_transition,
)
from backend.models.voice_enrollment import VoiceEnrollment


class VoiceEnrollmentRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, commit: bool = True, **values: object) -> VoiceEnrollment:
        enrollment = VoiceEnrollment(**values)
        self.session.add(enrollment)
        self.session.flush()
        if commit:
            self.session.commit()
        self.session.refresh(enrollment)
        return enrollment

    def get(self, enrollment_id: str) -> VoiceEnrollment | None:
        return self.session.get(VoiceEnrollment, enrollment_id)

    def transition(
        self,
        enrollment: VoiceEnrollment,
        target: VoiceEnrollmentStatus,
        *,
        commit: bool = True,
    ) -> VoiceEnrollment:
        current = VoiceEnrollmentStatus(enrollment.status)
        validate_enrollment_transition(current, target)
        now = datetime.now(UTC)
        enrollment.status = target.value
        enrollment.last_activity_at = now
        if target == VoiceEnrollmentStatus.SUBMITTING:
            enrollment.submitted_at = now
        elif target == VoiceEnrollmentStatus.COMPLETED:
            enrollment.completed_at = now
        elif target == VoiceEnrollmentStatus.CANCELLED:
            enrollment.cancelled_at = now
        self.session.flush()
        if commit:
            self.session.commit()
        self.session.refresh(enrollment)
        return enrollment

    def list_expired(self, *, now: datetime, limit: int = 100) -> list[VoiceEnrollment]:
        statement = (
            select(VoiceEnrollment)
            .where(
                or_(
                    and_(
                        VoiceEnrollment.expires_at.is_not(None),
                        VoiceEnrollment.expires_at <= now,
                    ),
                    and_(
                        VoiceEnrollment.absolute_expires_at.is_not(None),
                        VoiceEnrollment.absolute_expires_at <= now,
                    ),
                ),
                VoiceEnrollment.status.in_(
                    [
                        VoiceEnrollmentStatus.DRAFT.value,
                        VoiceEnrollmentStatus.READY_TO_SUBMIT.value,
                    ]
                ),
            )
            .order_by(VoiceEnrollment.expires_at)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_cleanup_pending(
        self,
        *,
        retry_before: datetime | None = None,
        limit: int = 100,
    ) -> list[VoiceEnrollment]:
        retry_cutoff = retry_before or datetime.max.replace(tzinfo=UTC)
        statement = (
            select(VoiceEnrollment)
            .where(
                or_(
                    VoiceEnrollment.cleanup_status == VoiceCleanupStatus.PENDING.value,
                    VoiceEnrollment.status
                    == VoiceEnrollmentStatus.DELETE_PENDING.value,
                    and_(
                        or_(
                            VoiceEnrollment.cleanup_status
                            == VoiceCleanupStatus.FAILED.value,
                            VoiceEnrollment.status
                            == VoiceEnrollmentStatus.DELETE_FAILED.value,
                        ),
                        VoiceEnrollment.updated_at <= retry_cutoff,
                    ),
                )
            )
            .order_by(VoiceEnrollment.updated_at)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_interrupted_submissions(
        self, *, limit: int = 100
    ) -> list[VoiceEnrollment]:
        statement = (
            select(VoiceEnrollment)
            .where(VoiceEnrollment.status == VoiceEnrollmentStatus.SUBMITTING.value)
            .order_by(VoiceEnrollment.updated_at)
            .limit(limit)
        )
        return list(self.session.scalars(statement))
