"""ACTIVE verifier material source regression; never signing/admission tests."""

from __future__ import annotations

import base64
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from unittest.mock import Mock
from uuid import UUID

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.provisioning_authority import (
    CONFIRMATION_SIGNING_DOMAIN,
    PURPOSE,
    verify_provisioning_authority_history,
)
from backend.bootstrap_authority.provisioning_verifier_material import (
    MATERIAL_FILE,
    MATERIAL_SCHEMA,
    ExpectedProvisioningVerifierMaterial,
    ProvisioningVerifierMaterialDenied,
    _decode_material,
    _ProvisioningVerifierMaterialSnapshots,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_designation_source_custody import (
    process_account,
    provision_fixture_acl,
)
from backend.tests.test_provisioning_authority import _artifact, _payload
from backend.tests.test_provisioning_authority_source import (
    authority,
    root_fixture,
    setup_source,
    source_raw,
)


def uid(value):
    return str(UUID(int=value))


def active_history(authority_value, public_bytes):
    payload = _payload(
        authority_value,
        new_id="provisioner/material-v1",
        new_fingerprint=digest(public_bytes),
    )
    return (_artifact(authority_value, payload),)


def material_raw(authority_value, expected_source, public_bytes, **changes):
    events = active_history(authority_value, public_bytes)
    receipt = verify_provisioning_authority_history(
        events, root=authority_value[1], expected=authority_value[2]
    )
    expected = ExpectedProvisioningVerifierMaterial(uid(30), 1)
    value = {
        "schema": MATERIAL_SCHEMA,
        "algorithm": "Ed25519",
        "material_id": expected.material_id,
        "material_revision": expected.material_revision,
        "source_id": expected_source.source_id,
        "authorization_id": receipt.authorization_id,
        "authority_revision": receipt.semantic_revision,
        "authority_head_digest": receipt.head_event_digest,
        "installation_id": receipt.installation_id,
        "producer_ref": receipt.producer_ref,
        "purpose": PURPOSE,
        "confirmation_signing_domain": CONFIRMATION_SIGNING_DOMAIN,
        "verifier_key_id": receipt.current_verifier_key_id,
        "verifier_fingerprint": receipt.current_verifier_fingerprint,
        "public_key": base64.urlsafe_b64encode(public_bytes).rstrip(b"=").decode(),
    }
    value.update(changes)
    return rfc8785.dumps(value), expected, receipt, events


def setup_material(tmp_path, authority_reader, source_policy, raw):
    path = tmp_path / MATERIAL_FILE
    path.write_bytes(raw)
    provision_fixture_acl(path, process_account())
    files = _WindowsFactFiles(str(tmp_path))
    handle = files._open(str(path), directory=False)
    try:
        identity = files._check(handle, str(path), directory=False)[:2]
    finally:
        files._close([handle])
    policy = replace(source_policy, record_identity=identity)
    reader = _ProvisioningVerifierMaterialSnapshots(
        trusted_root=str(tmp_path),
        authority_snapshots=authority_reader,
        material_policy=policy,
    )
    return reader, path, policy


def test_strict_material_codec_binds_every_authority_and_source_fact():
    root_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    verifier_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    public = verifier_key.public_key().public_bytes_raw()
    from backend.tests.test_bootstrap_witness_lifetime import binding

    current = replace(
        binding(),
        root_public_key=root_key.public_key().public_bytes_raw(),
        root_fingerprint=digest(root_key.public_key().public_bytes_raw()),
    )
    auth = authority(root_key, current)
    source, expected_source = source_raw(auth, events=active_history(auth, public))
    del source
    raw, expected_material, receipt, _ = material_raw(auth, expected_source, public)
    verified = _decode_material(
        raw,
        expected_material=expected_material,
        expected_source=expected_source,
        expected_scope=auth[2],
        authority_receipt=receipt,
    )
    assert verified.public_key == public
    assert verified.verifier_fingerprint == digest(public)
    for field, value in (
        ("material_revision", True),
        ("source_id", uid(999)),
        ("authorization_id", uid(998)),
        ("authority_head_digest", digest(b"fork")),
        ("installation_id", uid(997)),
        ("producer_ref", "producer/other"),
        ("purpose", "FIRST_OWNER_BINDING_ONLY"),
        ("confirmation_signing_domain", "DohaMusicDeploymentBootstrapApprovalV1"),
        ("verifier_key_id", "provisioner/old"),
        ("verifier_fingerprint", digest(b"wrong")),
        ("public_key", base64.urlsafe_b64encode(bytes(32)).rstrip(b"=").decode()),
    ):
        bad, *_ = material_raw(auth, expected_source, public, **{field: value})
        with pytest.raises(ValueError):
            _decode_material(
                bad,
                expected_material=expected_material,
                expected_source=expected_source,
                expected_scope=auth[2],
                authority_receipt=receipt,
            )


def test_malformed_duplicate_noncanonical_and_parallel_verification():
    root_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    verifier_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    public = verifier_key.public_key().public_bytes_raw()
    from backend.tests.test_bootstrap_witness_lifetime import binding

    current = replace(
        binding(),
        root_public_key=root_key.public_key().public_bytes_raw(),
        root_fingerprint=digest(root_key.public_key().public_bytes_raw()),
    )
    auth = authority(root_key, current)
    _, expected_source = source_raw(auth, events=active_history(auth, public))
    raw, expected_material, receipt, _ = material_raw(auth, expected_source, public)

    def verify():
        return _decode_material(
            raw,
            expected_material=expected_material,
            expected_source=expected_source,
            expected_scope=auth[2],
            authority_receipt=receipt,
        )

    with ThreadPoolExecutor(8) as pool:
        assert len({item.material_digest for item in pool.map(lambda _: verify(), range(32))}) == 1
    for malformed in (
        b"",
        b"\xff",
        b"{}",
        b'{"schema":"a","schema":"b"}',
        json.dumps(json.loads(raw), indent=2).encode(),
        b"x" * 16_385,
    ):
        with pytest.raises((ValueError, UnicodeError)):
            _decode_material(
                malformed,
                expected_material=expected_material,
                expected_source=expected_source,
                expected_scope=auth[2],
                authority_receipt=receipt,
            )


@pytest.mark.parametrize("attack", ["material", "scope", "transaction", "stale_material"])
def test_native_active_authority_to_material_handoff_and_stale_reuse_denial(tmp_path, attack):
    if not native():
        return
    with root_fixture(tmp_path) as (fx, root_key, binding):
        verifier_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        public = verifier_key.public_key().public_bytes_raw()
        auth = authority(root_key, binding)
        events = active_history(auth, public)
        source_bytes, expected_source = source_raw(auth, events=events)
        authority_reader, designation, _, _, source_policy = setup_source(
            tmp_path, fx, source_bytes
        )
        raw, expected_material, _, _ = material_raw(auth, expected_source, public)
        reader, path, _ = setup_material(tmp_path, authority_reader, source_policy, raw)
        args = fx[1]
        with (
            fx[0]._open_facts(**args) as facts,
            designation._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as designation_handle,
            authority_reader._open_source(
                designation_handle=designation_handle,
                lease=args["lease"],
                session=args["session"],
                pin_facts=facts,
                expected_source=expected_source,
                expected_scope=auth[2],
            ) as authority_handle,
        ):
            open_args = dict(
                authority_handle=authority_handle,
                designation_handle=designation_handle,
                lease=args["lease"],
                session=args["session"],
                pin_facts=facts,
                expected_source=expected_source,
                expected_scope=auth[2],
                expected_material=expected_material,
            )
            with reader._open_material(**open_args) as handle:
                reader._require_open(handle, **open_args)
                if attack == "material":
                    with pytest.raises(OSError):
                        path.write_bytes(raw)
                    open_args["expected_material"] = replace(
                        expected_material, material_id=uid(999)
                    )
                elif attack == "scope":
                    open_args["expected_scope"] = replace(auth[2], producer_ref="producer/other")
                elif attack == "transaction":
                    args["session"].rollback()
                    args["session"].begin()
                else:
                    open_args["expected_material"] = replace(expected_material, material_revision=2)
                with pytest.raises(ProvisioningVerifierMaterialDenied):
                    reader._require_open(handle, **open_args)
                with pytest.raises(ProvisioningVerifierMaterialDenied):
                    reader._require_open(handle, **open_args)
        assert not reader._records


def test_superseded_material_cannot_substitute_rotated_active_material():
    root_key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    first_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    second_key = Ed25519PrivateKey.from_private_bytes(bytes(range(1, 33)))
    first_public = first_key.public_key().public_bytes_raw()
    second_public = second_key.public_key().public_bytes_raw()
    from backend.tests.test_bootstrap_witness_lifetime import binding

    root_public = root_key.public_key().public_bytes_raw()
    current = replace(binding(), root_public_key=root_public, root_fingerprint=digest(root_public))
    auth = authority(root_key, current)
    first = _artifact(
        auth,
        _payload(
            auth,
            new_id="provisioner/material-v1",
            new_fingerprint=digest(first_public),
        ),
    )
    second = _artifact(
        auth,
        _payload(
            auth,
            revision=2,
            previous=digest(first),
            kind="ROTATE",
            old_id="provisioner/material-v1",
            old_fingerprint=digest(first_public),
            new_id="provisioner/material-v2",
            new_fingerprint=digest(second_public),
        ),
    )
    events = (first, second)
    _, expected_source = source_raw(auth, events=events)
    receipt = verify_provisioning_authority_history(events, root=auth[1], expected=auth[2])
    raw, expected_material, _, _ = material_raw(auth, expected_source, second_public)
    value = json.loads(raw)
    value.update(
        verifier_key_id="provisioner/material-v2",
        verifier_fingerprint=digest(second_public),
        authority_revision=2,
        authority_head_digest=receipt.head_event_digest,
        public_key=base64.urlsafe_b64encode(second_public).rstrip(b"=").decode(),
    )
    raw = rfc8785.dumps(value)
    assert (
        _decode_material(
            raw,
            expected_material=expected_material,
            expected_source=expected_source,
            expected_scope=auth[2],
            authority_receipt=receipt,
        ).public_key
        == second_public
    )
    value["public_key"] = base64.urlsafe_b64encode(first_public).rstrip(b"=").decode()
    with pytest.raises(ValueError):
        _decode_material(
            rfc8785.dumps(value),
            expected_material=expected_material,
            expected_source=expected_source,
            expected_scope=auth[2],
            authority_receipt=receipt,
        )


@pytest.mark.parametrize("raised", [False, True])
def test_material_close_failure_quarantines_transport_and_abandons_chain(
    tmp_path, monkeypatch, raised
):
    if not native():
        return
    with root_fixture(tmp_path) as (fx, root_key, binding):
        verifier_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        public = verifier_key.public_key().public_bytes_raw()
        auth = authority(root_key, binding)
        events = active_history(auth, public)
        source_bytes, expected_source = source_raw(auth, events=events)
        authority_reader, designation, _, _, source_policy = setup_source(
            tmp_path, fx, source_bytes
        )
        raw, expected_material, _, _ = material_raw(auth, expected_source, public)
        reader, _, _ = setup_material(tmp_path, authority_reader, source_policy, raw)
        args = fx[1]
        original = reader._files._api.CloseHandle
        with (
            fx[0]._open_facts(**args) as facts,
            designation._open_record(
                lease=args["lease"], session=args["session"], pin_facts=facts
            ) as designation_handle,
            authority_reader._open_source(
                designation_handle=designation_handle,
                lease=args["lease"],
                session=args["session"],
                pin_facts=facts,
                expected_source=expected_source,
                expected_scope=auth[2],
            ) as authority_handle,
        ):
            open_args = dict(
                authority_handle=authority_handle,
                designation_handle=designation_handle,
                lease=args["lease"],
                session=args["session"],
                pin_facts=facts,
                expected_source=expected_source,
                expected_scope=auth[2],
                expected_material=expected_material,
            )
            with (
                pytest.raises(ProvisioningVerifierMaterialDenied),
                reader._open_material(**open_args) as handle,
            ):
                reader._require_open(handle, **open_args)
                monkeypatch.setattr(
                    reader._files._api,
                    "CloseHandle",
                    Mock(side_effect=OSError("injected")) if raised else Mock(return_value=0),
                )
            assert reader._files._quarantine
            assert not reader._records and not authority_reader._records
            with (
                pytest.raises(ProvisioningVerifierMaterialDenied),
                reader._open_material(**open_args),
            ):
                pass
            with pytest.raises(PrivateFactsDenied):
                reader._files._cleanup_failed_snapshots()
            assert reader._files._quarantine
            monkeypatch.setattr(reader._files._api, "CloseHandle", original)
            reader._files._cleanup_failed_snapshots()
            assert not reader._files._quarantine


def test_held_material_has_no_sign_or_authority_api():
    for target in (ExpectedProvisioningVerifierMaterial, ProvisioningVerifierMaterialDenied):
        for attribute in ("sign", "admit", "authorize", "currentness_witness"):
            assert not hasattr(target, attribute)
