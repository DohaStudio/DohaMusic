"""Provider-independent local operator authentication foundation."""

from backend.authentication.bootstrap import (
    CURRENT_LOCAL_OPERATOR_AUTHENTICATION_SELECTION,
    LocalOperatorAuthenticationBootstrap,
    LocalOperatorAuthenticationBootstrapper,
    LocalOperatorAuthenticationConfig,
    LocalOperatorAuthenticationReadiness,
    LocalOperatorAuthenticationSelection,
)
from backend.authentication.contracts import (
    LocalOperatorAssurance,
    LocalOperatorConcreteMechanism,
    LocalOperatorCredentialReference,
    LocalOperatorPrincipal,
    LocalOperatorProofModel,
    VerifiedLocalOperatorContext,
)
from backend.authentication.errors import LocalOperatorAuthenticationError
from backend.authentication.providers import (
    FakeLocalOperatorAuthenticationProvider,
    LocalOperatorAuthenticationProvider,
    UnavailableLocalOperatorAuthenticationProvider,
)

__all__ = [
    "CURRENT_LOCAL_OPERATOR_AUTHENTICATION_SELECTION",
    "FakeLocalOperatorAuthenticationProvider",
    "LocalOperatorAssurance",
    "LocalOperatorAuthenticationBootstrap",
    "LocalOperatorAuthenticationBootstrapper",
    "LocalOperatorAuthenticationConfig",
    "LocalOperatorAuthenticationError",
    "LocalOperatorAuthenticationProvider",
    "LocalOperatorAuthenticationReadiness",
    "LocalOperatorAuthenticationSelection",
    "LocalOperatorConcreteMechanism",
    "LocalOperatorCredentialReference",
    "LocalOperatorPrincipal",
    "LocalOperatorProofModel",
    "UnavailableLocalOperatorAuthenticationProvider",
    "VerifiedLocalOperatorContext",
]
