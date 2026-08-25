"""Public request and response contracts for Guided Voice Enrollment."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VoiceEnrollmentCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    consent_confirmed: Literal[True]
    consent_policy_version: str = Field(default="v1", min_length=1, max_length=50)


class VoiceWarningAcknowledgement(BaseModel):
    sample_id: str
    codes: list[str] = Field(default_factory=list, max_length=20)


class VoiceEnrollmentSubmitRequest(BaseModel):
    active_reference_sample_id: str
    included_sample_ids: list[str] | None = Field(default=None, min_length=1, max_length=10)
    acknowledged_warning_codes: list[VoiceWarningAcknowledgement] = Field(
        default_factory=list, max_length=10
    )
    consent_confirmed: Literal[True]
    consent_policy_version: str = Field(default="v1", min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_unique_samples(self) -> VoiceEnrollmentSubmitRequest:
        if self.included_sample_ids is not None and len(set(self.included_sample_ids)) != len(
            self.included_sample_ids
        ):
            raise ValueError("included_sample_ids must be unique")
        return self


class VoiceQualityResultResponse(BaseModel):
    status: str
    warnings: list[str]
    version: str | None
    peak: float | None
    rms: float | None
    silence_ratio: float | None
    clipping_ratio: float | None


class VoiceSampleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    enrollment_id: str | None
    source_type: str
    prompt_id: str | None
    category: str
    status: str
    original_content_type: str | None
    original_size_bytes: int | None
    normalized_content_type: str | None
    normalized_size_bytes: int | None
    duration_seconds: float | None
    sample_rate: int | None
    channels: int | None
    bit_depth: int | None
    quality: VoiceQualityResultResponse
    failure_code: str | None
    submit_eligible: bool
    cleanup_status: str
    created_at: datetime
    validated_at: datetime | None


class VoiceEnrollmentValidationSummary(BaseModel):
    ready: int
    warning: int
    failed: int


class VoiceEnrollmentResponse(BaseModel):
    id: str
    status: str
    name: str
    description: str | None
    consent_confirmed: bool
    consent_policy_version: str | None
    sample_count: int
    samples: list[VoiceSampleResponse]
    can_submit: bool
    validation_summary: VoiceEnrollmentValidationSummary
    cleanup_status: str
    cleanup_failure_code: str | None
    voice_profile_id: str | None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    absolute_expires_at: datetime | None
