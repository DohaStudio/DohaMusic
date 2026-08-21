from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta

import pytest

from backend.authentication.bootstrap import (
    CURRENT_LOCAL_OPERATOR_AUTHENTICATION_SELECTION,
    LocalOperatorAuthenticationBootstrapper,
    LocalOperatorAuthenticationConfig,
    LocalOperatorAuthenticationSelection,
)
from backend.authentication.contracts import (
    LocalOperatorConcreteMechanism,
    LocalOperatorCredentialReference,
    LocalOperatorProofModel,
    VerifiedLocalOperatorContext,
)
from backend.authentication.errors import (
    LocalOperatorAuthenticationError,
    LocalOperatorAuthenticationErrorCode,
)
from backend.authentication.providers import (
    FakeLocalOperatorAuthenticationProvider,
    UnavailableLocalOperatorAuthenticationProvider,
)

NOW = datetime(2026, 8, 21, 3, 0, tzinfo=UTC)


def _credential(**updates: object) -> LocalOperatorCredentialReference:
    values: dict[str, object] = {
        "provider_id": "local-operator/test-provider",
        "credential_reference_id": "credential-ref/test-operator",
        "challenge_reference_id": "challenge/test-1",
        "session_binding_reference": "session/test-1",
        "challenge_issued_at": NOW - timedelta(seconds=5),
        "challenge_expires_at": NOW + timedelta(seconds=30),
    }
    values.update(updates)
    return LocalOperatorCredentialReference(**values)  # type: ignore[arg-type]


def _config(**updates: object) -> LocalOperatorAuthenticationConfig:
    values: dict[str, object] = {
        "configuration_version": "local-operator-auth-config/test/v1",
        "provider_id": "local-operator/windows-webauthn",
        "proof_model": LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL,
        "mechanism": (LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL),
        "enabled": True,
        "freshness_required": True,
        "expiry_required": True,
        "session_binding_required": True,
    }
    values.update(updates)
    return LocalOperatorAuthenticationConfig(**values)  # type: ignore[arg-type]


def _selection(**updates: object) -> LocalOperatorAuthenticationSelection:
    values: dict[str, object] = {
        "decision_version": "local-operator-auth-selection/test/v1",
        "source_authority_reference_id": "dohamusic/adr-038",
        "decision_reference_id": "dohamusic/adr-040",
        "proof_model_selected": True,
        "selected_proof_model": (LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL),
        "concrete_os_adapter_selected": True,
        "selected_mechanism": (LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL),
        "concrete_os_adapter_implemented": False,
    }
    values.update(updates)
    return LocalOperatorAuthenticationSelection(**values)  # type: ignore[arg-type]


def test_current_selection_records_authority_without_implementation() -> None:
    selection = CURRENT_LOCAL_OPERATOR_AUTHENTICATION_SELECTION
    result = LocalOperatorAuthenticationBootstrapper().bootstrap(selection, None, None)

    assert selection.proof_model_selected is True
    assert (
        selection.selected_proof_model is LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL
    )
    assert selection.concrete_os_adapter_selected is True
    assert (
        selection.selected_mechanism
        is LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL
    )
    assert selection.concrete_os_adapter_implemented is False
    assert selection.source_authority_reference_id == "dohamusic/adr-038"
    assert result.provider is None
    assert result.readiness.proof_model_selected is True
    assert result.readiness.concrete_os_adapter_selected is True
    assert result.readiness.provider_configured is False
    assert result.readiness.provider_operational is False
    assert result.readiness.reviewer_authentication_operational is False
    assert result.readiness.reason_code == "LOCAL_OPERATOR_AUTH_NOT_CONFIGURED"


@pytest.mark.parametrize(
    "updates",
    [
        {"proof_model_selected": False},
        {"selected_proof_model": None},
        {"concrete_os_adapter_selected": False},
        {"selected_mechanism": None},
        {
            "proof_model_selected": False,
            "selected_proof_model": None,
            "concrete_os_adapter_selected": True,
        },
        {
            "concrete_os_adapter_selected": False,
            "selected_mechanism": None,
            "concrete_os_adapter_implemented": True,
        },
    ],
)
def test_selection_rejects_contradictory_states(updates: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _selection(**updates)


@pytest.mark.parametrize(
    "updates",
    [
        {"freshness_required": False},
        {"expiry_required": False},
        {"session_binding_required": False},
    ],
)
def test_config_rejects_fail_open_policy(updates: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        _config(**updates)


def test_selected_without_config_is_fail_closed() -> None:
    result = LocalOperatorAuthenticationBootstrapper().bootstrap(_selection(), None, None)

    assert result.provider is None
    assert result.readiness.provider_configured is False
    assert result.readiness.provider_operational is False
    assert result.readiness.reason_code == "LOCAL_OPERATOR_AUTH_NOT_CONFIGURED"


def test_selected_with_config_but_without_adapter_returns_unavailable_provider() -> None:
    result = LocalOperatorAuthenticationBootstrapper().bootstrap(_selection(), _config(), None)

    assert isinstance(result.provider, UnavailableLocalOperatorAuthenticationProvider)
    assert result.readiness.provider_configured is True
    assert result.readiness.provider_operational is False
    with pytest.raises(LocalOperatorAuthenticationError) as error:
        result.provider.verify(_credential(), verified_at=NOW)
    assert error.value.code is LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL


def test_disabled_config_is_not_configured() -> None:
    result = LocalOperatorAuthenticationBootstrapper().bootstrap(
        _selection(), _config(enabled=False), None
    )

    assert result.provider is None
    assert result.readiness.provider_configured is False
    assert result.readiness.provider_operational is False


def test_fake_provider_is_forbidden_in_production_bootstrap() -> None:
    with pytest.raises(LocalOperatorAuthenticationError) as error:
        LocalOperatorAuthenticationBootstrapper().bootstrap(
            _selection(),
            _config(provider_id="local-operator/test-provider"),
            FakeLocalOperatorAuthenticationProvider(),
        )
    assert error.value.code is LocalOperatorAuthenticationErrorCode.PROVIDER_FAKE_FORBIDDEN


def test_provider_mismatch_is_blocked() -> None:
    provider = UnavailableLocalOperatorAuthenticationProvider(
        provider_id="local-operator/other",
        proof_model=LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL,
        mechanism=LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL,
    )
    with pytest.raises(LocalOperatorAuthenticationError) as error:
        LocalOperatorAuthenticationBootstrapper().bootstrap(_selection(), _config(), provider)
    assert error.value.code is LocalOperatorAuthenticationErrorCode.PROVIDER_MISMATCH


class _UnexpectedOperationalProvider(UnavailableLocalOperatorAuthenticationProvider):
    @property
    def operational(self) -> bool:
        return True


def test_unimplemented_selected_adapter_cannot_become_operational() -> None:
    provider = _UnexpectedOperationalProvider(
        provider_id="local-operator/windows-webauthn",
        proof_model=LocalOperatorProofModel.OS_BOUND_LOCAL_OPERATOR_CREDENTIAL,
        mechanism=LocalOperatorConcreteMechanism.WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL,
    )
    with pytest.raises(LocalOperatorAuthenticationError) as error:
        LocalOperatorAuthenticationBootstrapper().bootstrap(_selection(), _config(), provider)
    assert error.value.code is LocalOperatorAuthenticationErrorCode.ADAPTER_NOT_IMPLEMENTED


def test_fake_provider_issues_and_revalidates_test_only_context() -> None:
    provider = FakeLocalOperatorAuthenticationProvider()
    context = provider.verify(_credential(), verified_at=NOW)
    principal = provider.revalidate(context, at=NOW + timedelta(seconds=1))

    assert principal.assurance.value == "TEST_ONLY"
    assert principal.proof_model.value == "OS_BOUND_LOCAL_OPERATOR_CREDENTIAL"
    assert context.public_summary()["mechanism"] == ("WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL")


@pytest.mark.parametrize(
    "updates",
    [
        {"provider_id": "local-operator/other"},
        {"credential_reference_id": "credential-ref/unknown"},
        {"challenge_issued_at": NOW + timedelta(seconds=1)},
        {"challenge_expires_at": NOW},
    ],
)
def test_fake_provider_rejects_invalid_or_stale_credential(
    updates: dict[str, object],
) -> None:
    with pytest.raises(LocalOperatorAuthenticationError) as error:
        FakeLocalOperatorAuthenticationProvider().verify(_credential(**updates), verified_at=NOW)
    assert error.value.code is LocalOperatorAuthenticationErrorCode.CREDENTIAL_INVALID


def test_expired_context_is_rejected() -> None:
    provider = FakeLocalOperatorAuthenticationProvider(context_lifetime_seconds=5)
    context = provider.verify(_credential(), verified_at=NOW)

    with pytest.raises(LocalOperatorAuthenticationError) as error:
        provider.revalidate(context, at=NOW + timedelta(seconds=5))
    assert error.value.code is LocalOperatorAuthenticationErrorCode.CONTEXT_EXPIRED


def test_future_revalidation_time_before_authentication_is_rejected() -> None:
    provider = FakeLocalOperatorAuthenticationProvider()
    context = provider.verify(_credential(), verified_at=NOW)

    with pytest.raises(LocalOperatorAuthenticationError) as error:
        provider.revalidate(context, at=NOW - timedelta(seconds=1))
    assert error.value.code is LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED


def test_plain_principal_and_caller_forged_context_are_rejected() -> None:
    provider = FakeLocalOperatorAuthenticationProvider()
    authentic = provider.verify(_credential(), verified_at=NOW)
    forged = VerifiedLocalOperatorContext(
        context_id="context/forged",
        principal=authentic.principal,
        authenticated_at=authentic.authenticated_at,
        expires_at=authentic.expires_at,
        private_session_reference="session/forged",
        _provider_witness=object(),
    )

    with pytest.raises(LocalOperatorAuthenticationError) as plain_error:
        provider.revalidate(authentic.principal, at=NOW)  # type: ignore[arg-type]
    assert plain_error.value.code is LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED
    with pytest.raises(LocalOperatorAuthenticationError) as error:
        provider.revalidate(forged, at=NOW)
    assert error.value.code is LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED


def test_context_copy_and_field_mutation_are_rejected() -> None:
    provider = FakeLocalOperatorAuthenticationProvider()
    authentic = provider.verify(_credential(), verified_at=NOW)
    copied = replace(authentic)
    modified = replace(authentic, expires_at=authentic.expires_at + timedelta(seconds=1))

    for context in (copied, modified):
        with pytest.raises(LocalOperatorAuthenticationError) as error:
            provider.revalidate(context, at=NOW)
        assert error.value.code is LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED
    with pytest.raises(FrozenInstanceError):
        authentic.context_id = "context/mutated"  # type: ignore[misc]


def test_context_from_other_provider_witness_is_rejected() -> None:
    first = FakeLocalOperatorAuthenticationProvider()
    second = FakeLocalOperatorAuthenticationProvider()
    context = first.verify(_credential(), verified_at=NOW)

    with pytest.raises(LocalOperatorAuthenticationError) as error:
        second.revalidate(context, at=NOW)
    assert error.value.code is LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED


def test_disabled_fake_provider_rejects_verify_and_revalidation() -> None:
    provider = FakeLocalOperatorAuthenticationProvider()
    context = provider.verify(_credential(), verified_at=NOW)
    provider.disable()

    for operation in (
        lambda: provider.verify(_credential(), verified_at=NOW),
        lambda: provider.revalidate(context, at=NOW),
    ):
        with pytest.raises(LocalOperatorAuthenticationError) as error:
            operation()
        assert error.value.code is LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL


@pytest.mark.parametrize(
    "updates",
    [
        {"provider_id": "../../unsafe"},
        {"credential_reference_id": "C:\\Users\\name"},
        {"challenge_reference_id": "username@example.com"},
        {"session_binding_reference": "session value"},
    ],
)
def test_credential_reference_rejects_identity_and_path_injection(
    updates: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        _credential(**updates)


def test_contracts_reject_credential_like_extra_fields() -> None:
    for extra_field in (
        "username",
        "password",
        "secret",
        "token",
        "private_key",
        "credential_blob",
        "private_subject",
        "verified",
    ):
        with pytest.raises(TypeError):
            _credential(**{extra_field: "synthetic-do-not-store"})


def test_private_identity_and_session_references_are_not_in_repr_or_public_summary() -> None:
    provider = FakeLocalOperatorAuthenticationProvider(
        opaque_subject_reference="subject/private-value"
    )
    credential = _credential(session_binding_reference="session/private-value")
    context = provider.verify(credential, verified_at=NOW)
    rendered = repr(context)
    summary = repr(context.public_summary())

    for private_value in ("subject/private-value", "session/private-value"):
        assert private_value not in rendered
        assert private_value not in summary


def test_errors_are_structured_and_do_not_leak_input() -> None:
    provider = FakeLocalOperatorAuthenticationProvider()
    injected = "credential-ref/private-input"

    with pytest.raises(LocalOperatorAuthenticationError) as error:
        provider.verify(
            _credential(credential_reference_id=injected),
            verified_at=NOW,
        )
    assert error.value.code is LocalOperatorAuthenticationErrorCode.CREDENTIAL_INVALID
    assert injected not in str(error.value)
