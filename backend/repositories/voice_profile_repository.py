"""Voice profile persistence operations."""

from sqlalchemy.orm import Session

from backend.models.voice_profile import VoiceProfile
from backend.schemas.voice_profile import VoiceProfileCreate


class VoiceProfileRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, request: VoiceProfileCreate) -> VoiceProfile:
        profile = VoiceProfile(**request.model_dump())
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile

    def get(self, profile_id: str) -> VoiceProfile | None:
        return self.session.get(VoiceProfile, profile_id)

    def delete(self, profile: VoiceProfile) -> None:
        self.session.delete(profile)
        self.session.commit()
