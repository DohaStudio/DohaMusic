"""Voice profile use cases with mandatory consent."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.models.voice_profile import VoiceProfile
from backend.repositories.voice_profile_repository import VoiceProfileRepository
from backend.schemas.voice_profile import VoiceProfileCreate


class VoiceProfileService:
    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self.session_factory = session_factory

    def create(self, request: VoiceProfileCreate) -> VoiceProfile:
        with self.session_factory() as session:
            profile = VoiceProfileRepository(session).create(request)
            session.expunge(profile)
            return profile

    def delete(self, profile_id: str) -> None:
        with self.session_factory() as session:
            repository = VoiceProfileRepository(session)
            profile = repository.get(profile_id)
            if profile is None:
                raise ResourceNotFoundError("음성 프로필")
            repository.delete(profile)
