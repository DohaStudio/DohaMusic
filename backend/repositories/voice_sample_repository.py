"""Persistence operations for Guided Voice Enrollment samples."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from backend.core.voice_enrollment_status import (
    VoiceSampleStatus,
    validate_sample_transition,
)
from backend.models.voice_profile import VoiceProfile
from backend.models.voice_sample import VoiceSample


class VoiceSampleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, commit: bool = True, **values: object) -> VoiceSample:
        sample = VoiceSample(**values)
        self.session.add(sample)
        self.session.flush()
        if commit:
            self.session.commit()
        self.session.refresh(sample)
        return sample

    def get(self, sample_id: str) -> VoiceSample | None:
        return self.session.get(VoiceSample, sample_id)

    def list_by_enrollment(self, enrollment_id: str) -> list[VoiceSample]:
        statement = (
            select(VoiceSample)
            .where(VoiceSample.enrollment_id == enrollment_id)
            .order_by(VoiceSample.created_at, VoiceSample.id)
        )
        return list(self.session.scalars(statement))

    def list_by_profile(self, profile_id: str) -> list[VoiceSample]:
        statement = (
            select(VoiceSample)
            .where(VoiceSample.voice_profile_id == profile_id)
            .order_by(VoiceSample.created_at, VoiceSample.id)
        )
        return list(self.session.scalars(statement))

    def count_active_by_enrollment(self, enrollment_id: str) -> int:
        return int(
            self.session.scalar(
                select(func.count(VoiceSample.id)).where(
                    VoiceSample.enrollment_id == enrollment_id,
                    VoiceSample.status != VoiceSampleStatus.DELETED.value,
                )
            )
            or 0
        )

    def transition(
        self,
        sample: VoiceSample,
        target: VoiceSampleStatus,
        *,
        commit: bool = True,
    ) -> VoiceSample:
        current = VoiceSampleStatus(sample.status)
        validate_sample_transition(current, target)
        now = datetime.now(UTC)
        sample.status = target.value
        if target == VoiceSampleStatus.READY:
            sample.validated_at = now
        elif target == VoiceSampleStatus.PROMOTED:
            sample.promoted_at = now
        elif target == VoiceSampleStatus.DELETED:
            sample.deleted_at = now
        self.session.flush()
        if commit:
            self.session.commit()
        self.session.refresh(sample)
        return sample

    def promote(
        self,
        sample: VoiceSample,
        profile: VoiceProfile,
        *,
        commit: bool = True,
    ) -> VoiceSample:
        if sample.enrollment_id is None:
            raise ValueError("Only enrollment samples can be promoted")
        if sample.status != VoiceSampleStatus.READY.value:
            raise ValueError("Only ready samples can be promoted")
        sample.voice_profile_id = profile.id
        return self.transition(sample, VoiceSampleStatus.PROMOTED, commit=commit)

    def list_cleanup_pending(
        self,
        *,
        retry_before: datetime | None = None,
        limit: int = 100,
    ) -> list[VoiceSample]:
        retry_cutoff = retry_before or datetime.max.replace(tzinfo=UTC)
        statement = (
            select(VoiceSample)
            .where(
                or_(
                    VoiceSample.status == VoiceSampleStatus.DELETE_PENDING.value,
                    and_(
                        VoiceSample.status == VoiceSampleStatus.DELETE_FAILED.value,
                        VoiceSample.updated_at <= retry_cutoff,
                    ),
                )
            )
            .order_by(VoiceSample.updated_at)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_interrupted(self, *, limit: int = 100) -> list[VoiceSample]:
        statement = (
            select(VoiceSample)
            .where(
                VoiceSample.status.in_(
                    [
                        VoiceSampleStatus.UPLOADED.value,
                        VoiceSampleStatus.VALIDATING.value,
                    ]
                )
            )
            .order_by(VoiceSample.updated_at)
            .limit(limit)
        )
        return list(self.session.scalars(statement))

    def list_all_managed(self) -> list[VoiceSample]:
        return list(self.session.scalars(select(VoiceSample)))
