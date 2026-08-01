"""Voice profile use cases with mandatory consent."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from backend.core.exceptions import AppError, InvalidVoiceReferenceError
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
                raise AppError(
                    "VOICE_PROFILE_NOT_FOUND", "음성 프로필을 찾을 수 없습니다.", 404
                )
            if repository.is_in_use(profile_id):
                raise AppError(
                    "VOICE_PROFILE_IN_USE",
                    "음악 작업에서 사용 중인 음성 프로필은 삭제할 수 없습니다.",
                    409,
                )
            managed_file = self._managed_upload_path(profile)
            tombstone = managed_file.with_suffix(".deleting") if managed_file else None
            try:
                if managed_file is not None:
                    managed_file.replace(tombstone)
                repository.delete(profile, commit=False)
                if tombstone is not None:
                    tombstone.unlink()
                    tombstone.parent.rmdir()
                session.commit()
            except OSError:
                session.rollback()
                if tombstone is not None and tombstone.exists():
                    tombstone.replace(managed_file)
                raise AppError(
                    "VOICE_STORAGE_DELETE_FAILED",
                    "음성 파일을 안전하게 삭제하지 못했습니다.",
                    500,
                ) from None

    def list(self, *, limit: int, offset: int) -> list[VoiceProfile]:
        with self.session_factory() as session:
            profiles = VoiceProfileRepository(session).list(limit=limit, offset=offset)
            for profile in profiles:
                session.expunge(profile)
            return profiles

    def get(self, profile_id: str) -> VoiceProfile:
        with self.session_factory() as session:
            profile = VoiceProfileRepository(session).get(profile_id)
            if profile is None:
                raise AppError(
                    "VOICE_PROFILE_NOT_FOUND", "음성 프로필을 찾을 수 없습니다.", 404
                )
            session.expunge(profile)
            return profile

    def _managed_upload_path(self, profile: VoiceProfile) -> Path | None:
        expected = Path("voices/references") / profile.id / "reference.wav"
        if Path(profile.reference_file_path) != expected:
            return None
        try:
            path = self.storage.resolve_voice_reference(profile.reference_file_path)
        except ValueError:
            raise AppError(
                "VOICE_STORAGE_DELETE_FAILED",
                "음성 파일 경계를 확인하지 못했습니다.",
                500,
            ) from None
        return (
            path if path.exists() and path.is_file() and not path.is_symlink() else None
        )
