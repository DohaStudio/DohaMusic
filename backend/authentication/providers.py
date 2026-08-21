"""Local operator authentication provider ports and safe test/unavailable adapters."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from backend.authentication.contracts import (
    LocalOperatorAssurance,
    LocalOperatorConcreteMechanism,
    LocalOperatorCredentialReference,
    LocalOperatorPrincipal,
    LocalOperatorProofModel,
    LocalOperatorVerificationStatus,
    VerifiedLocalOperatorContext,
    require_aware,
    require_safe_reference,
)
from backend.authentication.errors import (
    LocalOperatorAuthenticationError,
    LocalOperatorAuthenticationErrorCode,
)


@runtime_checkable
class LocalOperatorAuthenticationProvider(Protocol):
    @property
    def provider_id(self) -> str: ...

    @property
    def proof_model(self) -> LocalOperatorProofModel: ...

    @property
    def mechanism(self) -> LocalOperatorConcreteMechanism: ...

    @property
    def operational(self) -> bool: ...

    @property
    def test_only(self) -> bool: ...

    def verify(
        self,
        credential: LocalOperatorCredentialReference,
        *,
        verified_at: datetime,
    ) -> VerifiedLocalOperatorContext: ...

    def revalidate(
        self,
        context: VerifiedLocalOperatorContext,
        *,
        at: datetime,
    ) -> LocalOperatorPrincipal: ...


class UnavailableLocalOperatorAuthenticationProvider:
    """Selected mechanism stub that cannot authenticate or issue context."""

    def __init__(
        self,
        *,
        provider_id: str,
        proof_model: LocalOperatorProofModel,
        mechanism: LocalOperatorConcreteMechanism,
    ) -> None:
        self._provider_id = require_safe_reference(provider_id, "provider_id")
        self._proof_model = proof_model
        self._mechanism = mechanism

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def proof_model(self) -> LocalOperatorProofModel:
        return self._proof_model

    @property
    def mechanism(self) -> LocalOperatorConcreteMechanism:
        return self._mechanism

    @property
    def operational(self) -> bool:
        return False

    @property
    def test_only(self) -> bool:
        return False

    def verify(
        self,
        credential: LocalOperatorCredentialReference,
        *,
        verified_at: datetime,
    ) -> VerifiedLocalOperatorContext:
        del credential, verified_at
        raise LocalOperatorAuthenticationError(
            LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL
        )

    def revalidate(
        self,
        context: VerifiedLocalOperatorContext,
        *,
        at: datetime,
    ) -> LocalOperatorPrincipal:
        del context, at
        raise LocalOperatorAuthenticationError(
            LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL
        )


class FakeLocalOperatorAuthenticationProvider:
    """Deterministic test-only issuer; it never reads Windows identity or secrets."""

    def __init__(
        self,
        *,
        provider_id: str = "local-operator/test-provider",
        accepted_credential_reference_id: str = "credential-ref/test-operator",
        opaque_subject_reference: str = "subject/test-operator",
        context_lifetime_seconds: int = 300,
    ) -> None:
        self._provider_id = require_safe_reference(provider_id, "provider_id")
        self._accepted_credential_reference_id = require_safe_reference(
            accepted_credential_reference_id,
            "accepted_credential_reference_id",
        )
        self._opaque_subject_reference = require_safe_reference(
            opaque_subject_reference,
            "opaque_subject_reference",
        )
        if context_lifetime_seconds < 1 or context_lifetime_seconds > 900:
            raise ValueError("fake context lifetime must be between 1 and 900 seconds")
        self._context_lifetime = timedelta(seconds=context_lifetime_seconds)
        self._provider_witness = object()
        self._issued_contexts: dict[str, VerifiedLocalOperatorContext] = {}
        self._issue_sequence = 0
        self._enabled = True

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def proof_model(self) -> LocalOperatorProofModel:
        return LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL

    @property
    def mechanism(self) -> LocalOperatorConcreteMechanism:
        return LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL

    @property
    def operational(self) -> bool:
        return self._enabled

    @property
    def test_only(self) -> bool:
        return True

    def disable(self) -> None:
        self._enabled = False

    def verify(
        self,
        credential: LocalOperatorCredentialReference,
        *,
        verified_at: datetime,
    ) -> VerifiedLocalOperatorContext:
        self._require_operational()
        require_aware(verified_at, "verified_at")
        if (
            credential.provider_id != self.provider_id
            or credential.credential_reference_id
            != self._accepted_credential_reference_id
            or verified_at < credential.challenge_issued_at
            or verified_at >= credential.challenge_expires_at
        ):
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.CREDENTIAL_INVALID
            )

        self._issue_sequence += 1
        context_id = f"context/test-{self._issue_sequence}"
        principal = LocalOperatorPrincipal(
            provider_id=self.provider_id,
            proof_model=self.proof_model,
            mechanism=self.mechanism,
            assurance=LocalOperatorAssurance.TEST_ONLY,
            verification_status=LocalOperatorVerificationStatus.VERIFIED,
            opaque_subject_reference=self._opaque_subject_reference,
        )
        context = VerifiedLocalOperatorContext(
            context_id=context_id,
            principal=principal,
            authenticated_at=verified_at,
            expires_at=verified_at + self._context_lifetime,
            private_session_reference=credential.session_binding_reference,
            _provider_witness=self._provider_witness,
        )
        self._issued_contexts[context_id] = context
        return context

    def revalidate(
        self,
        context: VerifiedLocalOperatorContext,
        *,
        at: datetime,
    ) -> LocalOperatorPrincipal:
        self._require_operational()
        require_aware(at, "at")
        if not isinstance(context, VerifiedLocalOperatorContext):
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED
            )
        issued = self._issued_contexts.get(context.context_id)
        if (
            issued is not context
            or context._provider_witness is not self._provider_witness
            or context.principal.provider_id != self.provider_id
            or context.principal.proof_model is not self.proof_model
            or context.principal.mechanism is not self.mechanism
        ):
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED
            )
        if at < context.authenticated_at:
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED
            )
        if at >= context.expires_at:
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.CONTEXT_EXPIRED
            )
        return context.principal

    def _require_operational(self) -> None:
        if not self.operational:
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL
            )
