"""Voice profile persistence operations."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.pipeline_job import PipelineJob
from backend.models.voice_conversion_job import VoiceConversionJob
from backend.models.voice_profile import VoiceProfile
from backend.schemas.voice_profile import VoiceProfileCreate


class VoiceProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self, request: VoiceProfileCreate | None = None, **values: object
    ) -> VoiceProfile:
        profile = VoiceProfile(**(request.model_dump() if request else values))
        self.session.add(profile)
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

    def delete(self, profile: VoiceProfile) -> None:
        self.session.delete(profile)
        self.session.commit()
