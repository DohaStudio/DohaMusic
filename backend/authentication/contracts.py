"""Provider-independent local operator authentication value contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

SAFE_REFERENCE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class LocalOperatorProofModel(StrEnum):
    OS_BOUND_LOCAL_OPERATOR_CREDENTIAL = "OS_BOUND_LOCAL_OPERATOR_CREDENTIAL"


class LocalOperatorConcreteMechanism(StrEnum):
    WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL = "WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL"


class LocalOperatorAssurance(StrEnum):
    LOCAL_OS_BOUND = "LOCAL_OS_BOUND"
    TEST_ONLY = "TEST_ONLY"


class LocalOperatorVerificationStatus(StrEnum):
    VERIFIED = "VERIFIED"


def require_safe_reference(value: str, label: str) -> str:
    if (
        not SAFE_REFERENCE.fullmatch(value)
        or ".." in value
        or "\\" in value
        or value.startswith(("/", "//"))
    ):
        raise ValueError(f"{label} must be an opaque logical reference")
    return value


def require_aware(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value


@dataclass(frozen=True, slots=True)
class LocalOperatorCredentialReference:
    """Unverified logical reference; it never contains credential material."""

    provider_id: str
    credential_reference_id: str
    challenge_reference_id: str
    session_binding_reference: str = field(repr=False)
    challenge_issued_at: datetime
    challenge_expires_at: datetime

    def __post_init__(self) -> None:
        require_safe_reference(self.provider_id, "provider_id")
        require_safe_reference(self.credential_reference_id, "credential_reference_id")
        require_safe_reference(self.challenge_reference_id, "challenge_reference_id")
        require_safe_reference(self.session_binding_reference, "session_binding_reference")
        require_aware(self.challenge_issued_at, "challenge_issued_at")
        require_aware(self.challenge_expires_at, "challenge_expires_at")
        if self.challenge_expires_at <= self.challenge_issued_at:
            raise ValueError("challenge expiry must follow challenge issuance")


@dataclass(frozen=True, slots=True)
class LocalOperatorPrincipal:
    """Internal authenticated principal; never a public reviewer identity."""

    provider_id: str
    proof_model: LocalOperatorProofModel
    mechanism: LocalOperatorConcreteMechanism
    assurance: LocalOperatorAssurance
    verification_status: LocalOperatorVerificationStatus
    opaque_subject_reference: str = field(repr=False)

    def __post_init__(self) -> None:
        require_safe_reference(self.provider_id, "provider_id")
        require_safe_reference(self.opaque_subject_reference, "opaque_subject_reference")
        if self.verification_status is not LocalOperatorVerificationStatus.VERIFIED:
            raise ValueError("principal must be provider-verified")


@dataclass(frozen=True, slots=True)
class VerifiedLocalOperatorContext:
    """Provider-issued capability whose private provenance is revalidated by its issuer."""

    context_id: str
    principal: LocalOperatorPrincipal
    authenticated_at: datetime
    expires_at: datetime
    private_session_reference: str = field(repr=False)
    _provider_witness: Any = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        require_safe_reference(self.context_id, "context_id")
        require_safe_reference(self.private_session_reference, "private_session_reference")
        require_aware(self.authenticated_at, "authenticated_at")
        require_aware(self.expires_at, "expires_at")
        if self.expires_at <= self.authenticated_at:
            raise ValueError("context expiry must follow authentication")
        if self._provider_witness is None:
            raise ValueError("provider witness is required")

    def public_summary(self) -> dict[str, str]:
        """Return only non-private classification metadata for diagnostics."""

        return {
            "context_id": self.context_id,
            "provider_id": self.principal.provider_id,
            "proof_model": self.principal.proof_model.value,
            "mechanism": self.principal.mechanism.value,
            "assurance": self.principal.assurance.value,
            "verification_status": self.principal.verification_status.value,
            "authenticated_at": self.authenticated_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
        }
