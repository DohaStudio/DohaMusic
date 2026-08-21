"""Stable, non-sensitive local operator authentication errors."""

from __future__ import annotations

from enum import StrEnum


class LocalOperatorAuthenticationErrorCode(StrEnum):
    NOT_SELECTED = "LOCAL_OPERATOR_AUTH_NOT_SELECTED"
    NOT_CONFIGURED = "LOCAL_OPERATOR_AUTH_NOT_CONFIGURED"
    NOT_OPERATIONAL = "LOCAL_OPERATOR_AUTH_NOT_OPERATIONAL"
    CREDENTIAL_INVALID = "LOCAL_OPERATOR_CREDENTIAL_INVALID"
    CONTEXT_EXPIRED = "LOCAL_OPERATOR_CONTEXT_EXPIRED"
    CONTEXT_UNVERIFIED = "LOCAL_OPERATOR_CONTEXT_UNVERIFIED"
    PROVIDER_FAKE_FORBIDDEN = "LOCAL_OPERATOR_PROVIDER_FAKE_FORBIDDEN"
    PROVIDER_MISMATCH = "LOCAL_OPERATOR_PROVIDER_MISMATCH"
    ADAPTER_NOT_IMPLEMENTED = "LOCAL_OPERATOR_ADAPTER_NOT_IMPLEMENTED"


SAFE_MESSAGES = {
    LocalOperatorAuthenticationErrorCode.NOT_SELECTED: (
        "Local operator proof model is not selected."
    ),
    LocalOperatorAuthenticationErrorCode.NOT_CONFIGURED: (
        "Local operator authentication is not configured."
    ),
    LocalOperatorAuthenticationErrorCode.NOT_OPERATIONAL: (
        "Local operator authentication is not operational."
    ),
    LocalOperatorAuthenticationErrorCode.CREDENTIAL_INVALID: (
        "Local operator credential proof is invalid."
    ),
    LocalOperatorAuthenticationErrorCode.CONTEXT_EXPIRED: (
        "Local operator authentication context has expired."
    ),
    LocalOperatorAuthenticationErrorCode.CONTEXT_UNVERIFIED: (
        "Local operator authentication context is not provider-verified."
    ),
    LocalOperatorAuthenticationErrorCode.PROVIDER_FAKE_FORBIDDEN: (
        "Test authentication providers are forbidden in production."
    ),
    LocalOperatorAuthenticationErrorCode.PROVIDER_MISMATCH: (
        "Local operator provider does not match the selected contract."
    ),
    LocalOperatorAuthenticationErrorCode.ADAPTER_NOT_IMPLEMENTED: (
        "The selected OS authentication adapter is not implemented."
    ),
}


class LocalOperatorAuthenticationError(Exception):
    """Authentication failure that never includes raw OS or credential details."""

    def __init__(self, code: LocalOperatorAuthenticationErrorCode) -> None:
        self.code = code
        self.safe_message = SAFE_MESSAGES[code]
        super().__init__(self.safe_message)
