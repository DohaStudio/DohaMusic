"""Fail-closed local operator authentication selection and bootstrap."""

from __future__ import annotations

from dataclasses import dataclass

from backend.authentication.contracts import (
    LocalOperatorConcreteMechanism,
    LocalOperatorProofModel,
    require_safe_reference,
)
from backend.authentication.errors import (
    LocalOperatorAuthenticationError,
    LocalOperatorAuthenticationErrorCode,
)
from backend.authentication.providers import (
    LocalOperatorAuthenticationProvider,
    UnavailableLocalOperatorAuthenticationProvider,
)


@dataclass(frozen=True, slots=True)
class LocalOperatorAuthenticationSelection:
    decision_version: str
    source_authority_reference_id: str
    decision_reference_id: str
    proof_model_selected: bool
    selected_proof_model: LocalOperatorProofModel | None
    concrete_os_adapter_selected: bool
    selected_mechanism: LocalOperatorConcreteMechanism | None
    concrete_os_adapter_implemented: bool

    def __post_init__(self) -> None:
        require_safe_reference(self.decision_version, "decision_version")
        require_safe_reference(
            self.source_authority_reference_id,
            "source_authority_reference_id",
        )
        require_safe_reference(self.decision_reference_id, "decision_reference_id")
        if self.proof_model_selected != (self.selected_proof_model is not None):
            raise ValueError("proof model selection state is contradictory")
        if self.concrete_os_adapter_selected != (self.selected_mechanism is not None):
            raise ValueError("concrete adapter selection state is contradictory")
        if self.concrete_os_adapter_selected and not self.proof_model_selected:
            raise ValueError(
                "concrete adapter requires an authority-selected proof model"
            )
        if (
            self.concrete_os_adapter_implemented
            and not self.concrete_os_adapter_selected
        ):
            raise ValueError("implemented adapter must first be selected")


@dataclass(frozen=True, slots=True)
class LocalOperatorAuthenticationConfig:
    configuration_version: str
    provider_id: str
    proof_model: LocalOperatorProofModel
    mechanism: LocalOperatorConcreteMechanism
    enabled: bool
    freshness_required: bool
    expiry_required: bool
    session_binding_required: bool

    def __post_init__(self) -> None:
        require_safe_reference(self.configuration_version, "configuration_version")
        require_safe_reference(self.provider_id, "provider_id")
        if not self.freshness_required or not self.expiry_required:
            raise ValueError(
                "local operator authentication requires freshness and expiry"
            )
        if not self.session_binding_required:
            raise ValueError("local operator authentication requires session binding")


@dataclass(frozen=True, slots=True)
class LocalOperatorAuthenticationReadiness:
    proof_model_selected: bool
    concrete_os_adapter_selected: bool
    provider_configured: bool
    provider_operational: bool
    reviewer_authentication_operational: bool
    reason_code: str


@dataclass(frozen=True, slots=True)
class LocalOperatorAuthenticationBootstrap:
    readiness: LocalOperatorAuthenticationReadiness
    provider: LocalOperatorAuthenticationProvider | None = None


class LocalOperatorAuthenticationBootstrapper:
    """Composes explicit adapters only and never trusts localhost or OS usernames."""

    def bootstrap(
        self,
        selection: LocalOperatorAuthenticationSelection,
        config: LocalOperatorAuthenticationConfig | None,
        provider: LocalOperatorAuthenticationProvider | None,
    ) -> LocalOperatorAuthenticationBootstrap:
        if not selection.proof_model_selected:
            return _unavailable(
                LocalOperatorAuthenticationErrorCode.NOT_SELECTED,
                selection=selection,
            )
        if config is None or not config.enabled:
            return _unavailable(
                LocalOperatorAuthenticationErrorCode.NOT_CONFIGURED,
                selection=selection,
            )
        if (
            config.proof_model is not selection.selected_proof_model
            or config.mechanism is not selection.selected_mechanism
        ):
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.PROVIDER_MISMATCH
            )
        if provider is None:
            unavailable_provider = UnavailableLocalOperatorAuthenticationProvider(
                provider_id=config.provider_id,
                proof_model=config.proof_model,
                mechanism=config.mechanism,
            )
            return _configured_unavailable(selection, unavailable_provider)
        if provider.test_only:
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.PROVIDER_FAKE_FORBIDDEN
            )
        if (
            provider.provider_id != config.provider_id
            or provider.proof_model is not config.proof_model
            or provider.mechanism is not config.mechanism
        ):
            raise LocalOperatorAuthenticationError(
                LocalOperatorAuthenticationErrorCode.PROVIDER_MISMATCH
            )
        if not selection.concrete_os_adapter_implemented:
            if provider.operational:
                raise LocalOperatorAuthenticationError(
                    LocalOperatorAuthenticationErrorCode.ADAPTER_NOT_IMPLEMENTED
                )
            return _configured_unavailable(selection, provider)
        if not provider.operational:
            return _configured_unavailable(selection, provider)

        readiness = LocalOperatorAuthenticationReadiness(
            proof_model_selected=True,
            concrete_os_adapter_selected=True,
            provider_configured=True,
            provider_operational=True,
            reviewer_authentication_operational=True,
            reason_code="LOCAL_OPERATOR_AUTH_OPERATIONAL",
        )
        return LocalOperatorAuthenticationBootstrap(
            readiness=readiness, provider=provider
        )


def _unavailable(
    reason: LocalOperatorAuthenticationErrorCode,
    *,
    selection: LocalOperatorAuthenticationSelection,
) -> LocalOperatorAuthenticationBootstrap:
    return LocalOperatorAuthenticationBootstrap(
        readiness=LocalOperatorAuthenticationReadiness(
            proof_model_selected=selection.proof_model_selected,
            concrete_os_adapter_selected=selection.concrete_os_adapter_selected,
            provider_configured=False,
            provider_operational=False,
            reviewer_authentication_operational=False,
            reason_code=reason.value,
        )
    )


def _configured_unavailable(
    selection: LocalOperatorAuthenticationSelection,
    provider: LocalOperatorAuthenticationProvider,
) -> LocalOperatorAuthenticationBootstrap:
    return LocalOperatorAuthenticationBootstrap(
        readiness=LocalOperatorAuthenticationReadiness(
            proof_model_selected=selection.proof_model_selected,
            concrete_os_adapter_selected=selection.concrete_os_adapter_selected,
            provider_configured=True,
            provider_operational=False,
            reviewer_authentication_operational=False,
            reason_code=LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL.value,
        ),
        provider=provider,
    )


CURRENT_LOCAL_OPERATOR_AUTHENTICATION_SELECTION = LocalOperatorAuthenticationSelection(
    decision_version="local-operator-auth-selection/v1",
    source_authority_reference_id="dohamusic/adr-038",
    decision_reference_id="dohamusic/adr-041",
    proof_model_selected=True,
    selected_proof_model=LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL,
    concrete_os_adapter_selected=True,
    selected_mechanism=(
        LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL
    ),
    concrete_os_adapter_implemented=False,
)
