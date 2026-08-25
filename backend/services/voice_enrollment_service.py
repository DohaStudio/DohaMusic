"""Guided Voice Enrollment lifecycle, audio, storage, and profile promotion."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.core.config import Settings
from backend.core.exceptions import AppError
from backend.core.logging import get_logger
from backend.core.voice_enrollment_status import (
    VoiceCleanupStatus,
    VoiceEnrollmentStatus,
    VoiceQualityStatus,
    VoiceSampleSourceType,
    VoiceSampleStatus,
)
from backend.models.idempotency_record import IdempotencyRecord
from backend.models.voice_enrollment import VoiceEnrollment
from backend.models.voice_sample import VoiceSample
from backend.repositories.idempotency_repository import (
    IdempotencyClaim,
    IdempotencyRepository,
)
from backend.repositories.voice_enrollment_repository import VoiceEnrollmentRepository
from backend.repositories.voice_profile_repository import VoiceProfileRepository
from backend.repositories.voice_sample_repository import VoiceSampleRepository
from backend.schemas.voice_enrollment import (
    VoiceEnrollmentCreateRequest,
    VoiceEnrollmentResponse,
    VoiceEnrollmentSubmitRequest,
    VoiceEnrollmentValidationSummary,
    VoiceQualityResultResponse,
    VoiceSampleResponse,
)
from backend.storage.service import StorageService
from backend.voice_enrollment.contracts import VoiceAudioProcessingError, VoiceContainer
from backend.voice_enrollment.media import validate_media
from backend.voice_enrollment.normalizer import (
    HybridVoiceAudioNormalizer,
    VoiceAudioNormalizer,
)
from backend.voice_enrollment.storage import VoiceEnrollmentStorage
from backend.voice_enrollment.validator import QUALITY_VERSION, VoiceAudioValidator

UPLOAD_CHUNK_BYTES = 1024 * 1024
MEDIA_HEADER_BYTES = 64 * 1024
CONSENT_POLICY_VERSION = "v1"
logger = get_logger(__name__)


class VoiceEnrollmentService:
    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        storage: StorageService,
        settings: Settings,
        normalizer: VoiceAudioNormalizer | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.storage = VoiceEnrollmentStorage(storage)
        self.settings = settings
        max_output_bytes = int(settings.voice_enrollment_max_duration_seconds * 48_000 * 2 + 4096)
        self.normalizer = normalizer or HybridVoiceAudioNormalizer(
            ffmpeg_executable=settings.voice_ffmpeg_executable,
            timeout_seconds=settings.voice_normalization_timeout_seconds,
            max_output_bytes=max_output_bytes,
        )
        self.validator = VoiceAudioValidator(
            min_duration_seconds=settings.voice_enrollment_min_duration_seconds,
            max_duration_seconds=settings.voice_enrollment_max_duration_seconds,
        )

    def create(
        self, request: VoiceEnrollmentCreateRequest, idempotency_key: str | None
    ) -> VoiceEnrollmentResponse:
        key = self._require_idempotency_key(idempotency_key)
        self._validate_policy(request.consent_policy_version)
        now = datetime.now(UTC)
        fingerprint = self._fingerprint(request.model_dump(mode="json"))
        with self.session_factory() as session:
            claim = self._claim(
                session,
                scope="voice-enrollment:create",
                key=key,
                fingerprint=fingerprint,
                now=now,
            )
            if claim.replayed:
                enrollment = session.get(VoiceEnrollment, claim.record.resource_id)
                if enrollment is None:
                    raise self._error("VOICE_ENROLLMENT_NOT_FOUND")
                return self._enrollment_response(enrollment)
            enrollment = VoiceEnrollmentRepository(session).create(
                commit=False,
                profile_name=request.name,
                profile_description=request.description,
                status=VoiceEnrollmentStatus.DRAFT.value,
                consent_confirmed=True,
                consent_policy_version=request.consent_policy_version,
                consent_confirmed_at=now,
                last_activity_at=now,
                expires_at=now
                + timedelta(hours=self.settings.voice_enrollment_sliding_expiry_hours),
                absolute_expires_at=now
                + timedelta(days=self.settings.voice_enrollment_absolute_expiry_days),
            )
            IdempotencyRepository(session).complete(
                claim.record,
                resource_type="VOICE_ENROLLMENT",
                resource_id=enrollment.id,
                response_status=201,
            )
            session.commit()
            session.refresh(enrollment)
            return self._enrollment_response(enrollment)

    def get(self, enrollment_id: str) -> VoiceEnrollmentResponse:
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            self._expire_if_needed(session, enrollment)
            return self._enrollment_response(enrollment)

    async def upload_sample(
        self,
        *,
        enrollment_id: str,
        file: UploadFile | None,
        source_type: str,
        prompt_id: str | None,
        category: str,
        idempotency_key: str | None,
    ) -> VoiceSampleResponse:
        key = self._require_idempotency_key(idempotency_key)
        if file is None or not file.filename:
            raise self._error("VOICE_SAMPLE_FILE_REQUIRED")
        try:
            source = VoiceSampleSourceType(source_type)
        except ValueError:
            raise self._error("VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE") from None
        if source == VoiceSampleSourceType.LEGACY_REFERENCE:
            raise self._error("VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE")

        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            self._expire_if_needed(session, enrollment)
            self._require_mutable(enrollment)

        sample_id = str(uuid.uuid4())
        provisional = self.storage.sample_paths(enrollment_id, sample_id, VoiceContainer.WAV)
        uploading_path = provisional.directory / ".uploading"
        size_bytes = 0
        header = bytearray()
        digest = hashlib.sha256()
        try:
            self.storage.create_sample_directory(provisional)
            with uploading_path.open("xb") as target:
                while chunk := await file.read(UPLOAD_CHUNK_BYTES):
                    size_bytes += len(chunk)
                    if size_bytes > self.settings.voice_enrollment_max_file_bytes:
                        raise self._error("VOICE_SAMPLE_TOO_LARGE")
                    digest.update(chunk)
                    if len(header) < MEDIA_HEADER_BYTES:
                        header.extend(chunk[: MEDIA_HEADER_BYTES - len(header)])
                    target.write(chunk)
                target.flush()
                os.fsync(target.fileno())
            if size_bytes == 0:
                raise self._error("VOICE_SAMPLE_EMPTY_AUDIO")
            try:
                container = validate_media(file.filename, file.content_type, bytes(header))
            except VoiceAudioProcessingError as error:
                raise self._processing_error(error.code) from None
            paths = self.storage.sample_paths(enrollment_id, sample_id, container)
            uploading_path.replace(paths.original)
        except AppError:
            self._cleanup_failed_reservation(provisional.directory)
            raise
        except OSError:
            self._cleanup_failed_reservation(provisional.directory)
            raise self._error("VOICE_SAMPLE_UPLOAD_FAILED") from None
        finally:
            await file.close()

        fingerprint = self._fingerprint(
            {
                "enrollment_id": enrollment_id,
                "source_type": source.value,
                "prompt_id": prompt_id,
                "category": category,
                "content_type": (file.content_type or "").lower(),
                "size_bytes": size_bytes,
                "sha256": digest.hexdigest(),
            }
        )
        claim_id: str | None = None
        try:
            with self.session_factory() as session:
                enrollment = self._get_enrollment(session, enrollment_id)
                self._expire_if_needed(session, enrollment)
                self._require_mutable(enrollment)
                claim = self._claim(
                    session,
                    scope=f"voice-enrollment:{enrollment_id}:upload",
                    key=key,
                    fingerprint=fingerprint,
                    now=datetime.now(UTC),
                )
                if claim.replayed:
                    existing = session.get(VoiceSample, claim.record.resource_id)
                    self._cleanup_failed_reservation(paths.directory)
                    if existing is None:
                        raise self._error("VOICE_SAMPLE_NOT_FOUND")
                    return self._sample_response(existing)
                claim_id = claim.record.id
                sample_repository = VoiceSampleRepository(session)
                if any(
                    current.status == VoiceSampleStatus.VALIDATING.value
                    for current in sample_repository.list_by_enrollment(enrollment_id)
                ):
                    IdempotencyRepository(session).release(claim.record)
                    session.commit()
                    self._cleanup_failed_reservation(paths.directory)
                    raise self._error("VOICE_ENROLLMENT_BUSY")
                if (
                    sample_repository.count_active_by_enrollment(enrollment_id)
                    >= self.settings.voice_enrollment_max_samples
                ):
                    IdempotencyRepository(session).release(claim.record)
                    session.commit()
                    self._cleanup_failed_reservation(paths.directory)
                    raise self._error("VOICE_SAMPLE_LIMIT_EXCEEDED")
                sample = sample_repository.create(
                    commit=False,
                    id=sample_id,
                    enrollment_id=enrollment_id,
                    source_type=source.value,
                    prompt_id=prompt_id,
                    category=category,
                    status=VoiceSampleStatus.VALIDATING.value,
                    original_content_type=(file.content_type or "").lower(),
                    original_size_bytes=size_bytes,
                    original_storage_path=self.storage.storage.relative_path(paths.original),
                    normalized_storage_path=self.storage.storage.relative_path(paths.normalized),
                    expires_at=enrollment.expires_at,
                )
                session.commit()

            normalized = await run_in_threadpool(
                self.normalizer.normalize, paths.original, paths.normalized, container
            )
            validated = await run_in_threadpool(self.validator.validate, normalized.path)
            with self.session_factory() as session:
                enrollment = self._get_enrollment(session, enrollment_id)
                self._expire_if_needed(session, enrollment)
                self._require_mutable(enrollment)
                sample = self._get_sample(session, enrollment_id, sample_id)
                if sample.status != VoiceSampleStatus.VALIDATING.value:
                    raise self._error("VOICE_ENROLLMENT_INVALID_STATE")
                sample.status = VoiceSampleStatus.READY.value
                sample.normalized_content_type = normalized.content_type
                sample.normalized_size_bytes = normalized.size_bytes
                sample.duration_seconds = validated.duration_seconds
                sample.sample_rate = validated.sample_rate
                sample.channels = validated.channels
                sample.bit_depth = validated.bit_depth
                sample.quality_status = validated.quality_status
                sample.quality_warnings = validated.quality_warnings
                sample.quality_metrics = {
                    "version": QUALITY_VERSION,
                    "peak": validated.metrics.peak,
                    "rms": validated.metrics.rms,
                    "silence_ratio": validated.metrics.silence_ratio,
                    "clipping_ratio": validated.metrics.clipping_ratio,
                }
                sample.validated_at = datetime.now(UTC)
                enrollment.status = VoiceEnrollmentStatus.READY_TO_SUBMIT.value
                self._touch(enrollment)
                record = session.get(IdempotencyRecord, claim_id)
                if record is None:
                    raise RuntimeError("Upload idempotency record disappeared")
                IdempotencyRepository(session).complete(
                    record,
                    resource_type="VOICE_SAMPLE",
                    resource_id=sample.id,
                    response_status=201,
                )
                session.commit()
                session.refresh(sample)
                return self._sample_response(sample)
        except VoiceAudioProcessingError as error:
            self._record_upload_failure(sample_id, claim_id, error.code, paths.directory)
            raise self._processing_error(error.code) from None
        except AppError as error:
            self._record_upload_failure(sample_id, claim_id, error.code, paths.directory)
            raise
        except Exception as error:
            logger.error(
                "Unexpected voice sample processing failure",
                extra={
                    "enrollment_id": enrollment_id,
                    "sample_id": sample_id,
                    "exception_type": type(error).__name__,
                },
                exc_info=(
                    RuntimeError,
                    RuntimeError("exception details redacted"),
                    error.__traceback__,
                ),
            )
            self._record_upload_failure(
                sample_id,
                claim_id,
                "VOICE_SAMPLE_NORMALIZATION_FAILED",
                paths.directory,
            )
            raise self._error("VOICE_SAMPLE_NORMALIZATION_FAILED") from None

    def get_sample(self, enrollment_id: str, sample_id: str) -> VoiceSampleResponse:
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            self._expire_if_needed(session, enrollment)
            return self._sample_response(self._get_sample(session, enrollment_id, sample_id))

    def delete_sample(self, enrollment_id: str, sample_id: str) -> VoiceSampleResponse:
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            self._expire_if_needed(session, enrollment)
            self._require_mutable(enrollment)
            sample = self._get_sample(session, enrollment_id, sample_id)
            if (
                sample.voice_profile_id is not None
                or sample.status == VoiceSampleStatus.PROMOTED.value
            ):
                raise self._error("VOICE_SAMPLE_IN_USE")
            if sample.status == VoiceSampleStatus.DELETED.value:
                return self._sample_response(sample)
            sample.status = VoiceSampleStatus.DELETE_PENDING.value
            session.commit()
            if not self._cleanup_sample_files(sample):
                sample.status = VoiceSampleStatus.DELETE_FAILED.value
                sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
                session.commit()
                raise self._error("VOICE_CLEANUP_FAILED")
            sample.status = VoiceSampleStatus.DELETED.value
            sample.original_storage_path = None
            sample.normalized_storage_path = None
            sample.deleted_at = datetime.now(UTC)
            sample.delete_failure_code = None
            self._recalculate_enrollment_status(session, enrollment)
            self._touch(enrollment)
            session.commit()
            session.refresh(sample)
            return self._sample_response(sample)

    def submit(
        self,
        enrollment_id: str,
        request: VoiceEnrollmentSubmitRequest,
        idempotency_key: str | None,
    ) -> VoiceEnrollmentResponse:
        key = self._require_idempotency_key(idempotency_key)
        self._validate_policy(request.consent_policy_version)
        fingerprint = self._fingerprint(request.model_dump(mode="json"))
        claim_id: str | None = None
        included_ids: list[str] = []
        promotion_paths: list[tuple[str, Path, Path]] = []
        profile_id = str(uuid.uuid4())
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            self._expire_if_needed(session, enrollment)
            claim = self._claim(
                session,
                scope=f"voice-enrollment:{enrollment_id}:submit",
                key=key,
                fingerprint=fingerprint,
                now=datetime.now(UTC),
            )
            if claim.replayed:
                return self._enrollment_response(enrollment)
            claim_id = claim.record.id
            if enrollment.status == VoiceEnrollmentStatus.COMPLETED.value:
                IdempotencyRepository(session).release(claim.record)
                session.commit()
                raise self._error("VOICE_ENROLLMENT_ALREADY_SUBMITTED")
            if enrollment.status != VoiceEnrollmentStatus.READY_TO_SUBMIT.value:
                IdempotencyRepository(session).release(claim.record)
                session.commit()
                raise self._error("VOICE_ENROLLMENT_INVALID_STATE")
            samples = VoiceSampleRepository(session).list_by_enrollment(enrollment_id)
            if any(sample.status == VoiceSampleStatus.FAILED.value for sample in samples):
                IdempotencyRepository(session).release(claim.record)
                session.commit()
                raise self._error("VOICE_SAMPLE_VALIDATION_FAILED")
            ready = [sample for sample in samples if sample.status == VoiceSampleStatus.READY.value]
            included_ids = request.included_sample_ids or [sample.id for sample in ready]
            included = [sample for sample in ready if sample.id in set(included_ids)]
            if not included or len(included) != len(included_ids):
                IdempotencyRepository(session).release(claim.record)
                session.commit()
                raise self._error("VOICE_SAMPLE_VALIDATION_FAILED")
            if request.active_reference_sample_id not in included_ids:
                IdempotencyRepository(session).release(claim.record)
                session.commit()
                raise self._error("VOICE_SAMPLE_VALIDATION_FAILED")
            acknowledgements = {
                item.sample_id: set(item.codes) for item in request.acknowledged_warning_codes
            }
            for sample in included:
                if sample.quality_status not in {
                    VoiceQualityStatus.PASS.value,
                    VoiceQualityStatus.WARNING.value,
                }:
                    raise self._error("VOICE_SAMPLE_VALIDATION_FAILED")
                if sample.quality_status == VoiceQualityStatus.WARNING.value and not set(
                    sample.quality_warnings
                ).issubset(acknowledgements.get(sample.id, set())):
                    raise self._error("VOICE_WARNING_ACKNOWLEDGEMENT_REQUIRED")
                if sample.normalized_storage_path is None:
                    raise self._error("VOICE_SAMPLE_VALIDATION_FAILED")
                promotion_paths.append(
                    (
                        sample.id,
                        self.storage.storage.resolve_relative_path(sample.normalized_storage_path),
                        self.storage.promoted_path(profile_id, sample.id),
                    )
                )
            enrollment.status = VoiceEnrollmentStatus.SUBMITTING.value
            enrollment.submitted_at = datetime.now(UTC)
            enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
            session.commit()

        moved: list[tuple[Path, Path]] = []
        try:
            for _sample_id, source, destination in promotion_paths:
                self.storage.promote(source, destination)
                moved.append((source, destination))
            with self.session_factory() as session:
                enrollment = self._get_enrollment(session, enrollment_id)
                samples = VoiceSampleRepository(session).list_by_enrollment(enrollment_id)
                included = [sample for sample in samples if sample.id in set(included_ids)]
                active = next(
                    sample for sample in included if sample.id == request.active_reference_sample_id
                )
                destination_by_id = {
                    sample_id: destination for sample_id, _source, destination in promotion_paths
                }
                active_path = destination_by_id[active.id]
                profile = VoiceProfileRepository(session).create(
                    create_compatibility_sample=False,
                    commit=False,
                    id=profile_id,
                    name=enrollment.profile_name,
                    reference_file_path=self.storage.storage.relative_path(active_path),
                    consent_confirmed=True,
                    mime_type="audio/wav",
                    size_bytes=active.normalized_size_bytes,
                    duration_seconds=active.duration_seconds,
                    sample_rate=active.sample_rate,
                    channels=active.channels,
                    status="READY",
                    quality_warnings=active.quality_warnings,
                    consent_text_version=request.consent_policy_version,
                    consent_confirmed_at=datetime.now(UTC),
                )
                sample_repository = VoiceSampleRepository(session)
                for sample in included:
                    sample.normalized_storage_path = self.storage.storage.relative_path(
                        destination_by_id[sample.id]
                    )
                    sample_repository.promote(sample, profile, commit=False)
                VoiceProfileRepository(session).set_active_reference(profile, active, commit=False)
                enrollment.voice_profile_id = profile.id
                enrollment.consent_confirmed = True
                enrollment.consent_policy_version = request.consent_policy_version
                enrollment.consent_confirmed_at = datetime.now(UTC)
                enrollment.status = VoiceEnrollmentStatus.COMPLETED.value
                enrollment.completed_at = datetime.now(UTC)
                self._touch(enrollment)
                record = session.get(IdempotencyRecord, claim_id)
                if record is None:
                    raise RuntimeError("Submit idempotency record disappeared")
                IdempotencyRepository(session).complete(
                    record,
                    resource_type="VOICE_PROFILE",
                    resource_id=profile.id,
                    response_status=201,
                )
                session.commit()
        except Exception:  # noqa: BLE001 - compensate DB and filesystem failures
            for source, destination in reversed(moved):
                with suppress(OSError):
                    self.storage.restore_promotion(destination, source)
            self._recover_submit(enrollment_id, claim_id)
            raise self._error("VOICE_PROFILE_CREATION_FAILED") from None

        self._cleanup_after_submit(enrollment_id, set(included_ids))
        return self.get(enrollment_id)

    def cancel(self, enrollment_id: str) -> VoiceEnrollmentResponse:
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            self._expire_if_needed(session, enrollment)
            if enrollment.status == VoiceEnrollmentStatus.COMPLETED.value:
                raise self._error("VOICE_ENROLLMENT_ALREADY_SUBMITTED")
            if enrollment.status == VoiceEnrollmentStatus.SUBMITTING.value:
                raise self._error("VOICE_ENROLLMENT_INVALID_STATE")
            if enrollment.status != VoiceEnrollmentStatus.CANCELLED.value:
                VoiceEnrollmentRepository(session).transition(
                    enrollment, VoiceEnrollmentStatus.CANCELLED, commit=False
                )
                self._touch(enrollment)
            enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
            enrollment.cleanup_requested_at = datetime.now(UTC)
            session.commit()
            if not self._cleanup_enrollment_in_session(session, enrollment):
                session.commit()
                raise self._error("VOICE_CLEANUP_FAILED")
            session.commit()
            return self._enrollment_response(enrollment)

    def _expire_if_needed(self, session: Session, enrollment: VoiceEnrollment) -> None:
        if enrollment.status not in {
            VoiceEnrollmentStatus.DRAFT.value,
            VoiceEnrollmentStatus.READY_TO_SUBMIT.value,
        }:
            return
        now = datetime.now(UTC)
        expiry_candidates = [
            _as_utc(value)
            for value in (enrollment.expires_at, enrollment.absolute_expires_at)
            if value is not None
        ]
        if expiry_candidates and now >= min(expiry_candidates):
            enrollment.status = VoiceEnrollmentStatus.EXPIRED.value
            enrollment.cleanup_status = VoiceCleanupStatus.PENDING.value
            enrollment.cleanup_requested_at = now
            session.commit()
            self._cleanup_enrollment_in_session(session, enrollment)
            session.commit()
            raise self._error("VOICE_ENROLLMENT_EXPIRED")

    def _cleanup_enrollment_in_session(self, session: Session, enrollment: VoiceEnrollment) -> bool:
        success = True
        for sample in VoiceSampleRepository(session).list_by_enrollment(enrollment.id):
            if sample.status == VoiceSampleStatus.DELETED.value:
                continue
            sample.status = VoiceSampleStatus.DELETE_PENDING.value
            if self._cleanup_sample_files(sample):
                sample.status = VoiceSampleStatus.DELETED.value
                sample.original_storage_path = None
                sample.normalized_storage_path = None
                sample.deleted_at = datetime.now(UTC)
                sample.delete_failure_code = None
            else:
                sample.status = VoiceSampleStatus.DELETE_FAILED.value
                sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
                success = False
        enrollment.cleanup_status = (
            VoiceCleanupStatus.COMPLETED.value if success else VoiceCleanupStatus.FAILED.value
        )
        enrollment.cleanup_completed_at = datetime.now(UTC) if success else None
        enrollment.cleanup_failure_code = None if success else "VOICE_STORAGE_DELETE_FAILED"
        return success

    def _cleanup_after_submit(self, enrollment_id: str, included_ids: set[str]) -> None:
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            success = True
            for sample in VoiceSampleRepository(session).list_by_enrollment(enrollment_id):
                if sample.id in included_ids:
                    try:
                        self.storage.delete_file(sample.original_storage_path)
                        sample.original_storage_path = None
                    except (OSError, ValueError):
                        sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
                        success = False
                    continue
                sample.status = VoiceSampleStatus.DELETE_PENDING.value
                if self._cleanup_sample_files(sample):
                    sample.status = VoiceSampleStatus.DELETED.value
                    sample.original_storage_path = None
                    sample.normalized_storage_path = None
                    sample.deleted_at = datetime.now(UTC)
                else:
                    sample.status = VoiceSampleStatus.DELETE_FAILED.value
                    sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
                    success = False
            enrollment.cleanup_status = (
                VoiceCleanupStatus.COMPLETED.value if success else VoiceCleanupStatus.FAILED.value
            )
            enrollment.cleanup_completed_at = datetime.now(UTC) if success else None
            enrollment.cleanup_failure_code = None if success else "VOICE_STORAGE_DELETE_FAILED"
            session.commit()

    def _cleanup_sample_files(self, sample: VoiceSample) -> bool:
        try:
            self.storage.delete_file(sample.original_storage_path)
            self.storage.delete_file(sample.normalized_storage_path)
            return True
        except (OSError, ValueError):
            return False

    def _cleanup_failed_reservation(self, directory: Path) -> None:
        with suppress(OSError, ValueError):
            self.storage.remove_sample_directory(directory)

    def _record_upload_failure(
        self,
        sample_id: str,
        claim_id: str | None,
        code: str,
        directory: Path,
    ) -> None:
        cleanup_succeeded = True
        try:
            self.storage.remove_sample_directory(directory)
        except (OSError, ValueError):
            cleanup_succeeded = False
        with self.session_factory() as session:
            sample = session.get(VoiceSample, sample_id)
            if sample is not None and sample.status == VoiceSampleStatus.VALIDATING.value:
                sample.failure_code = code
                sample.quality_status = VoiceQualityStatus.FAIL.value
                sample.status = (
                    VoiceSampleStatus.FAILED.value
                    if cleanup_succeeded
                    else VoiceSampleStatus.DELETE_FAILED.value
                )
                if cleanup_succeeded:
                    sample.original_storage_path = None
                    sample.normalized_storage_path = None
                else:
                    sample.delete_failure_code = "VOICE_STORAGE_DELETE_FAILED"
            record = session.get(IdempotencyRecord, claim_id) if claim_id else None
            if record is not None:
                IdempotencyRepository(session).release(record)
            session.commit()

    def _recover_submit(self, enrollment_id: str, claim_id: str | None) -> None:
        with self.session_factory() as session:
            enrollment = self._get_enrollment(session, enrollment_id)
            if enrollment.status == VoiceEnrollmentStatus.SUBMITTING.value:
                enrollment.status = VoiceEnrollmentStatus.READY_TO_SUBMIT.value
                enrollment.failure_code = "VOICE_PROFILE_CREATION_FAILED"
            record = session.get(IdempotencyRecord, claim_id) if claim_id else None
            if record is not None:
                IdempotencyRepository(session).release(record)
            session.commit()

    def _touch(self, enrollment: VoiceEnrollment) -> None:
        now = datetime.now(UTC)
        enrollment.last_activity_at = now
        sliding = now + timedelta(hours=self.settings.voice_enrollment_sliding_expiry_hours)
        absolute = _as_utc(enrollment.absolute_expires_at)
        enrollment.expires_at = min(sliding, absolute) if absolute else sliding

    @staticmethod
    def _recalculate_enrollment_status(session: Session, enrollment: VoiceEnrollment) -> None:
        samples = VoiceSampleRepository(session).list_by_enrollment(enrollment.id)
        target = (
            VoiceEnrollmentStatus.READY_TO_SUBMIT.value
            if any(sample.status == VoiceSampleStatus.READY.value for sample in samples)
            else VoiceEnrollmentStatus.DRAFT.value
        )
        enrollment.status = target

    @staticmethod
    def _require_mutable(enrollment: VoiceEnrollment) -> None:
        if enrollment.status not in {
            VoiceEnrollmentStatus.DRAFT.value,
            VoiceEnrollmentStatus.READY_TO_SUBMIT.value,
        }:
            raise VoiceEnrollmentService._error("VOICE_ENROLLMENT_INVALID_STATE")

    @staticmethod
    def _get_enrollment(session: Session, enrollment_id: str) -> VoiceEnrollment:
        enrollment = VoiceEnrollmentRepository(session).get(enrollment_id)
        if enrollment is None:
            raise VoiceEnrollmentService._error("VOICE_ENROLLMENT_NOT_FOUND")
        return enrollment

    @staticmethod
    def _get_sample(session: Session, enrollment_id: str, sample_id: str) -> VoiceSample:
        sample = VoiceSampleRepository(session).get(sample_id)
        if sample is None or sample.enrollment_id != enrollment_id:
            raise VoiceEnrollmentService._error("VOICE_SAMPLE_NOT_FOUND")
        return sample

    @staticmethod
    def _validate_policy(version: str) -> None:
        if version != CONSENT_POLICY_VERSION:
            raise VoiceEnrollmentService._error("VOICE_CONSENT_REQUIRED")

    @staticmethod
    def _require_idempotency_key(value: str | None) -> str:
        if value is None or not value.strip() or len(value) > 128:
            raise VoiceEnrollmentService._error("IDEMPOTENCY_KEY_REQUIRED")
        return value.strip()

    @staticmethod
    def _fingerprint(payload: object) -> str:
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _claim(
        session: Session,
        *,
        scope: str,
        key: str,
        fingerprint: str,
        now: datetime,
    ) -> IdempotencyClaim:
        try:
            return IdempotencyRepository(session).claim(
                scope=scope,
                key=key,
                fingerprint=fingerprint,
                now=now,
            )
        except ValueError as error:
            if str(error) == "IDEMPOTENCY_CONFLICT":
                raise VoiceEnrollmentService._error("IDEMPOTENCY_CONFLICT") from None
            raise VoiceEnrollmentService._error("IDEMPOTENCY_IN_PROGRESS") from None

    @staticmethod
    def _sample_response(sample: VoiceSample) -> VoiceSampleResponse:
        metrics = sample.quality_metrics or {}
        return VoiceSampleResponse(
            id=sample.id,
            enrollment_id=sample.enrollment_id,
            source_type=sample.source_type,
            prompt_id=sample.prompt_id,
            category=sample.category,
            status=_public_sample_status(sample.status),
            original_content_type=sample.original_content_type,
            original_size_bytes=sample.original_size_bytes,
            normalized_content_type=sample.normalized_content_type,
            normalized_size_bytes=sample.normalized_size_bytes,
            duration_seconds=sample.duration_seconds,
            sample_rate=sample.sample_rate,
            channels=sample.channels,
            bit_depth=sample.bit_depth,
            quality=VoiceQualityResultResponse(
                status=sample.quality_status or VoiceQualityStatus.FAIL.value,
                warnings=sample.quality_warnings,
                version=_metric_string(metrics, "version"),
                peak=_metric_float(metrics, "peak"),
                rms=_metric_float(metrics, "rms"),
                silence_ratio=_metric_float(metrics, "silence_ratio"),
                clipping_ratio=_metric_float(metrics, "clipping_ratio"),
            ),
            failure_code=sample.failure_code,
            submit_eligible=(
                sample.status == VoiceSampleStatus.READY.value
                and sample.quality_status
                in {VoiceQualityStatus.PASS.value, VoiceQualityStatus.WARNING.value}
            ),
            cleanup_status=_sample_cleanup_status(sample.status),
            created_at=sample.created_at,
            validated_at=sample.validated_at,
        )

    @classmethod
    def _enrollment_response(cls, enrollment: VoiceEnrollment) -> VoiceEnrollmentResponse:
        visible = [
            sample
            for sample in enrollment.samples
            if sample.status != VoiceSampleStatus.DELETED.value
        ]
        ready = sum(sample.status == VoiceSampleStatus.READY.value for sample in visible)
        warning = sum(
            sample.quality_status == VoiceQualityStatus.WARNING.value for sample in visible
        )
        failed = sum(
            sample.status
            in {
                VoiceSampleStatus.FAILED.value,
                VoiceSampleStatus.DELETE_FAILED.value,
            }
            for sample in visible
        )
        return VoiceEnrollmentResponse(
            id=enrollment.id,
            status=_public_enrollment_status(enrollment.status),
            name=enrollment.profile_name,
            description=enrollment.profile_description,
            consent_confirmed=enrollment.consent_confirmed,
            consent_policy_version=enrollment.consent_policy_version,
            sample_count=len(visible),
            samples=[cls._sample_response(sample) for sample in visible],
            can_submit=(
                enrollment.status == VoiceEnrollmentStatus.READY_TO_SUBMIT.value
                and ready > 0
                and failed == 0
            ),
            validation_summary=VoiceEnrollmentValidationSummary(
                ready=ready,
                warning=warning,
                failed=failed,
            ),
            cleanup_status=enrollment.cleanup_status,
            cleanup_failure_code=enrollment.cleanup_failure_code,
            voice_profile_id=enrollment.voice_profile_id,
            created_at=enrollment.created_at,
            updated_at=enrollment.updated_at,
            expires_at=enrollment.expires_at,
            absolute_expires_at=enrollment.absolute_expires_at,
        )

    @staticmethod
    def _processing_error(code: str) -> AppError:
        mapped = {
            "VOICE_SAMPLE_DECODE_TIMEOUT": "VOICE_SAMPLE_DECODE_FAILED",
            "VOICE_SAMPLE_INVALID_WAV_OUTPUT": "VOICE_SAMPLE_VALIDATION_FAILED",
            "VOICE_SAMPLE_EMPTY_AUDIO": "VOICE_SAMPLE_VALIDATION_FAILED",
        }.get(code, code)
        return VoiceEnrollmentService._error(mapped)

    @staticmethod
    def _error(code: str) -> AppError:
        status_code, message = ERRORS[code]
        return AppError(code, message, status_code)


ERRORS: dict[str, tuple[int, str]] = {
    "VOICE_ENROLLMENT_NOT_FOUND": (404, "음성 등록 작업을 찾을 수 없습니다."),
    "VOICE_ENROLLMENT_EXPIRED": (
        410,
        "음성 등록 시간이 만료되었습니다. 새로 시작해 주세요.",
    ),
    "VOICE_ENROLLMENT_INVALID_STATE": (
        409,
        "현재 단계에서는 이 작업을 할 수 없습니다.",
    ),
    "VOICE_ENROLLMENT_ALREADY_SUBMITTED": (409, "이미 등록된 목소리입니다."),
    "VOICE_ENROLLMENT_BUSY": (
        409,
        "다른 음성 샘플을 처리 중입니다. 완료 후 다시 시도해 주세요.",
    ),
    "VOICE_SAMPLE_LIMIT_EXCEEDED": (
        422,
        "한 번에 등록할 수 있는 음성 샘플 수를 초과했습니다.",
    ),
    "VOICE_SAMPLE_NOT_FOUND": (404, "음성 샘플을 찾을 수 없습니다."),
    "VOICE_SAMPLE_FILE_REQUIRED": (422, "음성 파일을 선택해 주세요."),
    "VOICE_SAMPLE_UNSUPPORTED_MEDIA_TYPE": (
        415,
        "지원하는 WAV, WebM 또는 Ogg 음성 파일을 사용해 주세요.",
    ),
    "VOICE_SAMPLE_TOO_LARGE": (413, "음성 파일은 25MB 이하여야 합니다."),
    "VOICE_SAMPLE_DURATION_TOO_SHORT": (422, "음성은 5초 이상이어야 합니다."),
    "VOICE_SAMPLE_DURATION_TOO_LONG": (422, "음성은 60초 이하여야 합니다."),
    "VOICE_SAMPLE_EMPTY_AUDIO": (422, "빈 음성 파일은 등록할 수 없습니다."),
    "VOICE_SAMPLE_DECODE_FAILED": (
        422,
        "음성 파일을 읽지 못했습니다. 다른 파일을 선택해 주세요.",
    ),
    "VOICE_SAMPLE_UNSUPPORTED_CODEC": (
        422,
        "이 WAV 파일의 오디오 형식은 지원하지 않습니다. PCM 16-bit WAV로 변환해 주세요.",
    ),
    "VOICE_SAMPLE_NORMALIZATION_FAILED": (
        500,
        "음성 형식을 준비하지 못했습니다. 다시 시도해 주세요.",
    ),
    "VOICE_SAMPLE_VALIDATION_FAILED": (
        422,
        "이 음성 샘플은 등록 조건을 충족하지 않습니다.",
    ),
    "VOICE_SAMPLE_UPLOAD_FAILED": (
        500,
        "음성 파일을 저장하지 못했습니다. 다시 시도해 주세요.",
    ),
    "VOICE_SAMPLE_IN_USE": (
        409,
        "등록 처리 중이거나 사용 중인 샘플은 삭제할 수 없습니다.",
    ),
    "VOICE_WARNING_ACKNOWLEDGEMENT_REQUIRED": (
        422,
        "품질 경고를 확인한 뒤 제출해 주세요.",
    ),
    "VOICE_CONSENT_REQUIRED": (422, "음성 처리와 보관 범위에 동의해 주세요."),
    "VOICE_PROFILE_CREATION_FAILED": (
        500,
        "목소리 프로필을 만들지 못했습니다. 상태를 확인해 주세요.",
    ),
    "VOICE_CLEANUP_FAILED": (500, "음성 파일을 안전하게 삭제하지 못했습니다."),
    "VOICE_NORMALIZER_UNAVAILABLE": (
        503,
        "현재 이 음성 형식을 처리할 수 없습니다. WAV 파일을 사용해 주세요.",
    ),
    "IDEMPOTENCY_KEY_REQUIRED": (
        422,
        "안전한 중복 요청 처리를 위한 요청 키가 필요합니다.",
    ),
    "IDEMPOTENCY_CONFLICT": (
        409,
        "같은 요청 키가 다른 내용에 사용되었습니다. 새 요청으로 다시 시도해 주세요.",
    ),
    "IDEMPOTENCY_IN_PROGRESS": (
        409,
        "같은 요청을 처리 중입니다. 잠시 후 상태를 확인해 주세요.",
    ),
}


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _sample_cleanup_status(status: str) -> str:
    return {
        VoiceSampleStatus.DELETE_PENDING.value: VoiceCleanupStatus.PENDING.value,
        VoiceSampleStatus.DELETE_FAILED.value: VoiceCleanupStatus.FAILED.value,
        VoiceSampleStatus.DELETED.value: VoiceCleanupStatus.COMPLETED.value,
    }.get(status, VoiceCleanupStatus.NOT_REQUESTED.value)


def _public_enrollment_status(status: str) -> str:
    return {
        VoiceEnrollmentStatus.SUBMITTING.value: "PROCESSING",
        VoiceEnrollmentStatus.DELETE_PENDING.value: "PROCESSING",
        VoiceEnrollmentStatus.DELETE_FAILED.value: "FAILED",
    }.get(status, status)


def _public_sample_status(status: str) -> str:
    return {
        VoiceSampleStatus.UPLOADED.value: "PROCESSING",
        VoiceSampleStatus.VALIDATING.value: "PROCESSING",
        VoiceSampleStatus.PROMOTED.value: "COMPLETED",
        VoiceSampleStatus.DELETE_PENDING.value: "PROCESSING",
        VoiceSampleStatus.DELETE_FAILED.value: "FAILED",
        VoiceSampleStatus.DELETED.value: "CANCELLED",
    }.get(status, status)


def _metric_float(metrics: dict[str, float | str], key: str) -> float | None:
    value = metrics.get(key)
    return float(value) if isinstance(value, int | float) else None


def _metric_string(metrics: dict[str, float | str], key: str) -> str | None:
    value = metrics.get(key)
    return value if isinstance(value, str) else None
