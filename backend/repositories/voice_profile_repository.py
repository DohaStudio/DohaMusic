"""Voice profile persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.voice_enrollment_status import (
    VoiceSampleSourceType,
    VoiceSampleStatus,
)
from backend.models.pipeline_job import PipelineJob
from backend.models.voice_conversion_job import VoiceConversionJob
from backend.models.voice_profile import VoiceProfile
from backend.models.voice_sample import VoiceSample
from backend.schemas.voice_profile import VoiceProfileCreate


class VoiceProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        request: VoiceProfileCreate | None = None,
        *,
        create_compatibility_sample: bool = True,
        commit: bool = True,
        **values: object,
    ) -> VoiceProfile:
        profile = VoiceProfile(**(request.model_dump() if request else values))
        self.session.add(profile)
        self.session.flush()
        if create_compatibility_sample:
            sample = VoiceSample(
                voice_profile_id=profile.id,
                source_type=(
                    VoiceSampleSourceType.FILE_UPLOAD.value
                    if profile.display_filename
                    else VoiceSampleSourceType.LEGACY_REFERENCE.value
                ),
                category="legacy",
                status=(
                    VoiceSampleStatus.PROMOTED.value
                    if profile.status == "READY"
                    else VoiceSampleStatus.FAILED.value
                ),
                normalized_content_type=profile.mime_type,
                normalized_size_bytes=profile.size_bytes,
                normalized_storage_path=profile.reference_file_path,
                duration_seconds=profile.duration_seconds,
                sample_rate=profile.sample_rate,
                channels=profile.channels,
                quality_warnings=profile.quality_warnings,
            )
            self.session.add(sample)
            self.session.flush()
            if sample.status == VoiceSampleStatus.PROMOTED.value:
                profile.active_reference_sample_id = sample.id
        if commit:
            self.session.commit()
        self.session.refresh(profile)
        return profile

    def get(self, profile_id: str) -> VoiceProfile | None:
        return self.session.get(VoiceProfile, profile_id)

    def list(self, *, limit: int, offset: int) -> list[VoiceProfile]:
        statement = (
            select(VoiceProfile)
            .order_by(VoiceProfile.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.session.scalars(statement))

    def is_in_use(self, profile_id: str) -> bool:
        pipeline = self.session.scalar(
            select(PipelineJob.id)
            .where(PipelineJob.voice_profile_id == profile_id)
            .limit(1)
        )
        conversion = self.session.scalar(
            select(VoiceConversionJob.id)
            .where(VoiceConversionJob.voice_profile_id == profile_id)
            .limit(1)
        )
        return pipeline is not None or conversion is not None

    def delete(self, profile: VoiceProfile, *, commit: bool = True) -> None:
        if profile.source_enrollment is not None:
            profile.source_enrollment.voice_profile_id = None
        profile.active_reference_sample_id = None
        self.session.flush()
        for sample in list(profile.samples):
            self.session.delete(sample)
        self.session.flush()
        self.session.delete(profile)
        if commit:
            self.session.commit()
        else:
            self.session.flush()

    def set_active_reference(
        self,
        profile: VoiceProfile,
        sample: VoiceSample,
        *,
        commit: bool = True,
    ) -> VoiceProfile:
        if sample.voice_profile_id != profile.id:
            raise ValueError("Active reference sample must belong to the voice profile")
        if sample.status != VoiceSampleStatus.PROMOTED.value:
            raise ValueError("Active reference sample must be promoted")
        profile.active_reference_sample_id = sample.id
        self.session.flush()
        if commit:
            self.session.commit()
        self.session.refresh(profile)
        return profile
