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
        validated_request = request.model_copy(update={"reference_file_path": safe_path})
        with self.session_factory() as session:
            profile = VoiceProfileRepository(session).create(validated_request)
            session.expunge(profile)
            return profile

    def _validate_reference_path(self, value: str) -> str:
        requested = Path(value)
        if requested.is_absolute() or requested.suffix.lower() not in ALLOWED_VOICE_EXTENSIONS:
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
                raise AppError("VOICE_PROFILE_NOT_FOUND", "음성 프로필을 찾을 수 없습니다.", 404)
            if repository.is_in_use(profile_id):
                raise AppError(
                    "VOICE_PROFILE_IN_USE",
                    "음악 작업에서 사용 중인 음성 프로필은 삭제할 수 없습니다.",
                    409,
                )
            managed_files = self._managed_upload_paths(profile)
            tombstones = [path.with_suffix(".deleting") for path in managed_files]
            try:
                for managed_file, tombstone in zip(managed_files, tombstones, strict=True):
                    managed_file.replace(tombstone)
                repository.delete(profile, commit=False)
                for tombstone in tombstones:
                    tombstone.unlink()
                    self._remove_empty_voice_reference_parents(tombstone.parent)
                session.commit()
            except OSError:
                session.rollback()
                for managed_file, tombstone in zip(managed_files, tombstones, strict=True):
                    if tombstone.exists():
                        managed_file.parent.mkdir(parents=True, exist_ok=True)
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
                raise AppError("VOICE_PROFILE_NOT_FOUND", "음성 프로필을 찾을 수 없습니다.", 404)
            session.expunge(profile)
            return profile

    def _managed_upload_paths(self, profile: VoiceProfile) -> list[Path]:
        paths = [
            path
            for sample in profile.samples
            if (
                path := self._managed_reference_path(
                    sample.normalized_storage_path,
                    expected=(
                        Path("voices/references")
                        / profile.id
                        / "samples"
                        / sample.id
                        / "reference.wav"
                    ),
                )
            )
            is not None
        ]
        legacy_path = self._legacy_managed_upload_path(profile)
        if legacy_path is not None and legacy_path not in paths:
            paths.append(legacy_path)
        return paths

    def _legacy_managed_upload_path(self, profile: VoiceProfile) -> Path | None:
        expected = Path("voices/references") / profile.id / "reference.wav"
        if Path(profile.reference_file_path) != expected:
            return None
        return self._managed_reference_path(profile.reference_file_path, expected=expected)

    def _managed_reference_path(self, value: str | None, *, expected: Path) -> Path | None:
        if value is None or Path(value) != expected:
            return None
        try:
            path = self.storage.resolve_voice_reference(value)
        except ValueError:
            raise AppError(
                "VOICE_STORAGE_DELETE_FAILED",
                "음성 파일 경계를 확인하지 못했습니다.",
                500,
            ) from None
        return path if path.exists() and path.is_file() and not path.is_symlink() else None

    def _remove_empty_voice_reference_parents(self, path: Path) -> None:
        root = self.storage.voice_references_dir.resolve()
        current = path
        while current != root and current.is_relative_to(root):
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
