"""Strict reviewed inputs for future Durable Admission production activation.

The configuration selects exact logical identities and fixed locations.  It is
not authentication, custody evidence, journal readiness, or admission authority.
"""

from __future__ import annotations

import json
import ntpath
import re
from dataclasses import dataclass, fields

import rfc8785

from backend.authentication.contracts import require_safe_reference
from backend.bootstrap_authority.confirmation_snapshot import CONFIRMATION_RECORD_FILE
from backend.bootstrap_authority.contracts import require_uuid
from backend.bootstrap_authority.designation_snapshot import DESIGNATION_RECORD_FILE
from backend.bootstrap_authority.journal_schema_v1 import SCHEMA_VERSION as JOURNAL_SCHEMA_VERSION
from backend.bootstrap_authority.live_lineage_reader import LINEAGE_RECORD_FILE
from backend.bootstrap_authority.provisioning_authority import (
    CONFIRMATION_SIGNING_DOMAIN,
    POLICY_DOMAIN,
    PURPOSE,
)
from backend.bootstrap_authority.provisioning_authority_source import SOURCE_FILE
from backend.bootstrap_authority.provisioning_verifier_material import MATERIAL_FILE
from backend.bootstrap_authority.windows_fact_files import PIN_FACTS_FILE

CONFIGURATION_SCHEMA = "dohamusic/durable-admission-production-configuration/v1"
CONFIGURATION_VERSION = 1
PRODUCTION_ENVIRONMENT = "production"
PRODUCTION_PROFILE = "dohamusic/durable-admission-production/v1"
AUTHENTICATION_PROOF_MODEL = "OS_BOUND_LOCAL_OPERATOR_CREDENTIAL"
AUTHENTICATION_MECHANISM = "WINDOWS_WEBAUTHN_PLATFORM_CREDENTIAL"
JOURNAL_FILE = "durable-admission-journal-v1.sqlite3"
MAX_CONFIGURATION_BYTES = 32_768

_FIXED_PRIVATE_FILES = (
    DESIGNATION_RECORD_FILE,
    PIN_FACTS_FILE,
    SOURCE_FILE,
    MATERIAL_FILE,
    CONFIRMATION_RECORD_FILE,
    LINEAGE_RECORD_FILE,
)
_UNSAFE_COMPONENTS = frozenset(
    {"fake", "fakes", "fixture", "fixtures", "mock", "mocks", "temp", "tmp", "test", "tests"}
)
_RESERVED_COMPONENTS = frozenset(
    {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
)


class ProductionConfigurationDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PRODUCTION_CONFIGURATION_DENIED")


@dataclass(frozen=True, slots=True)
class ProductionDeploymentExpectations:
    """Independently reviewed identities; constructing this is not authority."""

    installation_id: str
    deployment_id: str
    authority_source_id: str
    verifier_material_id: str
    confirmation_id: str
    lineage_source_id: str
    journal_id: str
    authentication_provider_id: str

    def __post_init__(self) -> None:
        for item in fields(self):
            value = getattr(self, item.name)
            if type(value) is not str:
                raise ValueError("PRODUCTION_EXPECTATION")
            if item.name == "authentication_provider_id":
                require_safe_reference(value, item.name)
            else:
                require_uuid(value)


@dataclass(frozen=True, slots=True, repr=False)
class _ProductionDeploymentConfiguration:
    installation_id: str
    deployment_id: str
    authority_source_id: str
    verifier_material_id: str
    confirmation_id: str
    lineage_source_id: str
    journal_id: str
    private_source_root: str
    external_journal_path: str
    authentication_provider_id: str

    @property
    def private_source_files(self) -> tuple[str, ...]:
        return tuple(ntpath.join(self.private_source_root, name) for name in _FIXED_PRIVATE_FILES)


_FIELDS = frozenset(
    {
        "schema",
        "configuration_version",
        "environment",
        "profile",
        "installation_id",
        "deployment_id",
        "private_source_root",
        "designation_record_file",
        "pin_facts_file",
        "authority_source_id",
        "authority_source_file",
        "verifier_material_id",
        "verifier_material_file",
        "confirmation_id",
        "confirmation_file",
        "lineage_source_id",
        "lineage_file",
        "journal_id",
        "external_journal_path",
        "journal_schema_version",
        "policy_domain",
        "provisioning_purpose",
        "confirmation_signing_domain",
        "authentication_provider_id",
        "authentication_proof_model",
        "authentication_mechanism",
    }
)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE")
        result[key] = value
    return result


def _reject_number(_value):
    raise ValueError("NON_INTEGER_NUMBER")


def _windows_absolute_path(value: object, *, expected_file: str | None = None) -> str:
    if type(value) is not str or not re.fullmatch(r"[A-Z]:\\[^\\]+(?:\\[^\\]+)*", value):
        raise ValueError("PATH")
    parts = value[3:].split("\\")
    for part in parts:
        stem = part.split(".", 1)[0].casefold()
        if (
            not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
            or part in {".", ".."}
            or part.endswith((".", " "))
            or stem in _RESERVED_COMPONENTS
            or part.casefold() in _UNSAFE_COMPONENTS
            or "fake" in part.casefold()
            or "fixture" in part.casefold()
        ):
            raise ValueError("PATH")
    if expected_file is not None:
        if parts[-1] != expected_file or len(value) >= 260:
            raise ValueError("PATH")
    elif max(len(value + "\\" + name) for name in _FIXED_PRIVATE_FILES) >= 260:
        raise ValueError("PATH")
    return value


def _exact_expectations(value: dict, expected: ProductionDeploymentExpectations) -> None:
    for item in fields(expected):
        actual = value[item.name]
        wanted = getattr(expected, item.name)
        if type(actual) is not str or actual != wanted:
            raise ValueError("IDENTITY")


def parse_production_deployment_configuration(
    raw: bytes, *, expected: ProductionDeploymentExpectations
) -> _ProductionDeploymentConfiguration:
    """Parse exact canonical bytes without activating or opening any dependency."""

    try:
        if type(raw) is not bytes or not 0 < len(raw) <= MAX_CONFIGURATION_BYTES:
            raise ValueError("SIZE")
        if type(expected) is not ProductionDeploymentExpectations:
            raise ValueError("EXPECTATION")
        expected.__post_init__()
        value = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_float=_reject_number,
            parse_constant=_reject_number,
        )
        if type(value) is not dict or set(value) != _FIELDS or raw != rfc8785.dumps(value):
            raise ValueError("WIRE")
        fixed = {
            "schema": CONFIGURATION_SCHEMA,
            "configuration_version": CONFIGURATION_VERSION,
            "environment": PRODUCTION_ENVIRONMENT,
            "profile": PRODUCTION_PROFILE,
            "designation_record_file": DESIGNATION_RECORD_FILE,
            "pin_facts_file": PIN_FACTS_FILE,
            "authority_source_file": SOURCE_FILE,
            "verifier_material_file": MATERIAL_FILE,
            "confirmation_file": CONFIRMATION_RECORD_FILE,
            "lineage_file": LINEAGE_RECORD_FILE,
            "journal_schema_version": JOURNAL_SCHEMA_VERSION,
            "policy_domain": POLICY_DOMAIN,
            "provisioning_purpose": PURPOSE,
            "confirmation_signing_domain": CONFIRMATION_SIGNING_DOMAIN,
            "authentication_proof_model": AUTHENTICATION_PROOF_MODEL,
            "authentication_mechanism": AUTHENTICATION_MECHANISM,
        }
        for name, wanted in fixed.items():
            if type(value[name]) is not type(wanted) or value[name] != wanted:
                raise ValueError("PROFILE")
        _exact_expectations(value, expected)
        private_root = _windows_absolute_path(value["private_source_root"])
        journal_path = _windows_absolute_path(
            value["external_journal_path"], expected_file=JOURNAL_FILE
        )
        private_key = ntpath.normcase(private_root).rstrip("\\")
        journal_parent = ntpath.normcase(ntpath.dirname(journal_path)).rstrip("\\")
        if (
            private_key == journal_parent
            or journal_parent.startswith(private_key + "\\")
            or private_key.startswith(journal_parent + "\\")
        ):
            raise ValueError("STORE_SEPARATION")
        return _ProductionDeploymentConfiguration(
            installation_id=value["installation_id"],
            deployment_id=value["deployment_id"],
            authority_source_id=value["authority_source_id"],
            verifier_material_id=value["verifier_material_id"],
            confirmation_id=value["confirmation_id"],
            lineage_source_id=value["lineage_source_id"],
            journal_id=value["journal_id"],
            private_source_root=private_root,
            external_journal_path=journal_path,
            authentication_provider_id=value["authentication_provider_id"],
        )
    except ProductionConfigurationDenied:
        raise
    except Exception:
        raise ProductionConfigurationDenied() from None
