"""Traversal-resistant temporary and promoted Voice Enrollment storage."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from backend.storage.service import StorageService
from backend.voice_enrollment.contracts import VoiceContainer


@dataclass(frozen=True, slots=True)
class EnrollmentSamplePaths:
    directory: Path
    original: Path
    normalized: Path


class VoiceEnrollmentStorage:
    def __init__(self, storage: StorageService) -> None:
        self.storage = storage

    def sample_paths(
        self,
        enrollment_id: str,
        sample_id: str,
        container: VoiceContainer,
    ) -> EnrollmentSamplePaths:
        self._validate_uuid(enrollment_id)
        self._validate_uuid(sample_id)
        directory = (
            self.storage.voice_enrollments_dir / enrollment_id / "samples" / sample_id
        ).resolve()
        self._require_within(directory, self.storage.voice_enrollments_dir)
        return EnrollmentSamplePaths(
            directory=directory,
            original=directory / f"original.{container.value}",
            normalized=directory / "normalized.wav",
        )

    def create_sample_directory(self, paths: EnrollmentSamplePaths) -> None:
        parent = paths.directory.parent
        parent.mkdir(parents=True, exist_ok=True)
        self._reject_symlink_chain(parent, self.storage.voice_enrollments_dir)
        paths.directory.mkdir(exist_ok=False)

    def promoted_path(self, profile_id: str, sample_id: str) -> Path:
        self._validate_uuid(profile_id)
        self._validate_uuid(sample_id)
        result = (
            self.storage.voice_references_dir / profile_id / "samples" / sample_id / "reference.wav"
        ).resolve()
        self._require_within(result, self.storage.voice_references_dir)
        return result

    def promote(self, source: Path, destination: Path) -> None:
        self._require_within(source.resolve(), self.storage.voice_enrollments_dir)
        self._require_within(destination.resolve(), self.storage.voice_references_dir)
        if source.is_symlink():
            raise OSError("Refusing to promote a symlinked voice file")
        self._reject_symlink_chain(source.parent, self.storage.voice_enrollments_dir)
        destination.parent.mkdir(parents=True, exist_ok=False)
        if destination.exists():
            raise FileExistsError("Promoted sample already exists")
        source.replace(destination)

    def restore_promotion(self, destination: Path, source: Path) -> None:
        if not destination.exists():
            return
        source.parent.mkdir(parents=True, exist_ok=True)
        destination.replace(source)
        self._remove_empty_parents(destination.parent, self.storage.voice_references_dir)

    def delete_file(self, relative_path: str | None) -> None:
        if relative_path is None:
            return
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Voice file path is not a safe relative path")
        path = self.storage.root / relative
        if not (
            path.is_relative_to(self.storage.voice_enrollments_dir)
            or path.is_relative_to(self.storage.voice_references_dir)
        ):
            raise ValueError("Voice file is outside an allowed voice storage root")
        if path.is_symlink():
            raise OSError("Refusing to delete a symlinked voice file")
        allowed_root = (
            self.storage.voice_enrollments_dir
            if path.is_relative_to(self.storage.voice_enrollments_dir)
            else self.storage.voice_references_dir
        )
        self._reject_symlink_chain(path.parent, allowed_root)
        path.unlink(missing_ok=True)
        self._remove_empty_parents(path.parent, allowed_root)

    def remove_sample_directory(self, directory: Path) -> None:
        self._require_within(directory.resolve(), self.storage.voice_enrollments_dir)
        for name in (
            "original.wav",
            "original.webm",
            "original.ogg",
            "normalized.wav",
            "normalized.normalizing",
            ".uploading",
        ):
            candidate = directory / name
            if candidate.is_symlink():
                raise OSError("Refusing to delete a symlinked voice file")
            candidate.unlink(missing_ok=True)
        self._remove_empty_parents(directory, self.storage.voice_enrollments_dir)

    @staticmethod
    def fsync_file(path: Path) -> None:
        with path.open("rb") as file_handle:
            os.fsync(file_handle.fileno())

    @staticmethod
    def _validate_uuid(value: str) -> None:
        if str(uuid.UUID(value)) != value.lower():
            raise ValueError("Voice storage identifiers must be canonical UUIDs")

    @staticmethod
    def _require_within(path: Path, root: Path) -> None:
        if not path.is_relative_to(root.resolve()):
            raise ValueError("Voice storage path escaped its configured root")

    @staticmethod
    def _reject_symlink_chain(path: Path, root: Path) -> None:
        current = path
        resolved_root = root.resolve()
        while current != resolved_root:
            if current.is_symlink():
                raise OSError("Voice storage path contains a symlink")
            current = current.parent

    @staticmethod
    def _remove_empty_parents(path: Path, root: Path) -> None:
        resolved_root = root.resolve()
        current = path
        while current != resolved_root and current.is_relative_to(resolved_root):
            try:
                current.rmdir()
            except OSError:
                break
            current = current.parent
