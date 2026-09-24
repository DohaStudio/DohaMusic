"""Reviewed production configuration is strict routing input, never authority."""

from dataclasses import replace

import pytest
import rfc8785

from backend.bootstrap_authority.production_configuration import (
    AUTHENTICATION_MECHANISM,
    AUTHENTICATION_PROOF_MODEL,
    CONFIGURATION_SCHEMA,
    CONFIRMATION_SIGNING_DOMAIN,
    JOURNAL_FILE,
    POLICY_DOMAIN,
    PRODUCTION_PROFILE,
    ProductionConfigurationDenied,
    ProductionDeploymentExpectations,
    parse_production_deployment_configuration,
)
from backend.bootstrap_authority.provisioning_authority import PURPOSE


def expectations():
    return ProductionDeploymentExpectations(
        installation_id="11111111-1111-4111-8111-111111111111",
        deployment_id="22222222-2222-4222-8222-222222222222",
        authority_source_id="33333333-3333-4333-8333-333333333333",
        verifier_material_id="44444444-4444-4444-8444-444444444444",
        confirmation_id="55555555-5555-4555-8555-555555555555",
        lineage_source_id="66666666-6666-4666-8666-666666666666",
        journal_id="77777777-7777-4777-8777-777777777777",
        authentication_provider_id="local-operator/windows-webauthn/v1",
    )


def payload():
    expected = expectations()
    return {
        "schema": CONFIGURATION_SCHEMA,
        "configuration_version": 1,
        "environment": "production",
        "profile": PRODUCTION_PROFILE,
        "installation_id": expected.installation_id,
        "deployment_id": expected.deployment_id,
        "private_source_root": r"D:\DohaMusicAuthority\Private",
        "designation_record_file": "designation-record-v1.txt",
        "pin_facts_file": "pin-comparison-facts-v1.json",
        "authority_source_id": expected.authority_source_id,
        "authority_source_file": "provisioning-authority-history-v1.json",
        "verifier_material_id": expected.verifier_material_id,
        "verifier_material_file": "provisioning-verifier-material-v1.json",
        "confirmation_id": expected.confirmation_id,
        "confirmation_file": "original-confirmation-v1.txt",
        "lineage_source_id": expected.lineage_source_id,
        "lineage_file": "policy-lineage-current-v1.json",
        "journal_id": expected.journal_id,
        "external_journal_path": rf"E:\DohaMusicJournal\{JOURNAL_FILE}",
        "journal_schema_version": 1,
        "policy_domain": POLICY_DOMAIN,
        "provisioning_purpose": PURPOSE,
        "confirmation_signing_domain": CONFIRMATION_SIGNING_DOMAIN,
        "authentication_provider_id": expected.authentication_provider_id,
        "authentication_proof_model": AUTHENTICATION_PROOF_MODEL,
        "authentication_mechanism": AUTHENTICATION_MECHANISM,
    }


def encoded(value=None):
    return rfc8785.dumps(payload() if value is None else value)


def test_exact_reviewed_configuration_parses_without_opening_or_activating_dependencies():
    config = parse_production_deployment_configuration(encoded(), expected=expectations())
    assert config.installation_id == expectations().installation_id
    assert config.external_journal_path.endswith(JOURNAL_FILE)
    assert len(config.private_source_files) == 6
    assert all(
        path.startswith(config.private_source_root + "\\") for path in config.private_source_files
    )


@pytest.mark.parametrize("field", tuple(payload()))
def test_missing_field_is_denied(field):
    value = payload()
    value.pop(field)
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=expectations())


def test_unknown_and_duplicate_fields_are_denied():
    value = payload()
    value["fallback"] = True
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=expectations())
    raw = encoded().replace(b'"schema":', b'"schema":"duplicate","schema":', 1)
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(raw, expected=expectations())


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("configuration_version", True),
        ("configuration_version", 2),
        ("environment", "development"),
        ("profile", "test"),
        ("journal_schema_version", True),
        ("policy_domain", "wrong/domain"),
        ("provisioning_purpose", "ANALYZE"),
        ("confirmation_signing_domain", "wrong-domain"),
        ("authentication_proof_model", "FAKE"),
        ("authentication_mechanism", "PASSWORD"),
        ("authority_source_file", "other.json"),
    ],
)
def test_wrong_profile_or_fixed_contract_is_denied(field, wrong):
    value = payload()
    value[field] = wrong
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=expectations())


@pytest.mark.parametrize(
    "field",
    [
        "installation_id",
        "deployment_id",
        "authority_source_id",
        "verifier_material_id",
        "confirmation_id",
        "lineage_source_id",
        "journal_id",
    ],
)
def test_wrong_reviewed_identity_is_denied(field):
    value = payload()
    value[field] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=expectations())


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("private_source_root", r"relative\authority"),
        ("private_source_root", r"d:\Authority"),
        ("private_source_root", r"D:\Authority\..\Escape"),
        ("private_source_root", r"\\server\share\Authority"),
        ("private_source_root", r"\\?\D:\Authority"),
        ("private_source_root", r"D:\tests\Authority"),
        ("private_source_root", r"D:\ProductionFixture\Authority"),
        ("private_source_root", "D:\\" + "a" * 230),
        ("external_journal_path", r"E:\Journal\other.sqlite3"),
        ("external_journal_path", r"E:\tmp\durable-admission-journal-v1.sqlite3"),
        ("external_journal_path", r"E:\Journal\name:stream"),
    ],
)
def test_unsafe_or_test_path_is_denied(field, path):
    value = payload()
    value[field] = path
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=expectations())


def test_private_source_and_external_journal_must_be_separate():
    value = payload()
    value["external_journal_path"] = rf"{value['private_source_root']}\Journal\{JOURNAL_FILE}"
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=expectations())


def test_noncanonical_utf8_and_non_bytes_are_denied():
    pretty = b'{"schema": "not-canonical"}'
    for raw in (pretty, b"\xff", bytearray(encoded())):
        with pytest.raises(ProductionConfigurationDenied):
            parse_production_deployment_configuration(raw, expected=expectations())


def test_expectation_subclass_and_authentication_substitution_are_denied():
    class HostileExpectations(ProductionDeploymentExpectations):
        pass

    base = expectations()
    hostile = HostileExpectations(**{item: getattr(base, item) for item in base.__slots__})
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(), expected=hostile)

    value = payload()
    value["authentication_provider_id"] = "local-operator/fake"
    with pytest.raises(ProductionConfigurationDenied):
        parse_production_deployment_configuration(encoded(value), expected=base)


def test_invalid_independent_expectations_fail_before_configuration_use():
    with pytest.raises(ValueError):
        replace(expectations(), journal_id="not-a-uuid")
