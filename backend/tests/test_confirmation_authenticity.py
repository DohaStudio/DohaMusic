"""Original Confirmation authenticity regression with disposable keys only."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace

import pytest
import rfc8785
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.bootstrap_authority.confirmation_authenticity import (
    SIGNATURE_DOMAIN,
    OriginalConfirmationAuthenticityDenied,
    _decode_signature,
    _OriginalConfirmationAuthenticity,
    _verify_signature,
)
from backend.bootstrap_authority.confirmation_payload import (
    CONFIRMATION_ALGORITHM,
    CONFIRMATION_SCHEMA,
    CONFIRMATION_SCOPE,
    ExpectedConfirmationPayload,
)
from backend.bootstrap_authority.confirmation_snapshot import (
    CONFIRMATION_RECORD_FILE,
    _OriginalConfirmationSnapshots,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.provisioning_authority import SIGNATURE_DOMAIN as AUTHORITY_DOMAIN
from backend.bootstrap_authority.provisioning_binding import (
    InitializerConfirmationFacts,
    PolicyLineageFacts,
    PolicySnapshotFacts,
    ProvisioningActionFacts,
    policy_snapshot_digest,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.tests.test_bootstrap_pin_facts import INSTALLATION_FP
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_designation_source_custody import (
    process_account,
    provision_fixture_acl,
)
from backend.tests.test_provisioning_authority_source import (
    authority,
    root_fixture,
    setup_source,
    source_raw,
    uid,
)
from backend.tests.test_provisioning_verifier_material import (
    active_history,
    material_raw,
    setup_material,
)


def signature_text(key, message):
    return base64.urlsafe_b64encode(key.sign(message)).rstrip(b"=").decode("ascii")


def confirmation_raw(expected):
    return rfc8785.dumps(
        {
            "schema": CONFIRMATION_SCHEMA,
            "algorithm": CONFIRMATION_ALGORITHM,
            "confirmation_id": expected.confirmation_id,
            "original_confirmation_ref": expected.original_confirmation_ref,
            "initializer_ref": expected.initializer_ref,
            "installation_id": expected.installation_id,
            "installation_proof_key_fingerprint": expected.installation_proof_key_fingerprint,
            "action_id": expected.action_id,
            "policy_digest": expected.policy_digest,
            "designation_digest": expected.designation_digest,
            "scope": CONFIRMATION_SCOPE,
            "verifier_key_id": expected.verifier_key_id,
            "verifier_fingerprint": expected.verifier_fingerprint,
            "replay_id": expected.replay_id,
        }
    )


def setup_confirmation(tmp_path, fx, designation, raw):
    path = tmp_path / CONFIRMATION_RECORD_FILE
    path.write_bytes(raw)
    provision_fixture_acl(path, process_account())
    files = _WindowsFactFiles(str(tmp_path))
    handle = files._open(str(path), directory=False)
    try:
        identity = files._check(handle, str(path), directory=False)[:2]
    finally:
        files._close([handle])
    policy = replace(designation._files._policy, record_identity=identity)
    return (
        _OriginalConfirmationSnapshots(
            trusted_root=str(tmp_path),
            pin_reader=fx[0],
            designation_snapshots=designation,
            confirmation_policy=policy,
        ),
        path,
    )


@contextmanager
def live_authenticity(tmp_path):
    with root_fixture(tmp_path) as (fx, root_key, binding):
        verifier_key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
        public = verifier_key.public_key().public_bytes_raw()
        auth = authority(root_key, binding)
        events = active_history(auth, public)
        source_bytes, expected_source = source_raw(auth, events=events)
        authority_reader, designation, _, _, source_policy = setup_source(
            tmp_path, fx, source_bytes
        )
        material_bytes, expected_material, _, _ = material_raw(auth, expected_source, public)
        material_reader, material_path, _ = setup_material(
            tmp_path, authority_reader, source_policy, material_bytes
        )
        args = fx[1]
        with fx[0]._open_facts(**args) as facts:
            policy = PolicySnapshotFacts(
                uid(50),
                1,
                auth[2].installation_id,
                INSTALLATION_FP,
                uid(51),
                designation._files._policy,
            )
            expected_payload = ExpectedConfirmationPayload(
                uid(100),
                "original/test",
                auth[2].producer_ref,
                auth[2].installation_id,
                INSTALLATION_FP,
                uid(200),
                policy_snapshot_digest(policy),
                facts.binding.designation_record_digest,
                "provisioner/material-v1",
                digest(public),
                uid(300),
            )
            raw = confirmation_raw(expected_payload)
            confirmation = InitializerConfirmationFacts(
                expected_payload.confirmation_id,
                expected_payload.original_confirmation_ref,
                digest(raw),
                expected_payload.initializer_ref,
                expected_payload.action_id,
                expected_payload.policy_digest,
                facts,
            )
            action = ProvisioningActionFacts(expected_payload.action_id, policy, confirmation, None)
            lineage = PolicyLineageFacts(
                uid(52), auth[2].installation_id, uid(51), (action,), ("ACTIVE",)
            )
            confirmation_reader, confirmation_path = setup_confirmation(
                tmp_path, fx, designation, raw
            )
            verifier = _OriginalConfirmationAuthenticity(
                confirmation_snapshots=confirmation_reader,
                material_snapshots=material_reader,
            )
            signature = signature_text(verifier_key, SIGNATURE_DOMAIN + raw)
            with (
                designation._open_record(
                    lease=args["lease"], session=args["session"], pin_facts=facts
                ) as designation_handle,
                confirmation_reader._open_snapshot(
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    designation=designation_handle,
                    action=action,
                    lineage=lineage,
                ) as confirmation_handle,
                authority_reader._open_source(
                    designation_handle=designation_handle,
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    expected_source=expected_source,
                    expected_scope=auth[2],
                ) as authority_handle,
                material_reader._open_material(
                    authority_handle=authority_handle,
                    designation_handle=designation_handle,
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    expected_source=expected_source,
                    expected_scope=auth[2],
                    expected_material=expected_material,
                ) as material_handle,
            ):
                call = dict(
                    confirmation_handle=confirmation_handle,
                    material_handle=material_handle,
                    authority_handle=authority_handle,
                    designation_handle=designation_handle,
                    lease=args["lease"],
                    session=args["session"],
                    pin_facts=facts,
                    fresh_action=action,
                    fresh_lineage=lineage,
                    expected_payload=expected_payload,
                    expected_material=expected_material,
                    expected_source=expected_source,
                    expected_scope=auth[2],
                    signature_text=signature,
                )
                yield (
                    verifier,
                    call,
                    raw,
                    verifier_key,
                    confirmation_path,
                    material_path,
                    confirmation_reader,
                    material_reader,
                    authority_reader,
                    designation,
                )


def test_signature_codec_domain_and_parallel_verification():
    key = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    public, raw = key.public_key().public_bytes_raw(), b'{"canonical":"payload"}'
    signature = signature_text(key, SIGNATURE_DOMAIN + raw)
    assert len(_decode_signature(signature)) == 64
    with ThreadPoolExecutor(8) as pool:
        assert (
            len(set(pool.map(lambda _: _verify_signature(public, signature, raw), range(64)))) == 1
        )
    for invalid in (
        signature[:-1],
        signature + "=",
        signature_text(key, AUTHORITY_DOMAIN + raw),
        signature_text(key, b"DohaMusicDeploymentBootstrapApprovalV1\x00" + raw),
        signature_text(
            Ed25519PrivateKey.from_private_bytes(bytes(range(32))), SIGNATURE_DOMAIN + raw
        ),
    ):
        with pytest.raises((ValueError, InvalidSignature)):
            _verify_signature(public, invalid, raw)


def test_native_exact_authenticity_handoff_is_opaque_and_non_authorizing(tmp_path):
    if not native():
        return
    with live_authenticity(tmp_path) as values:
        verifier, call, raw, _, confirmation_path, material_path, *_ = values
        with verifier._open_authenticity(**call) as handle:
            verifier._require_open(handle, **call)
            record = verifier._records[handle].verified
            assert record.payload_digest == digest(raw)
            assert record.verifier_key_id == call["expected_payload"].verifier_key_id
            assert record.authority_head_digest == call["expected_source"].head_event_digest
            assert record.material_id == call["expected_material"].material_id
            assert record.lineage_anchor_id == call["fresh_lineage"].anchor_id
            assert record.lineage_source_id == call["fresh_lineage"].source_id
            for name in ("admit", "authorize", "currentness_witness", "sign", "public_key"):
                assert not hasattr(handle, name)
            with pytest.raises(OSError):
                confirmation_path.write_bytes(raw)
            with pytest.raises(OSError):
                material_path.write_bytes(material_path.read_bytes())


@pytest.mark.parametrize(
    "attack",
    [
        "invalid-signature",
        "cross-domain",
        "wrong-key",
        "wrong-verifier-id",
        "wrong-fingerprint",
        "wrong-installation",
        "wrong-producer",
    ],
)
def test_native_signature_and_exact_binding_attacks_abandon_all_parents(tmp_path, attack):
    if not native():
        return
    with live_authenticity(tmp_path) as values:
        verifier, call, raw, key, _, _, confirmation, material, authority_reader, designation = (
            values
        )
        if attack == "invalid-signature":
            call["signature_text"] = "A" * 86
        elif attack == "cross-domain":
            call["signature_text"] = signature_text(key, AUTHORITY_DOMAIN + raw)
        elif attack == "wrong-key":
            other = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
            call["signature_text"] = signature_text(other, SIGNATURE_DOMAIN + raw)
        elif attack == "wrong-verifier-id":
            call["expected_payload"] = replace(
                call["expected_payload"], verifier_key_id="provisioner/other"
            )
        elif attack == "wrong-fingerprint":
            call["expected_payload"] = replace(
                call["expected_payload"], verifier_fingerprint=digest(b"other")
            )
        elif attack == "wrong-installation":
            call["expected_scope"] = replace(call["expected_scope"], installation_id=uid(999))
        else:
            call["expected_scope"] = replace(
                call["expected_scope"], producer_ref="initializer/other"
            )
        with (
            pytest.raises(OriginalConfirmationAuthenticityDenied),
            verifier._open_authenticity(**call),
        ):
            pytest.fail("invalid authenticity input became usable")
        assert not verifier._records
        assert not confirmation._records and not material._records
        assert not authority_reader._records and not designation._snapshots


@pytest.mark.parametrize("attack", ["signature", "payload", "material", "transaction"])
def test_native_stale_authenticity_handle_never_reactivates(tmp_path, attack):
    if not native():
        return
    with live_authenticity(tmp_path) as values:
        verifier, call, *_ = values
        original = dict(call)
        with verifier._open_authenticity(**call) as handle:
            verifier._require_open(handle, **call)
            if attack == "signature":
                call["signature_text"] = "A" * 86
            elif attack == "payload":
                call["expected_payload"] = replace(call["expected_payload"], replay_id=uid(999))
            elif attack == "material":
                call["expected_material"] = replace(call["expected_material"], material_revision=2)
            else:
                call["session"].rollback()
                call["session"].begin()
            with pytest.raises(OriginalConfirmationAuthenticityDenied):
                verifier._require_open(handle, **call)
            with pytest.raises(OriginalConfirmationAuthenticityDenied):
                verifier._require_open(handle, **original)
        assert not verifier._records


def test_public_api_does_not_expose_result_or_signing_capability():
    for target in (OriginalConfirmationAuthenticityDenied,):
        for name in ("authenticated", "verify", "sign", "admit", "authorize", "currentness"):
            assert not hasattr(target, name)
