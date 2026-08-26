from __future__ import annotations

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest

from backend.core.config import Settings
from backend.core.voice_enrollment_status import (
    VoiceCleanupStatus,
    VoiceEnrollmentStatus,
    VoiceSampleSourceType,
    VoiceSampleStatus,
)
from backend.models.voice_enrollment import VoiceEnrollment
from backend.models.voice_sample import VoiceSample
from backend.repositories.voice_enrollment_repository import (
    VoiceEnrollmentRepository,
)
from backend.repositories.voice_sample_repository import VoiceSampleRepository
from backend.storage.service import StorageService
from backend.voice_enrollment.contracts import VoiceContainer
from backend.voice_enrollment.maintenance import VoiceEnrollmentMaintenanceService
from backend.voice_enrollment.scheduler import VoiceEnrollmentScheduler
from backend.voice_enrollment.storage import VoiceEnrollmentStorage


def _maintenance(client, **settings_updates: object) -> VoiceEnrollmentMaintenanceService:
    return VoiceEnrollmentMaintenanceService(
        session_factory=client.app.state.session_factory,
        storage=client.app.state.storage,
        settings=client.app.state.settings.model_copy(update=settings_updates),
    )


def _create_enrollment(client, **values: object) -> VoiceEnrollment:
    defaults: dict[str, object] = {
        "profile_name": "maintenance",
        "expires_at": datetime.now(UTC) + timedelta(days=1),
        "absolute_expires_at": datetime.now(UTC) + timedelta(days=7),
    }
    defaults.update(values)
    with client.app.state.session_factory() as session:
        return VoiceEnrollmentRepository(session).create(**defaults)


def _create_sample(client, enrollment_id: str, **values: object) -> VoiceSample:
    defaults: dict[str, object] = {
        "enrollment_id": enrollment_id,
        "source_type": VoiceSampleSourceType.FILE_UPLOAD.value,
        "category": "speech",
    }
    defaults.update(values)
    with client.app.state.session_factory() as session:
        return VoiceSampleRepository(session).create(**defaults)


def _sample_files(client, enrollment_id: str, sample_id: str) -> tuple[str, str]:
    storage = VoiceEnrollmentStorage(client.app.state.storage)
    paths = storage.sample_paths(enrollment_id, sample_id, VoiceContainer.WAV)
    storage.create_sample_directory(paths)
    paths.original.write_bytes(b"original")
    paths.normalized.write_bytes(b"normalized")
    return (
        client.app.state.storage.relative_path(paths.original),
        client.app.state.storage.relative_path(paths.normalized),
    )


def test_expiration_uses_sliding_and_absolute_deadlines(client) -> None:
    assert client.app.state.voice_enrollment_scheduler.is_running
    assert set(client.app.state.voice_maintenance_metrics.snapshot()) == {
        "cleanup_success",
        "cleanup_failed",
        "retry_count",
        "expired_enrollment",
        "orphan_found",
        "recovered_items",
    }
    now = datetime.now(UTC)
    sliding = _create_enrollment(client, expires_at=now - timedelta(seconds=1))
    absolute = _create_enrollment(
        client,
        expires_at=now + timedelta(days=1),
        absolute_expires_at=now - timedelta(seconds=1),
    )
    retry = _create_enrollment(
        client,
        status=VoiceEnrollmentStatus.CANCELLED.value,
        cleanup_status=VoiceCleanupStatus.FAILED.value,
    )
    read_only = _create_enrollment(client)
    with client.app.state.session_factory() as session:
        before_get = session.get(VoiceEnrollment, read_only.id)
        assert before_get is not None
        before_activity = before_get.last_activity_at
        before_expiry = before_get.expires_at
    assert client.get(f"/api/voice-enrollments/{read_only.id}").status_code == 200
    with client.app.state.session_factory() as session:
        after_get = session.get(VoiceEnrollment, read_only.id)
        assert after_get is not None
        assert after_get.last_activity_at == before_activity
        assert after_get.expires_at == before_expiry
    with client.app.state.session_factory() as session:
        persisted_retry = session.get(VoiceEnrollment, retry.id)
        assert persisted_retry is not None
        persisted_retry.updated_at = now
        session.commit()

    maintenance = _maintenance(client)
    assert maintenance.expire_enrollments(now=now) == 2

    with client.app.state.session_factory() as session:
        for enrollment_id in (sliding.id, absolute.id):
            enrollment = session.get(VoiceEnrollment, enrollment_id)
            assert enrollment is not None
            assert enrollment.status == VoiceEnrollmentStatus.EXPIRED.value
            assert enrollment.cleanup_status == VoiceCleanupStatus.PENDING.value
        repository = VoiceEnrollmentRepository(session)
        assert repository.list_expired(now=now) == []
        pending_ids = {
            item.id
            for item in repository.list_cleanup_pending(retry_before=now - timedelta(seconds=1))
        }
        assert pending_ids == {sliding.id, absolute.id}
        retry_ids = {
            item.id
            for item in repository.list_cleanup_pending(retry_before=now + timedelta(seconds=1))
        }
        assert retry.id in retry_ids


def test_cleanup_is_idempotent_for_partial_and_missing_files(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    enrollment = _create_enrollment(
        client,
        status=VoiceEnrollmentStatus.CANCELLED.value,
        cleanup_status=VoiceCleanupStatus.PENDING.value,
    )
    sample = _create_sample(client, enrollment.id, status=VoiceSampleStatus.DELETE_PENDING.value)
    original, normalized = _sample_files(client, enrollment.id, sample.id)
    with client.app.state.session_factory() as session:
        persisted = session.get(VoiceSample, sample.id)
        assert persisted is not None
        persisted.original_storage_path = original
        persisted.normalized_storage_path = normalized
        session.commit()

    maintenance = _maintenance(
        client, voice_delete_retry_delay_seconds=0, voice_delete_retry_limit=3
    )
    actual_delete = maintenance.storage.delete_file
    failed_once = False

    def partial_delete(path: str | None) -> None:
        nonlocal failed_once
        if path == normalized and not failed_once:
            failed_once = True
            raise OSError("simulated partial delete")
        actual_delete(path)

    monkeypatch.setattr(maintenance.storage, "delete_file", partial_delete)
    assert maintenance.process_cleanup() == 1
    with client.app.state.session_factory() as session:
        persisted = session.get(VoiceSample, sample.id)
        assert persisted is not None
        assert persisted.status == VoiceSampleStatus.DELETE_FAILED.value
        assert persisted.original_storage_path is None
        assert persisted.normalized_storage_path == normalized

    assert maintenance.process_cleanup(now=datetime.now(UTC) + timedelta(seconds=1)) == 1
    assert maintenance.process_cleanup(now=datetime.now(UTC) + timedelta(seconds=2)) == 0
    with client.app.state.session_factory() as session:
        persisted_sample = session.get(VoiceSample, sample.id)
        persisted_enrollment = session.get(VoiceEnrollment, enrollment.id)
        assert persisted_sample is not None
        assert persisted_enrollment is not None
        assert persisted_sample.status == VoiceSampleStatus.DELETED.value
        assert persisted_sample.normalized_storage_path is None
        assert persisted_enrollment.cleanup_status == VoiceCleanupStatus.COMPLETED.value
    assert maintenance.metrics.snapshot()["retry_count"] == 1


def test_cleanup_retry_limit_stops_repeated_failures(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    enrollment = _create_enrollment(
        client,
        status=VoiceEnrollmentStatus.EXPIRED.value,
        cleanup_status=VoiceCleanupStatus.PENDING.value,
    )
    sample = _create_sample(client, enrollment.id, status=VoiceSampleStatus.READY.value)
    original, normalized = _sample_files(client, enrollment.id, sample.id)
    with client.app.state.session_factory() as session:
        persisted = session.get(VoiceSample, sample.id)
        assert persisted is not None
        persisted.original_storage_path = original
        persisted.normalized_storage_path = normalized
        session.commit()

    maintenance = _maintenance(
        client, voice_delete_retry_delay_seconds=0, voice_delete_retry_limit=2
    )

    def fail_delete(_path: str | None) -> None:
        raise OSError("simulated delete failure")

    monkeypatch.setattr(maintenance.storage, "delete_file", fail_delete)
    now = datetime.now(UTC)
    assert maintenance.process_cleanup(now=now) == 1
    assert maintenance.process_cleanup(now=now + timedelta(seconds=1)) == 1
    assert maintenance.process_cleanup(now=now + timedelta(seconds=2)) == 0
    assert maintenance.metrics.snapshot()["cleanup_failed"] == 2


def test_restart_recovers_interrupted_normalize_submit_and_cleanup(client) -> None:
    validating = _create_enrollment(client)
    validating_sample = _create_sample(
        client, validating.id, status=VoiceSampleStatus.VALIDATING.value
    )
    original, normalized = _sample_files(client, validating.id, validating_sample.id)
    partial = client.app.state.storage.resolve_relative_path(normalized).with_name(
        "normalized.normalizing"
    )
    partial.write_bytes(b"partial")

    submitting = _create_enrollment(client, status=VoiceEnrollmentStatus.SUBMITTING.value)
    ready_sample = _create_sample(client, submitting.id, status=VoiceSampleStatus.READY.value)
    _, ready_normalized = _sample_files(client, submitting.id, ready_sample.id)
    unrecoverable = _create_enrollment(client, status=VoiceEnrollmentStatus.SUBMITTING.value)
    _create_sample(
        client,
        unrecoverable.id,
        status=VoiceSampleStatus.READY.value,
        normalized_storage_path=(
            f"voices/enrollments/{unrecoverable.id}/samples/{uuid.uuid4()}/normalized.wav"
        ),
    )

    deleting = _create_enrollment(
        client,
        status=VoiceEnrollmentStatus.CANCELLED.value,
        cleanup_status=VoiceCleanupStatus.RUNNING.value,
    )
    deleting_sample = _create_sample(
        client, deleting.id, status=VoiceSampleStatus.DELETE_PENDING.value
    )

    with client.app.state.session_factory() as session:
        interrupted = session.get(VoiceSample, validating_sample.id)
        ready = session.get(VoiceSample, ready_sample.id)
        assert interrupted is not None and ready is not None
        interrupted.original_storage_path = original
        interrupted.normalized_storage_path = normalized
        ready.normalized_storage_path = ready_normalized
        session.commit()

    maintenance = _maintenance(client, voice_delete_retry_delay_seconds=0)
    maintenance.recover_startup()

    with client.app.state.session_factory() as session:
        interrupted = session.get(VoiceSample, validating_sample.id)
        retriable = session.get(VoiceEnrollment, submitting.id)
        cleaned = session.get(VoiceEnrollment, deleting.id)
        failed = session.get(VoiceEnrollment, unrecoverable.id)
        cleaned_sample = session.get(VoiceSample, deleting_sample.id)
        assert interrupted is not None
        assert retriable is not None
        assert cleaned is not None and cleaned_sample is not None
        assert failed is not None
        assert interrupted.status == VoiceSampleStatus.FAILED.value
        assert interrupted.original_storage_path is None
        assert interrupted.normalized_storage_path is None
        assert retriable.status == VoiceEnrollmentStatus.READY_TO_SUBMIT.value
        assert failed.status == VoiceEnrollmentStatus.FAILED.value
        assert failed.cleanup_status == VoiceCleanupStatus.COMPLETED.value
        assert cleaned.cleanup_status == VoiceCleanupStatus.COMPLETED.value
        assert cleaned_sample.status == VoiceSampleStatus.DELETED.value
    assert not partial.exists()


def test_orphan_scan_deletes_only_unambiguous_server_paths(client) -> None:
    storage = client.app.state.storage
    orphan_enrollment = str(uuid.uuid4())
    orphan_sample = str(uuid.uuid4())
    orphan = (
        storage.voice_enrollments_dir
        / orphan_enrollment
        / "samples"
        / orphan_sample
        / "normalized.wav"
    )
    orphan.parent.mkdir(parents=True)
    orphan.write_bytes(b"orphan")
    old = datetime.now(UTC) - timedelta(days=2)
    os.utime(orphan, (old.timestamp(), old.timestamp()))
    ambiguous = storage.voice_enrollments_dir / "operator-note.txt"
    ambiguous.write_text("keep", encoding="utf-8")
    os.utime(ambiguous, (old.timestamp(), old.timestamp()))
    orphan_profile = str(uuid.uuid4())
    orphan_profile_sample = str(uuid.uuid4())
    orphan_reference = (
        storage.voice_references_dir
        / orphan_profile
        / "samples"
        / orphan_profile_sample
        / "reference.wav"
    )
    orphan_reference.parent.mkdir(parents=True)
    orphan_reference.write_bytes(b"orphan")
    os.utime(orphan_reference, (old.timestamp(), old.timestamp()))
    missing_enrollment = _create_enrollment(
        client, status=VoiceEnrollmentStatus.READY_TO_SUBMIT.value
    )
    missing_sample = _create_sample(
        client,
        missing_enrollment.id,
        status=VoiceSampleStatus.READY.value,
        normalized_storage_path=(
            f"voices/enrollments/{missing_enrollment.id}/samples/{uuid.uuid4()}/normalized.wav"
        ),
    )

    maintenance = _maintenance(client, voice_orphan_grace_seconds=0)
    assert maintenance.scan_orphans() == 4
    assert not orphan.exists()
    assert not orphan_reference.exists()
    assert ambiguous.exists()
    assert maintenance.metrics.snapshot()["orphan_found"] == 4
    assert maintenance.process_cleanup() == 1
    with client.app.state.session_factory() as session:
        assert session.get(VoiceSample, missing_sample.id).status == "DELETED"
        assert session.get(VoiceEnrollment, missing_enrollment.id).status == "DRAFT"


def test_storage_delete_is_safe_for_missing_and_duplicate_files(tmp_path) -> None:
    storage = StorageService(tmp_path / "storage")
    storage.ensure_layout()
    voice_storage = VoiceEnrollmentStorage(storage)
    missing = f"voices/enrollments/{uuid.uuid4()}/samples/{uuid.uuid4()}/original.wav"

    voice_storage.delete_file(missing)
    voice_storage.delete_file(missing)


def test_maintenance_settings_load_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "DOHAMUSIC_VOICE_CLEANUP_INTERVAL_SECONDS": "11",
        "DOHAMUSIC_VOICE_EXPIRATION_SCAN_INTERVAL_SECONDS": "12",
        "DOHAMUSIC_VOICE_ORPHAN_SCAN_INTERVAL_SECONDS": "13",
        "DOHAMUSIC_VOICE_DELETE_RETRY_LIMIT": "4",
        "DOHAMUSIC_VOICE_DELETE_RETRY_DELAY_SECONDS": "14",
        "DOHAMUSIC_VOICE_ORPHAN_GRACE_SECONDS": "15",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)

    settings = Settings.from_environment()

    assert settings.voice_cleanup_interval_seconds == 11
    assert settings.voice_expiration_scan_interval_seconds == 12
    assert settings.voice_orphan_scan_interval_seconds == 13
    assert settings.voice_delete_retry_limit == 4
    assert settings.voice_delete_retry_delay_seconds == 14
    assert settings.voice_orphan_grace_seconds == 15


def test_scheduler_runs_recovery_and_each_periodic_scan() -> None:
    class MaintenanceSpy:
        def __init__(self) -> None:
            self.recovery = 0
            self.expiration = 0
            self.cleanup = 0
            self.orphan = 0

        def recover_startup(self) -> None:
            self.recovery += 1

        def expire_enrollments(self) -> int:
            self.expiration += 1
            return 0

        def process_cleanup(self) -> int:
            self.cleanup += 1
            return 0

        def scan_orphans(self) -> int:
            self.orphan += 1
            return 0

    async def run_scheduler() -> MaintenanceSpy:
        spy = MaintenanceSpy()
        scheduler = VoiceEnrollmentScheduler(
            maintenance=spy,  # type: ignore[arg-type]
            expiration_interval_seconds=0.01,
            cleanup_interval_seconds=0.01,
            orphan_interval_seconds=0.01,
        )
        await scheduler.start()
        assert scheduler.is_running
        await asyncio.sleep(0.04)
        await scheduler.stop()
        assert not scheduler.is_running
        return spy

    spy = asyncio.run(run_scheduler())
    assert spy.recovery == 1
    assert spy.expiration >= 1
    assert spy.cleanup >= 1
    assert spy.orphan >= 1
