"""Voice profile use cases with mandatory consent."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from backend.core.exceptions import InvalidVoiceReferenceError, ResourceNotFoundError
from backend.models.voice_profile import VoiceProfile
from backend.repositories.voice_profile_repository import VoiceProfileRepository
from backend.schemas.voice_profile import VoiceProfileCreate
from backend.storage.service import StorageService

ALLOWED_VOICE_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}


class VoiceProfileService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        storage: StorageService,
    ) -> None:
        self.session_factory = session_factory
        self.storage = storage

    def create(self, request: VoiceProfileCreate) -> VoiceProfile:
        safe_path = self._validate_reference_path(request.reference_file_path)
        validated_request = request.model_copy(
            update={"reference_file_path": safe_path}
        )
        with self.session_factory() as session:
            profile = VoiceProfileRepository(session).create(validated_request)
            session.expunge(profile)
            return profile

    def _validate_reference_path(self, value: str) -> str:
        requested = Path(value)
        if (
            requested.is_absolute()
            or requested.suffix.lower() not in ALLOWED_VOICE_EXTENSIONS
        ):
            raise InvalidVoiceReferenceError()
        candidate = self.storage.root / requested
        if not candidate.exists() or not candidate.is_file():
            raise InvalidVoiceReferenceError()
        current = candidate
        while current != self.storage.root:
            if current.is_symlink():
                raise InvalidVoiceReferenceError()
            current = current.parent
        try:
            resolved = candidate.resolve(strict=True)
            allowed_root = self.storage.voice_references_dir.resolve(strict=True)
            relative = resolved.relative_to(allowed_root)
        except (OSError, ValueError):
            raise InvalidVoiceReferenceError() from None
        return (Path("voices/references") / relative).as_posix()

    def delete(self, profile_id: str) -> None:
        with self.session_factory() as session:
            repository = VoiceProfileRepository(session)
            profile = repository.get(profile_id)
            if profile is None:
                raise ResourceNotFoundError("음성 프로필")
            repository.delete(profile)
