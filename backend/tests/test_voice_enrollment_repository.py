from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from backend.core.voice_enrollment_status import (
    VoiceCleanupStatus,
    VoiceEnrollmentStatus,
    VoiceSampleSourceType,
    VoiceSampleStatus,
)
from backend.repositories.voice_enrollment_repository import (
    VoiceEnrollmentRepository,
)
from backend.repositories.voice_profile_repository import VoiceProfileRepository
from backend.repositories.voice_sample_repository import VoiceSampleRepository


def _profile(repository: VoiceProfileRepository, name: str):
    return repository.create(
        name=name,
        reference_file_path=f"voices/references/{name}.wav",
        consent_confirmed=True,
        status="READY",
        quality_warnings=[],
    )


def test_enrollment_and_sample_relationships_and_query_indexes(client) -> None:
    now = datetime.now(UTC)
    with client.app.state.session_factory() as session:
        enrollments = VoiceEnrollmentRepository(session)
        samples = VoiceSampleRepository(session)
        enrollment = enrollments.create(
            profile_name="guided voice",
            consent_confirmed=True,
            consent_policy_version="v1",
            consent_confirmed_at=now,
            expires_at=now - timedelta(minutes=1),
            absolute_expires_at=now + timedelta(days=1),
            cleanup_status=VoiceCleanupStatus.PENDING.value,
        )
        sample = samples.create(
            enrollment_id=enrollment.id,
            source_type=VoiceSampleSourceType.BROWSER_RECORDING.value,
            category="natural",
        )

        assert samples.list_by_enrollment(enrollment.id) == [sample]
        assert enrollment.samples == [sample]
        assert enrollments.list_expired(now=now) == [enrollment]
        assert enrollments.list_cleanup_pending() == [enrollment]


def test_lifecycle_transitions_reject_terminal_state_regressions(client) -> None:
    with client.app.state.session_factory() as session:
        enrollments = VoiceEnrollmentRepository(session)
        enrollment = enrollments.create(profile_name="voice")
        enrollments.transition(enrollment, VoiceEnrollmentStatus.READY_TO_SUBMIT)
        enrollments.transition(enrollment, VoiceEnrollmentStatus.SUBMITTING)
        enrollments.transition(enrollment, VoiceEnrollmentStatus.COMPLETED)
        with pytest.raises(ValueError, match="COMPLETED -> DRAFT"):
            enrollments.transition(enrollment, VoiceEnrollmentStatus.DRAFT)

        cancelled = enrollments.create(profile_name="cancelled")
        enrollments.transition(cancelled, VoiceEnrollmentStatus.CANCELLED)
        with pytest.raises(ValueError, match="CANCELLED -> SUBMITTING"):
            enrollments.transition(cancelled, VoiceEnrollmentStatus.SUBMITTING)

        expired = enrollments.create(profile_name="expired")
        enrollments.transition(expired, VoiceEnrollmentStatus.EXPIRED)
        with pytest.raises(ValueError, match="EXPIRED -> READY_TO_SUBMIT"):
            enrollments.transition(expired, VoiceEnrollmentStatus.READY_TO_SUBMIT)


def test_sample_promotion_and_active_reference_invariants(client) -> None:
    with client.app.state.session_factory() as session:
        profiles = VoiceProfileRepository(session)
        enrollments = VoiceEnrollmentRepository(session)
        samples = VoiceSampleRepository(session)
        profile = _profile(profiles, "first")
        other_profile = _profile(profiles, "second")
        enrollment = enrollments.create(profile_name="guided")
        sample = samples.create(
            enrollment_id=enrollment.id,
            source_type=VoiceSampleSourceType.FILE_UPLOAD.value,
            category="speech",
        )

        with pytest.raises(ValueError, match="Only ready"):
            samples.promote(sample, profile)
        samples.transition(sample, VoiceSampleStatus.VALIDATING)
        samples.transition(sample, VoiceSampleStatus.READY)
        samples.promote(sample, profile)
        profiles.set_active_reference(profile, sample)
        assert profile.active_reference_sample_id == sample.id
        assert sample in samples.list_by_profile(profile.id)

        with pytest.raises(ValueError, match="must belong"):
            profiles.set_active_reference(
                profile, other_profile.active_reference_sample
            )

        incomplete = samples.create(
            enrollment_id=enrollment.id,
            voice_profile_id=profile.id,
            source_type=VoiceSampleSourceType.FILE_UPLOAD.value,
            category="incomplete",
            status=VoiceSampleStatus.READY.value,
        )
        with pytest.raises(ValueError, match="must be promoted"):
            profiles.set_active_reference(profile, incomplete)

        samples.transition(sample, VoiceSampleStatus.DELETE_PENDING)
        samples.transition(sample, VoiceSampleStatus.DELETED)
        with pytest.raises(ValueError, match="DELETED -> READY"):
            samples.transition(sample, VoiceSampleStatus.READY)


def test_enrollment_routes_are_not_exposed_yet(client) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(path.startswith("/api/voice-enrollments") for path in paths)
