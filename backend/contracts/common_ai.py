"""Opt-in access to the pinned DohaStudio Common AI Contract package."""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from types import ModuleType
from typing import Any

COMMON_AI_PACKAGE_VERSION = "0.1.0"
COMMON_AI_POLICY_VERSION = "1.0.0"
RIGHTS_METADATA_SCHEMA = "rights_metadata"

_EXPECTED_SCHEMAS = (
    "common_envelope",
    "dataset_manifest",
    "dataset_version",
    "evaluation_run",
    "learning_candidate",
    "model_manifest",
    "model_version",
    "music_intent",
    "provider_capability",
    "rights_metadata",
    "training_eligibility",
    "training_run",
)
_EXPECTED_RESOURCES = (
    "common-envelope.schema.json",
    "dataset-manifest.schema.json",
    "dataset-version.schema.json",
    "evaluation-run.schema.json",
    "learning-candidate.schema.json",
    "model-manifest.schema.json",
    "model-version.schema.json",
    "music-intent.schema.json",
    "provider-capability.schema.json",
    "rights-metadata.schema.json",
    "training-eligibility.schema.json",
    "training-run.schema.json",
    "version-policy.json",
)
_REQUIRED_PUBLIC_API = (
    "ContractResourceError",
    "__version__",
    "contract_policy_version",
    "get_schema",
    "resource_names",
    "schema_names",
    "validate_contract",
)


class CommonAIContractError(RuntimeError):
    """Base error for the Common AI Contract consumer boundary."""


class CommonAIContractUnavailableError(CommonAIContractError):
    """Raised when the pinned package cannot be imported."""


class CommonAIContractCompatibilityError(CommonAIContractError):
    """Raised when the installed package does not match the pinned contract."""


@dataclass(frozen=True, slots=True)
class CommonAIContractStatus:
    """Verified package and resource identity without filesystem details."""

    package_version: str
    policy_version: str
    schema_names: tuple[str, ...]
    resource_names: tuple[str, ...]


def _load_package() -> ModuleType:
    try:
        package = import_module("dohastudio_common_ai")
    except ModuleNotFoundError:
        raise CommonAIContractUnavailableError(
            "The pinned Common AI Contract package is unavailable."
        ) from None

    if any(not hasattr(package, name) for name in _REQUIRED_PUBLIC_API):
        raise CommonAIContractCompatibilityError(
            "The Common AI Contract package public API is incompatible."
        )
    return package


def common_ai_contract_status() -> CommonAIContractStatus:
    """Fail closed unless package, policy, schemas, and resources match v1."""

    package = _load_package()
    try:
        package_version = str(package.__version__)
        policy_version = str(package.contract_policy_version())
        schema_names = tuple(package.schema_names())
        resource_names = tuple(package.resource_names())
    except (AttributeError, TypeError, ValueError, package.ContractResourceError):
        raise CommonAIContractCompatibilityError(
            "The Common AI Contract package identity could not be verified."
        ) from None
    if (
        package_version != COMMON_AI_PACKAGE_VERSION
        or policy_version != COMMON_AI_POLICY_VERSION
        or schema_names != _EXPECTED_SCHEMAS
        or resource_names != _EXPECTED_RESOURCES
    ):
        raise CommonAIContractCompatibilityError(
            "The Common AI Contract package does not match the supported v1 contract."
        )
    return CommonAIContractStatus(
        package_version=package_version,
        policy_version=policy_version,
        schema_names=schema_names,
        resource_names=resource_names,
    )


def load_common_ai_schema(name_or_id: str) -> dict[str, Any]:
    """Load one canonical packaged schema by public name or exact schema ID."""

    package = _load_package()
    common_ai_contract_status()
    try:
        return package.get_schema(name_or_id)
    except package.ContractResourceError:
        raise CommonAIContractError(
            "The requested Common AI Contract schema is unavailable."
        ) from None


def validate_common_ai_contract(
    payload: Any, *, expected_kind: str | None = None
) -> tuple[Any, ...]:
    """Return the package's canonical ValidationIssue objects unchanged."""

    package = _load_package()
    common_ai_contract_status()
    try:
        return package.validate_contract(payload, expected_kind=expected_kind)
    except package.ContractResourceError:
        raise CommonAIContractError(
            "The Common AI Contract resources are unavailable."
        ) from None


def validate_rights_metadata(payload: Any) -> tuple[Any, ...]:
    """Validate a complete RightsMetadata object without local field synthesis."""

    return validate_common_ai_contract(payload, expected_kind=RIGHTS_METADATA_SCHEMA)
