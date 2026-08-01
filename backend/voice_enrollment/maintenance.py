"""DB-authoritative Voice Enrollment cleanup and crash recovery."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import Settings
from backend.core.logging import get_logger
from backend.core.voice_enrollment_status import (
    VoiceCleanupStatus,
    VoiceEnrollmentStatus,
    VoiceSampleStatus,
)
from backend.models.voice_enrollment import VoiceEnrollment
from backend.models.voice_profile import VoiceProfile
from backend.models.voice_sample import VoiceSample
from backend.repositories.idempotency_repository import IdempotencyRepository
from backend.repositories.voice_enrollment_repository import (
    VoiceEnrollmentRepository,
)
from backend.repositories.voice_sample_repository import VoiceSampleRepository
from backend.storage.service import StorageService
from backend.voice_enrollment.storage import VoiceEnrollmentStorage

logger = get_logger(__name__)

SAFE_ENROLLMENT_NAMES = {
    ".uploading",
    "normalized.normalizing",
    "normalized.wav",
    "original.ogg",
    "original.wav",
    "original.webm",
}


@dataclass(slots=True)
class VoiceMaintenanceMetrics:
    cleanup_success: int = 0
    cleanup_failed: int = 0
    retry_count: int = 0
    expired_enrollment: int = 0
    orphan_found: int = 0
    recovered_items: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            setattr(self, name, getattr(self, name) + amount)

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            return {
                "cleanup_success": self.cleanup_success,
                "cleanup_failed": self.cleanup_failed,
                "retry_count": self.retry_count,
                "expired_enrollment": self.expired_enrollment,
                "orphan_found": self.orphan_found,
                "recovered_items": self.recovered_items,
            }


class VoiceEnrollmentMaintenanceService:
    """Run idempotent local cleanup using existing lifecycle columns."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        storage: StorageService,
        settings: Settings,
        metrics: VoiceMaintenanceMetrics | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.storage = VoiceEnrollmentStorage(storage)
        self.settings = settings
        self.metrics = metrics or VoiceMaintenanceMetrics()
        self._attempts: dict[tuple[str, str], int] = {}
        self._exhaustion_logged: set[tuple[str, str]] = set()
        self._run_lock = threading.Lock()

    def recover_startup(self) -> None:
        """Repair process-local interrupted states before periodic scans start."""

        if not self._run_lock.acquire(blocking=False):
            return
        try:
            recovered = self._recover_database_states()
            if recovered:
                self.metrics.increment("recovered_items", recovered)
                logger.info("voice_maintenance_recovery completed count=%d", recovered)
        finally:
            self._run_lock.release()
        self.expire_enrollments()
        self.scan_orphans()
        self.process_cleanup()

    def expire_enrollments(self, *, now: datetime | None = None) -> int:
        if not self._run_lock.acquire(blocking=False):
            return 0
        try:
            effective_now = now or datetime.now(UTC)
            with self.session_factory() as session:
                expired = VoiceEnrollmentRepository(session).list_expired(
                    now=effective_now
                )
                for enrollment in expired:
                    enrollment.status = VoiceEnrollmentStatus.EXPIRED.value
                    enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
                    enrollment.cleanup_requested_at = effective_now
                session.commit()
            if expired:
                self.metrics.increment("expired_enrollment", len(expired))
                logger.info(
                    "voice_maintenance_expiration completed count=%d", len(expired)
                )
            return len(expired)
        finally:
            self._run_lock.release()

    def process_cleanup(self, *, now: datetime | None = None) -> int:
        if not self._run_lock.acquire(blocking=False):
            return 0
        try:
            effective_now = now or datetime.now(UTC)
            retry_before = effective_now - timedelta(
                seconds=self.settings.voice_delete_retry_delay_seconds
            )
            logger.info("voice_maintenance_cleanup started")
            processed = 0
            handled_samples: set[str] = set()
            with self.session_factory() as session:
                enrollments = VoiceEnrollmentRepository(session).list_cleanup_pending(
                    retry_before=retry_before
                )
                for enrollment in enrollments:
                    enrollment_samples = VoiceSampleRepository(
                        session
                    ).list_by_enrollment(enrollment.id)
                    handled_samples.update(sample.id for sample in enrollment_samples)
                    if not self._can_attempt("enrollment", enrollment.id):
                        continue
                    is_retry = (
                        enrollment.cleanup_status == VoiceCleanupStatus.FAILED.value
                        or enrollment.status
                        == VoiceEnrollmentStatus.DELETE_FAILED.value
                    )
                    self._start_attempt("enrollment", enrollment.id, is_retry)
                    self._cleanup_enrollment(session, enrollment, effective_now)
                    processed += 1

                samples = VoiceSampleRepository(session).list_cleanup_pending(
                    retry_before=retry_before
                )
                for sample in samples:
                    if sample.id in handled_samples or not self._can_attempt(
                        "sample", sample.id
                    ):
                        continue
                    is_retry = sample.status == VoiceSampleStatus.DELETE_FAILED.value
                    self._start_attempt("sample", sample.id, is_retry)
                    self._cleanup_standalone_sample(session, sample, effective_now)
                    processed += 1
                session.commit()
            if processed:
                logger.info("voice_maintenance_cleanup completed count=%d", processed)
            return processed
        finally:
            self._run_lock.release()

    def scan_orphans(self, *, now: datetime | None = None) -> int:
        if not self._run_lock.acquire(blocking=False):
            return 0
        try:
            effective_now = now or datetime.now(UTC)
            expected, enrollment_ids, profile_ids, owned_sample_ids = (
                self._database_storage_snapshot()
            )
            orphan_count = 0
            auto_deleted = 0
            affected_enrollments: set[str] = set()
            with self.session_factory() as session:
                for sample in VoiceSampleRepository(session).list_all_managed():
                    has_enrollment = (
                        sample.enrollment_id is not None
                        and sample.enrollment_id in enrollment_ids
                    )
                    has_profile = (
                        sample.voice_profile_id is not None
                        and sample.voice_profile_id in profile_ids
                    )
                    if has_enrollment or has_profile:
                        if (
                            sample.status == VoiceSampleStatus.READY.value
                            and sample.voice_profile_id is None
                            and (
                                sample.normalized_storage_path is None
                                or self._path_is_missing(sample.normalized_storage_path)
                            )
                        ):
                            sample.status = VoiceSampleStatus.DELETE_PENDING.value
                            sample.delete_failure_code = None
                            if sample.enrollment_id is not None:
                                affected_enrollments.add(sample.enrollment_id)
                        continue
                    orphan_count += 1
                    if sample.status != VoiceSampleStatus.DELETED.value:
                        sample.status = VoiceSampleStatus.DELETE_PENDING.value
                        sample.delete_failure_code = None
                enrollment_repository = VoiceEnrollmentRepository(session)
                sample_repository = VoiceSampleRepository(session)
                for enrollment_id in affected_enrollments:
                    enrollment = enrollment_repository.get(enrollment_id)
                    if enrollment is not None and enrollment.status in {
                        VoiceEnrollmentStatus.DRAFT.value,
                        VoiceEnrollmentStatus.READY_TO_SUBMIT.value,
                    }:
                        enrollment.status = (
                            VoiceEnrollmentStatus.READY_TO_SUBMIT.value
                            if any(
                                sample.status == VoiceSampleStatus.READY.value
                                for sample in sample_repository.list_by_enrollment(
                                    enrollment_id
                                )
                            )
                            else VoiceEnrollmentStatus.DRAFT.value
                        )
                session.commit()

            for root in (
                self.storage.storage.voice_enrollments_dir,
                self.storage.storage.voice_references_dir,
            ):
                try:
                    candidates = list(root.rglob("*"))
                except OSError:
                    self.metrics.increment("cleanup_failed")
                    logger.warning("voice_maintenance_orphan partial_scan count=1")
                    continue
                for candidate in candidates:
                    if candidate.is_symlink():
                        orphan_count += 1
                        continue
                    if not candidate.is_file():
                        continue
                    relative = self.storage.storage.relative_path(candidate)
                    if relative in expected:
                        continue
                    orphan_count += 1
                    if self._can_auto_delete_orphan(
                        candidate,
                        root=root,
                        now=effective_now,
                        enrollment_ids=enrollment_ids,
                        profile_ids=profile_ids,
                        owned_sample_ids=owned_sample_ids,
                    ):
                        try:
                            self.storage.delete_file(relative)
                            auto_deleted += 1
                        except (OSError, ValueError):
                            self.metrics.increment("cleanup_failed")

            missing = sum(1 for relative in expected if self._path_is_missing(relative))
            orphan_count += missing
            if orphan_count:
                self.metrics.increment("orphan_found", orphan_count)
                logger.warning(
                    "voice_maintenance_orphan found=%d auto_deleted=%d ambiguous=%d",
                    orphan_count,
                    auto_deleted,
                    orphan_count - auto_deleted,
                )
            if auto_deleted:
                self.metrics.increment("cleanup_success", auto_deleted)
            return orphan_count
        finally:
            self._run_lock.release()

    def _recover_database_states(self) -> int:
        recovered = 0
        affected_enrollments: set[str] = set()
        with self.session_factory() as session:
            enrollment_repository = VoiceEnrollmentRepository(session)
            sample_repository = VoiceSampleRepository(session)

            running = list(
                session.scalars(
                    select(VoiceEnrollment).where(
                        VoiceEnrollment.cleanup_status
                        == VoiceCleanupStatus.RUNNING.value
                    )
                )
            )
            for enrollment in running:
                enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
                recovered += 1

            for enrollment in list(
                session.scalars(
                    select(VoiceEnrollment).where(
                        VoiceEnrollment.status.in_(
                            [
                                VoiceEnrollmentStatus.DELETE_PENDING.value,
                                VoiceEnrollmentStatus.DELETE_FAILED.value,
                            ]
                        )
                    )
                )
            ):
                enrollment.status = self._recovered_terminal_status(enrollment)
                enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
                recovered += 1

            for sample in sample_repository.list_interrupted():
                affected_enrollments.add(sample.enrollment_id or "")
                if self._delete_sample_paths(sample, keep_normalized=False):
                    sample.status = VoiceSampleStatus.FAILED.value
                    sample.failure_code = "VOICE_SAMPLE_PROCESS_INTERRUPTED"
                    sample.delete_failure_code = None
                else:
                    sample.status = VoiceSampleStatus.DELETE_FAILED.value
                    sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
                recovered += 1

            for sample in list(
                session.scalars(
                    select(VoiceSample).where(
                        VoiceSample.status == VoiceSampleStatus.DELETE_FAILED.value
                    )
                )
            ):
                sample.status = VoiceSampleStatus.DELETE_PENDING.value
                recovered += 1

            for enrollment in enrollment_repository.list_interrupted_submissions():
                samples = sample_repository.list_by_enrollment(enrollment.id)
                profile = (
                    session.get(VoiceProfile, enrollment.voice_profile_id)
                    if enrollment.voice_profile_id
                    else None
                )
                if profile is not None and self._profile_files_exist(profile, samples):
                    enrollment.status = VoiceEnrollmentStatus.COMPLETED.value
                    enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
                elif self._submission_can_retry(samples):
                    enrollment.status = VoiceEnrollmentStatus.READY_TO_SUBMIT.value
                    enrollment.cleanup_status = VoiceCleanupStatus.NOT_REQUESTED.value
                    enrollment.cleanup_failure_code = None
                else:
                    enrollment.status = VoiceEnrollmentStatus.FAILED.value
                    enrollment.failure_code = "VOICE_SUBMIT_INTERRUPTED"
                    enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
                IdempotencyRepository(session).release_in_progress_for_scope_prefix(
                    f"voice-enrollment:{enrollment.id}:"
                )
                recovered += 1

            for enrollment_id in affected_enrollments - {""}:
                enrollment = enrollment_repository.get(enrollment_id)
                if enrollment is not None and enrollment.status in {
                    VoiceEnrollmentStatus.DRAFT.value,
                    VoiceEnrollmentStatus.READY_TO_SUBMIT.value,
                }:
                    samples = sample_repository.list_by_enrollment(enrollment.id)
                    enrollment.status = (
                        VoiceEnrollmentStatus.READY_TO_SUBMIT.value
                        if any(
                            sample.status == VoiceSampleStatus.READY.value
                            for sample in samples
                        )
                        else VoiceEnrollmentStatus.DRAFT.value
                    )
            session.commit()
        return recovered

    def _cleanup_enrollment(
        self, session: Session, enrollment: VoiceEnrollment, now: datetime
    ) -> None:
        enrollment.cleanup_status = VoiceCleanupStatus.RUNNING.value
        enrollment.cleanup_failure_code = None
        session.flush()
        success = True
        for sample in VoiceSampleRepository(session).list_by_enrollment(enrollment.id):
            if (
                enrollment.status == VoiceEnrollmentStatus.COMPLETED.value
                and sample.status == VoiceSampleStatus.PROMOTED.value
            ):
                success = (
                    self._delete_sample_paths(sample, keep_normalized=True) and success
                )
                continue
            if sample.status == VoiceSampleStatus.DELETED.value:
                continue
            sample.status = VoiceSampleStatus.DELETE_PENDING.value
            if self._delete_sample_paths(sample, keep_normalized=False):
                sample.status = VoiceSampleStatus.DELETED.value
                sample.deleted_at = now
                sample.delete_failure_code = None
                self._finish_attempt("sample", sample.id, succeeded=True)
            else:
                sample.status = VoiceSampleStatus.DELETE_FAILED.value
                sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
                success = False
        if success:
            enrollment.cleanup_status = VoiceCleanupStatus.COMPLETED.value
            enrollment.cleanup_completed_at = now
            enrollment.cleanup_failure_code = None
            self._finish_attempt("enrollment", enrollment.id, succeeded=True)
        else:
            enrollment.cleanup_status = VoiceCleanupStatus.FAILED.value
            enrollment.cleanup_completed_at = None
            enrollment.cleanup_failure_code = "VOICE_STORAGE_DELETE_FAILED"
            self._finish_attempt("enrollment", enrollment.id, succeeded=False)

    def _cleanup_standalone_sample(
        self, session: Session, sample: VoiceSample, now: datetime
    ) -> None:
        if (
            sample.voice_profile_id is not None
            and session.get(VoiceProfile, sample.voice_profile_id) is not None
        ):
            sample.status = VoiceSampleStatus.DELETE_FAILED.value
            sample.delete_failure_code = "VOICE_STORAGE_DELETE_BLOCKED"
            self._finish_attempt("sample", sample.id, succeeded=False)
            logger.warning("voice_maintenance_cleanup partial count=1")
            return
        sample.status = VoiceSampleStatus.DELETE_PENDING.value
        if self._delete_sample_paths(sample, keep_normalized=False):
            sample.status = VoiceSampleStatus.DELETED.value
            sample.deleted_at = now
            sample.delete_failure_code = None
            self._finish_attempt("sample", sample.id, succeeded=True)
        else:
            sample.status = VoiceSampleStatus.DELETE_FAILED.value
            sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
            self._finish_attempt("sample", sample.id, succeeded=False)

    def _delete_sample_paths(
        self, sample: VoiceSample, *, keep_normalized: bool
    ) -> bool:
        success = self._delete_temporary_sample_paths(sample)
        original_success = self._delete_path(sample.original_storage_path)
        success = original_success and success
        if original_success:
            sample.original_storage_path = None
        if not keep_normalized:
            normalized_success = self._delete_path(sample.normalized_storage_path)
            if normalized_success:
                sample.normalized_storage_path = None
            success = normalized_success and success
        return success

    def _delete_temporary_sample_paths(self, sample: VoiceSample) -> bool:
        known_path = sample.original_storage_path or sample.normalized_storage_path
        if known_path is None:
            return True
        parent = Path(known_path).parent
        results = [
            self._delete_path((parent / name).as_posix())
            for name in (".uploading", "normalized.normalizing")
        ]
        return all(results)

    def _delete_path(self, relative_path: str | None) -> bool:
        try:
            self.storage.delete_file(relative_path)
            return True
        except (OSError, ValueError):
            return False

    def _database_storage_snapshot(
        self,
    ) -> tuple[set[str], set[str], set[str], set[str]]:
        with self.session_factory() as session:
            samples = VoiceSampleRepository(session).list_all_managed()
            profiles = list(session.scalars(select(VoiceProfile)))
            enrollments = list(session.scalars(select(VoiceEnrollment)))
            expected = {
                path
                for sample in samples
                for path in (
                    sample.original_storage_path,
                    sample.normalized_storage_path,
                )
                if path is not None
            }
            expected.update(profile.reference_file_path for profile in profiles)
            return (
                expected,
                {enrollment.id for enrollment in enrollments},
                {profile.id for profile in profiles},
                {sample.id for sample in samples},
            )

    def _can_auto_delete_orphan(
        self,
        path: Path,
        *,
        root: Path,
        now: datetime,
        enrollment_ids: set[str],
        profile_ids: set[str],
        owned_sample_ids: set[str],
    ) -> bool:
        if path.is_symlink():
            return False
        relative = path.relative_to(root)
        parts = relative.parts
        partial = path.name in {".uploading", "normalized.normalizing"}
        if not partial:
            try:
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
            except OSError:
                return False
            if (
                now - modified
            ).total_seconds() < self.settings.voice_orphan_grace_seconds:
                return False
        if root == self.storage.storage.voice_enrollments_dir:
            return (
                len(parts) == 4
                and parts[1] == "samples"
                and path.name in SAFE_ENROLLMENT_NAMES
                and _is_uuid(parts[0])
                and _is_uuid(parts[2])
                and (parts[0] not in enrollment_ids or parts[2] not in owned_sample_ids)
            )
        return (
            len(parts) == 4
            and parts[1] == "samples"
            and path.name == "reference.wav"
            and _is_uuid(parts[0])
            and _is_uuid(parts[2])
            and (parts[0] not in profile_ids or parts[2] not in owned_sample_ids)
        )

    def _submission_can_retry(self, samples: list[VoiceSample]) -> bool:
        ready = [
            sample
            for sample in samples
            if sample.status == VoiceSampleStatus.READY.value
        ]
        return bool(ready) and all(
            sample.normalized_storage_path is not None
            and self._stored_file_exists(sample.normalized_storage_path)
            for sample in ready
        )

    def _profile_files_exist(
        self, profile: VoiceProfile, samples: list[VoiceSample]
    ) -> bool:
        if profile.status != "READY":
            return False
        promoted = [
            sample
            for sample in samples
            if sample.status == VoiceSampleStatus.PROMOTED.value
        ]
        return (
            bool(promoted)
            and all(
                sample.normalized_storage_path is not None
                and self._stored_file_exists(sample.normalized_storage_path)
                for sample in promoted
            )
            and self._stored_file_exists(profile.reference_file_path)
        )

    def _stored_file_exists(self, relative_path: str) -> bool:
        try:
            return self.storage.storage.resolve_relative_path(relative_path).is_file()
        except (OSError, ValueError):
            return False

    def _path_is_missing(self, relative_path: str) -> bool:
        return not self._stored_file_exists(relative_path)

    @staticmethod
    def _recovered_terminal_status(enrollment: VoiceEnrollment) -> str:
        if enrollment.cancelled_at is not None:
            return VoiceEnrollmentStatus.CANCELLED.value
        now = datetime.now(UTC)
        expiries = [
            _as_utc(value)
            for value in (enrollment.expires_at, enrollment.absolute_expires_at)
            if value is not None
        ]
        if expiries and now >= min(expiries):
            return VoiceEnrollmentStatus.EXPIRED.value
        return VoiceEnrollmentStatus.FAILED.value

    def _can_attempt(self, kind: str, object_id: str) -> bool:
        key = (kind, object_id)
        attempts = self._attempts.get(key, 0)
        if attempts < self.settings.voice_delete_retry_limit:
            return True
        if key not in self._exhaustion_logged:
            self._exhaustion_logged.add(key)
            logger.error("voice_maintenance_cleanup retry_limit_exceeded count=1")
        return False

    def _start_attempt(self, kind: str, object_id: str, is_retry: bool) -> None:
        key = (kind, object_id)
        self._attempts[key] = self._attempts.get(key, 0) + 1
        if is_retry:
            self.metrics.increment("retry_count")
            logger.info("voice_maintenance_cleanup retry count=1")

    def _finish_attempt(self, kind: str, object_id: str, *, succeeded: bool) -> None:
        if succeeded:
            self.metrics.increment("cleanup_success")
            self._attempts.pop((kind, object_id), None)
            self._exhaustion_logged.discard((kind, object_id))
        else:
            self.metrics.increment("cleanup_failed")
            logger.error("voice_maintenance_cleanup failed count=1")


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _is_uuid(value: str) -> bool:
    try:
        return str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False
