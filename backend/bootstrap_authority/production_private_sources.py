"""Immutable routing descriptors for future production private-source composition.

No descriptor opens a path or claims source existence, custody, authenticity,
currentness, authorization, admission, or activation readiness.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass
from enum import StrEnum

from backend.bootstrap_authority.confirmation_snapshot import CONFIRMATION_RECORD_FILE
from backend.bootstrap_authority.contracts import require_digest, require_uuid
from backend.bootstrap_authority.designation_snapshot import DESIGNATION_RECORD_FILE
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.live_lineage_reader import LINEAGE_RECORD_FILE
from backend.bootstrap_authority.production_configuration import (
    CONFIGURATION_SCHEMA,
    CONFIGURATION_VERSION,
    PRODUCTION_PROFILE,
    ProductionDeploymentExpectations,
    parse_production_deployment_configuration,
)
from backend.bootstrap_authority.provisioning_authority import (
    CONFIRMATION_SIGNING_DOMAIN,
    POLICY_DOMAIN,
    PURPOSE,
)
from backend.bootstrap_authority.provisioning_authority_source import SOURCE_FILE
from backend.bootstrap_authority.provisioning_verifier_material import MATERIAL_FILE
from backend.bootstrap_authority.windows_fact_files import PIN_FACTS_FILE


class ProductionPrivateSourceFactoryDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PRODUCTION_PRIVATE_SOURCE_FACTORY_DENIED")


class ProductionPrivateSourceRole(StrEnum):
    DESIGNATION_RECORD = "DESIGNATION_RECORD"
    PRIVATE_PIN_FACTS = "PRIVATE_PIN_FACTS"
    PROVISIONING_AUTHORITY_HISTORY = "PROVISIONING_AUTHORITY_HISTORY"
    PROVISIONING_VERIFIER_MATERIAL = "PROVISIONING_VERIFIER_MATERIAL"
    ORIGINAL_CONFIRMATION = "ORIGINAL_CONFIRMATION"
    LIVE_POLICY_LINEAGE = "LIVE_POLICY_LINEAGE"


class ProductionPrivateSourceReadiness(StrEnum):
    DESCRIPTORS_READY_SOURCES_UNPROVISIONED = "DESCRIPTORS_READY_SOURCES_UNPROVISIONED"


_ROLE_FILES = {
    ProductionPrivateSourceRole.DESIGNATION_RECORD: DESIGNATION_RECORD_FILE,
    ProductionPrivateSourceRole.PRIVATE_PIN_FACTS: PIN_FACTS_FILE,
    ProductionPrivateSourceRole.PROVISIONING_AUTHORITY_HISTORY: SOURCE_FILE,
    ProductionPrivateSourceRole.PROVISIONING_VERIFIER_MATERIAL: MATERIAL_FILE,
    ProductionPrivateSourceRole.ORIGINAL_CONFIRMATION: CONFIRMATION_RECORD_FILE,
    ProductionPrivateSourceRole.LIVE_POLICY_LINEAGE: LINEAGE_RECORD_FILE,
}


@dataclass(frozen=True, slots=True, repr=False)
class _ProductionPrivateSourceDescriptor:
    configuration_digest: str
    installation_id: str
    deployment_id: str
    role: ProductionPrivateSourceRole
    expected_identity: str
    root: str
    fixed_filename: str
    fixed_path: str
    policy_domain: str
    provisioning_purpose: str
    confirmation_signing_domain: str

    def __post_init__(self) -> None:
        for value in (
            self.installation_id,
            self.deployment_id,
            self.expected_identity,
        ):
            if type(value) is not str:
                raise ValueError("SOURCE_DESCRIPTOR_IDENTITY")
            require_uuid(value)
        if type(self.configuration_digest) is not str:
            raise ValueError("SOURCE_DESCRIPTOR_CONFIGURATION")
        require_digest(self.configuration_digest)
        if type(self.role) is not ProductionPrivateSourceRole:
            raise ValueError("SOURCE_DESCRIPTOR_ROLE")
        if (
            type(self.root) is not str
            or type(self.fixed_filename) is not str
            or type(self.fixed_path) is not str
            or self.fixed_filename != _ROLE_FILES[self.role]
            or self.fixed_path != ntpath.join(self.root, self.fixed_filename)
            or ntpath.dirname(self.fixed_path) != self.root
            or self.policy_domain != POLICY_DOMAIN
            or self.provisioning_purpose != PURPOSE
            or self.confirmation_signing_domain != CONFIRMATION_SIGNING_DOMAIN
        ):
            raise ValueError("SOURCE_DESCRIPTOR_BINDING")


@dataclass(frozen=True, slots=True, repr=False)
class _ProductionPrivateSourceBundle:
    configuration_digest: str
    configuration_schema: str
    configuration_version: int
    configuration_profile: str
    installation_id: str
    deployment_id: str
    descriptors: tuple[_ProductionPrivateSourceDescriptor, ...]
    readiness: ProductionPrivateSourceReadiness

    def __post_init__(self) -> None:
        if (
            type(self.configuration_digest) is not str
            or self.configuration_schema != CONFIGURATION_SCHEMA
            or type(self.configuration_version) is not int
            or self.configuration_version != CONFIGURATION_VERSION
            or self.configuration_profile != PRODUCTION_PROFILE
            or type(self.installation_id) is not str
            or type(self.deployment_id) is not str
            or type(self.descriptors) is not tuple
            or self.readiness
            is not ProductionPrivateSourceReadiness.DESCRIPTORS_READY_SOURCES_UNPROVISIONED
        ):
            raise ValueError("SOURCE_BUNDLE")
        require_digest(self.configuration_digest)
        require_uuid(self.installation_id)
        require_uuid(self.deployment_id)
        expected_roles = tuple(ProductionPrivateSourceRole)
        if (
            len(self.descriptors) != len(expected_roles)
            or tuple(item.role for item in self.descriptors) != expected_roles
            or any(
                type(item) is not _ProductionPrivateSourceDescriptor for item in self.descriptors
            )
            or any(
                item.configuration_digest != self.configuration_digest
                or item.installation_id != self.installation_id
                or item.deployment_id != self.deployment_id
                for item in self.descriptors
            )
            or len({item.expected_identity for item in self.descriptors}) != len(expected_roles)
            or len({ntpath.normcase(item.fixed_path) for item in self.descriptors})
            != len(expected_roles)
        ):
            raise ValueError("SOURCE_BUNDLE_BINDING")

    def descriptor_for(
        self, role: ProductionPrivateSourceRole
    ) -> _ProductionPrivateSourceDescriptor:
        if type(role) is not ProductionPrivateSourceRole:
            raise ProductionPrivateSourceFactoryDenied()
        for descriptor in self.descriptors:
            if descriptor.role is role:
                return descriptor
        raise ProductionPrivateSourceFactoryDenied()


class ProductionPrivateAuthoritySourceFactory:
    """Converts reviewed config bytes into descriptors; never opens a source."""

    def build(
        self,
        raw_configuration: bytes,
        *,
        expected: ProductionDeploymentExpectations,
    ) -> _ProductionPrivateSourceBundle:
        try:
            if type(self) is not ProductionPrivateAuthoritySourceFactory:
                raise ValueError("SOURCE_FACTORY_TYPE")
            configuration = parse_production_deployment_configuration(
                raw_configuration, expected=expected
            )
            configuration_digest = digest(raw_configuration)
            identities = {
                ProductionPrivateSourceRole.DESIGNATION_RECORD: configuration.deployment_id,
                ProductionPrivateSourceRole.PRIVATE_PIN_FACTS: configuration.installation_id,
                ProductionPrivateSourceRole.PROVISIONING_AUTHORITY_HISTORY: (
                    configuration.authority_source_id
                ),
                ProductionPrivateSourceRole.PROVISIONING_VERIFIER_MATERIAL: (
                    configuration.verifier_material_id
                ),
                ProductionPrivateSourceRole.ORIGINAL_CONFIRMATION: configuration.confirmation_id,
                ProductionPrivateSourceRole.LIVE_POLICY_LINEAGE: configuration.lineage_source_id,
            }
            if len(set(identities.values())) != len(identities):
                raise ValueError("SOURCE_IDENTITY_COLLISION")
            descriptors = tuple(
                _ProductionPrivateSourceDescriptor(
                    configuration_digest=configuration_digest,
                    installation_id=configuration.installation_id,
                    deployment_id=configuration.deployment_id,
                    role=role,
                    expected_identity=identities[role],
                    root=configuration.private_source_root,
                    fixed_filename=_ROLE_FILES[role],
                    fixed_path=ntpath.join(configuration.private_source_root, _ROLE_FILES[role]),
                    policy_domain=POLICY_DOMAIN,
                    provisioning_purpose=PURPOSE,
                    confirmation_signing_domain=CONFIRMATION_SIGNING_DOMAIN,
                )
                for role in ProductionPrivateSourceRole
            )
            return _ProductionPrivateSourceBundle(
                configuration_digest=configuration_digest,
                configuration_schema=CONFIGURATION_SCHEMA,
                configuration_version=CONFIGURATION_VERSION,
                configuration_profile=PRODUCTION_PROFILE,
                installation_id=configuration.installation_id,
                deployment_id=configuration.deployment_id,
                descriptors=descriptors,
                readiness=ProductionPrivateSourceReadiness.DESCRIPTORS_READY_SOURCES_UNPROVISIONED,
            )
        except ProductionPrivateSourceFactoryDenied:
            raise
        except Exception:
            raise ProductionPrivateSourceFactoryDenied() from None
