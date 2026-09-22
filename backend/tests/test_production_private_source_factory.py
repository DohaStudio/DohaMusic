"""Production private-source routing descriptors never become authority."""

from dataclasses import FrozenInstanceError

import pytest

from backend.bootstrap_authority.production_private_sources import (
    ProductionPrivateAuthoritySourceFactory,
    ProductionPrivateSourceFactoryDenied,
    ProductionPrivateSourceReadiness,
    ProductionPrivateSourceRole,
)
from backend.tests.test_production_deployment_configuration import encoded, expectations, payload


def build(value=None, expected=None):
    return ProductionPrivateAuthoritySourceFactory().build(
        encoded(payload() if value is None else value),
        expected=expectations() if expected is None else expected,
    )


def test_exact_six_role_descriptor_bundle_is_deterministic_and_unprovisioned():
    first, second = build(), build()
    assert first == second and first is not second
    assert (
        first.readiness is ProductionPrivateSourceReadiness.DESCRIPTORS_READY_SOURCES_UNPROVISIONED
    )
    assert tuple(item.role for item in first.descriptors) == tuple(ProductionPrivateSourceRole)
    assert len(first.descriptors) == 6
    assert len({item.expected_identity for item in first.descriptors}) == 6
    assert len({item.fixed_path.casefold() for item in first.descriptors}) == 6


def test_role_identity_and_fixed_filename_mapping_is_exact():
    bundle = build()
    expected = expectations()
    pairs = {
        ProductionPrivateSourceRole.DESIGNATION_RECORD: (
            expected.deployment_id,
            "designation-record-v1.txt",
        ),
        ProductionPrivateSourceRole.PRIVATE_PIN_FACTS: (
            expected.installation_id,
            "pin-comparison-facts-v1.json",
        ),
        ProductionPrivateSourceRole.PROVISIONING_AUTHORITY_HISTORY: (
            expected.authority_source_id,
            "provisioning-authority-history-v1.json",
        ),
        ProductionPrivateSourceRole.PROVISIONING_VERIFIER_MATERIAL: (
            expected.verifier_material_id,
            "provisioning-verifier-material-v1.json",
        ),
        ProductionPrivateSourceRole.ORIGINAL_CONFIRMATION: (
            expected.confirmation_id,
            "original-confirmation-v1.txt",
        ),
        ProductionPrivateSourceRole.LIVE_POLICY_LINEAGE: (
            expected.lineage_source_id,
            "policy-lineage-current-v1.json",
        ),
    }
    for role, (identity, filename) in pairs.items():
        descriptor = bundle.descriptor_for(role)
        assert descriptor.expected_identity == identity
        assert descriptor.fixed_filename == filename
        assert descriptor.fixed_path == rf"D:\DohaMusicAuthority\Private\{filename}"


def test_missing_files_are_not_created_or_opened(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("source factory attempted filesystem access")

    monkeypatch.setattr("builtins.open", forbidden)
    bundle = build()
    assert (
        bundle.readiness is ProductionPrivateSourceReadiness.DESCRIPTORS_READY_SOURCES_UNPROVISIONED
    )


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("installation_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("deployment_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("authority_source_id", "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        ("private_source_root", r"D:\tests\Authority"),
        ("private_source_root", r"d:\Authority"),
        ("private_source_root", r"\\server\share\Authority"),
        ("private_source_root", r"D:\Authority\..\Escape"),
        ("private_source_root", r"D:\Authority\name:stream"),
        ("authority_source_file", "other.json"),
    ],
)
def test_wrong_identity_path_or_filename_is_denied(field, wrong):
    value = payload()
    value[field] = wrong
    with pytest.raises(ProductionPrivateSourceFactoryDenied):
        build(value)


def test_duplicate_role_identity_is_denied():
    value = payload()
    value["verifier_material_id"] = value["authority_source_id"]
    expected = expectations()
    duplicate = type(expected)(
        installation_id=expected.installation_id,
        deployment_id=expected.deployment_id,
        authority_source_id=expected.authority_source_id,
        verifier_material_id=expected.authority_source_id,
        confirmation_id=expected.confirmation_id,
        lineage_source_id=expected.lineage_source_id,
        journal_id=expected.journal_id,
        authentication_provider_id=expected.authentication_provider_id,
    )
    with pytest.raises(ProductionPrivateSourceFactoryDenied):
        build(value, duplicate)


def test_wrong_role_and_factory_subclass_are_denied():
    bundle = build()
    with pytest.raises(ProductionPrivateSourceFactoryDenied):
        bundle.descriptor_for("DESIGNATION_RECORD")

    class HostileFactory(ProductionPrivateAuthoritySourceFactory):
        pass

    with pytest.raises(ProductionPrivateSourceFactoryDenied):
        HostileFactory().build(encoded(), expected=expectations())


def test_descriptors_are_immutable_and_have_no_authority_or_open_api():
    bundle = build()
    descriptor = bundle.descriptor_for(ProductionPrivateSourceRole.DESIGNATION_RECORD)
    with pytest.raises(FrozenInstanceError):
        descriptor.fixed_path = r"D:\replacement"
    for value in (bundle, descriptor):
        for name in ("open", "trusted", "authenticated", "current", "activate", "authorize"):
            assert not hasattr(value, name)
