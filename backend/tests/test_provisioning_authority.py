"""ADR-093 disposable scoped-authority integrity and negative tests."""

from __future__ import annotations

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from uuid import UUID

import pytest
import rfc8785
from cryptography.exceptions import UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from backend.bootstrap_authority import provisioning_authority as module
from backend.bootstrap_authority.contracts import PinnedRootVerifier
from backend.bootstrap_authority.provisioning_authority import (
    CONFIRMATION_SIGNING_DOMAIN,
    LINEAGE_SIGNING_DOMAIN,
    POLICY_DOMAIN,
    PURPOSE,
    SCHEMA,
    SIGNATURE_DOMAIN,
    ExpectedProvisioningAuthorityScope,
    ProvisioningAuthorityDenied,
    verify_provisioning_authority_history,
)


def _uuid(number: int) -> str:
    return str(UUID(int=number))


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


_DEFAULT_FINGERPRINT = object()


@pytest.fixture
def authority():
    # In-memory deterministic disposable material, never a production credential.
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = key.public_key().public_bytes_raw()
    root = PinnedRootVerifier(
        root_key_id="root/disposable-v1",
        designation_id=_uuid(2),
        deployment_owner_ref="deployment/disposable-owner",
        designation_digest=_digest(b"designation"),
        public_key_fingerprint=_digest(public),
        public_key=public,
    )
    expected = ExpectedProvisioningAuthorityScope(
        authorization_id=_uuid(10),
        installation_id=_uuid(11),
        producer_ref="initializer/disposable-producer",
        governance_provenance_digest=_digest(b"governance decision"),
    )
    return key, root, expected


def _payload(
    authority,
    *,
    revision=1,
    previous=None,
    kind="AUTHORIZE",
    old_id=None,
    old_fingerprint=None,
    new_id="provisioner/key-v1",
    new_fingerprint=_DEFAULT_FINGERPRINT,
):
    _, root, expected = authority
    return {
        "schema": SCHEMA,
        "algorithm": "Ed25519",
        "authorization_id": expected.authorization_id,
        "event_id": _uuid(100 + revision),
        "semantic_revision": revision,
        "previous_event_digest": previous,
        "event_kind": kind,
        "root_key_id": root.root_key_id,
        "designation_id": root.designation_id,
        "deployment_owner_ref": root.deployment_owner_ref,
        "designation_digest": root.designation_digest,
        "installation_id": expected.installation_id,
        "producer_ref": expected.producer_ref,
        "purpose": PURPOSE,
        "confirmation_signing_domain": CONFIRMATION_SIGNING_DOMAIN,
        "lineage_signing_domain": LINEAGE_SIGNING_DOMAIN,
        "policy_domain": POLICY_DOMAIN,
        "old_verifier_key_id": old_id,
        "old_verifier_fingerprint": old_fingerprint,
        "new_verifier_key_id": new_id,
        "new_verifier_fingerprint": (
            _digest(b"verifier v1") if new_fingerprint is _DEFAULT_FINGERPRINT else new_fingerprint
        ),
        "governance_provenance_digest": expected.governance_provenance_digest,
    }


def _artifact(authority, payload, *, domain=SIGNATURE_DOMAIN, signer=None):
    key = authority[0] if signer is None else signer
    signature = key.sign(domain + rfc8785.dumps(payload))
    return rfc8785.dumps(
        {
            "payload": payload,
            "signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
        }
    )


def _authorize(authority):
    return _artifact(authority, _payload(authority))


def _rotate(authority, previous, *, new_id="provisioner/key-v2", new_bytes=b"verifier v2"):
    return _artifact(
        authority,
        _payload(
            authority,
            revision=2,
            previous=_digest(previous),
            kind="ROTATE",
            old_id="provisioner/key-v1",
            old_fingerprint=_digest(b"verifier v1"),
            new_id=new_id,
            new_fingerprint=_digest(new_bytes),
        ),
    )


def _revoke(authority, authorize, rotate):
    return _artifact(
        authority,
        _payload(
            authority,
            revision=3,
            previous=_digest(rotate),
            kind="REVOKE",
            old_id="provisioner/key-v2",
            old_fingerprint=_digest(b"verifier v2"),
            new_id=None,
            new_fingerprint=None,
        ),
    )


def _verify(authority, artifacts):
    return verify_provisioning_authority_history(
        artifacts, root=authority[1], expected=authority[2]
    )


def _deny(authority, artifacts, **kwargs):
    with pytest.raises(ProvisioningAuthorityDenied) as caught:
        verify_provisioning_authority_history(
            artifacts,
            root=kwargs.get("root", authority[1]),
            expected=kwargs.get("expected", authority[2]),
        )
    assert str(caught.value) == "PROVISIONING_AUTHORITY_DENIED"
    assert caught.value.__cause__ is None


def test_authorize_yields_immutable_non_capability_integrity_receipt(authority):
    receipt = _verify(authority, (_authorize(authority),))
    assert receipt.lifecycle_state == "ACTIVE"
    assert receipt.semantic_revision == 1
    assert receipt.current_verifier_key_id == "provisioner/key-v1"
    assert receipt.verifier_history[0].status == "ACTIVE"
    with pytest.raises(FrozenInstanceError):
        receipt.lifecycle_state = "REVOKED"
    for attribute in ("admit", "authorize", "currentness_witness", "verify_confirmation"):
        assert not hasattr(receipt, attribute)


def test_rotation_and_revocation_have_explicit_terminal_projection(authority):
    first = _authorize(authority)
    second = _rotate(authority, first)
    active = _verify(authority, (first, second))
    assert [(item.key_id, item.status) for item in active.verifier_history] == [
        ("provisioner/key-v1", "SUPERSEDED"),
        ("provisioner/key-v2", "ACTIVE"),
    ]
    third = _revoke(authority, first, second)
    revoked = _verify(authority, (first, second, third))
    assert revoked.lifecycle_state == "REVOKED"
    assert revoked.current_verifier_key_id is None
    assert revoked.verifier_history[-1].status == "REVOKED"


def test_wire_order_and_whitespace_do_not_change_jcs_verification(authority):
    artifact = _authorize(authority)
    envelope = json.loads(artifact)
    envelope["payload"] = dict(reversed(tuple(envelope["payload"].items())))
    noncanonical_wire = json.dumps(envelope, indent=2).encode()
    assert _verify(authority, (noncanonical_wire,)) == _verify(authority, (artifact,))


@pytest.mark.parametrize(
    "field,value",
    [
        ("purpose", "FIRST_OWNER_BINDING_ONLY"),
        ("confirmation_signing_domain", "DohaMusicDeploymentBootstrapApprovalV1"),
        ("lineage_signing_domain", "DohaMusicOriginalInitializerConfirmationV1"),
        ("policy_domain", "dohamusic/rights/v1"),
        ("installation_id", _uuid(999)),
        ("producer_ref", "initializer/other"),
        ("authorization_id", _uuid(998)),
        ("root_key_id", "root/other"),
        ("designation_id", _uuid(997)),
        ("governance_provenance_digest", _digest(b"other decision")),
    ],
)
def test_exact_scope_purpose_and_domains_cannot_be_rebound(authority, field, value):
    payload = {**_payload(authority), field: value}
    _deny(authority, (_artifact(authority, payload),))


@pytest.mark.parametrize(
    "domain",
    [
        b"",
        b"DohaMusicDeploymentBootstrapApprovalV1\x00",
        b"DohaMusicOriginalInitializerConfirmationV1\x00",
        b"DohaMusicScopedProvisioningAuthorityEventV1",
    ],
)
def test_cross_domain_replay_is_denied(authority, domain):
    _deny(authority, (_artifact(authority, _payload(authority), domain=domain),))


def test_wrong_root_or_signature_substitution_is_denied(authority):
    other = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32))))
    raw = other.public_key().public_bytes_raw()
    _deny(authority, (_artifact(authority, _payload(authority), signer=other),))
    _deny(
        authority,
        (_authorize(authority),),
        root=replace(authority[1], public_key=raw, public_key_fingerprint=_digest(raw)),
    )


@pytest.mark.parametrize(
    "change",
    [
        "stale_revision",
        "wrong_previous",
        "wrong_predecessor",
        "key_id_reuse",
        "fingerprint_reuse",
        "authorize_twice",
    ],
)
def test_stale_rotation_wrong_predecessor_and_old_key_reuse_denied(authority, change):
    first = _authorize(authority)
    payload = _payload(
        authority,
        revision=2,
        previous=_digest(first),
        kind="ROTATE",
        old_id="provisioner/key-v1",
        old_fingerprint=_digest(b"verifier v1"),
        new_id="provisioner/key-v2",
        new_fingerprint=_digest(b"verifier v2"),
    )
    if change == "stale_revision":
        payload["semantic_revision"] = 1
    elif change == "wrong_previous":
        payload["previous_event_digest"] = _digest(b"fork")
    elif change == "wrong_predecessor":
        payload["old_verifier_key_id"] = "provisioner/wrong"
    elif change == "key_id_reuse":
        payload["new_verifier_key_id"] = "provisioner/key-v1"
    elif change == "fingerprint_reuse":
        payload["new_verifier_fingerprint"] = _digest(b"verifier v1")
    elif change == "authorize_twice":
        payload["event_kind"] = "AUTHORIZE"
        payload["old_verifier_key_id"] = None
        payload["old_verifier_fingerprint"] = None
    _deny(authority, (first, _artifact(authority, payload)))


def test_superseded_key_cannot_be_rotated_back_into_service(authority):
    first = _authorize(authority)
    second = _rotate(authority, first)
    replay = _artifact(
        authority,
        _payload(
            authority,
            revision=3,
            previous=_digest(second),
            kind="ROTATE",
            old_id="provisioner/key-v2",
            old_fingerprint=_digest(b"verifier v2"),
            new_id="provisioner/key-v1",
            new_fingerprint=_digest(b"verifier v1"),
        ),
    )
    _deny(authority, (first, second, replay))


def test_event_identity_cannot_be_reused_across_revisions(authority):
    first = _authorize(authority)
    payload = _payload(
        authority,
        revision=2,
        previous=_digest(first),
        kind="ROTATE",
        old_id="provisioner/key-v1",
        old_fingerprint=_digest(b"verifier v1"),
        new_id="provisioner/key-v2",
        new_fingerprint=_digest(b"verifier v2"),
    )
    payload["event_id"] = _uuid(101)
    _deny(authority, (first, _artifact(authority, payload)))


def test_revoked_chain_cannot_reactivate_or_accept_successor(authority):
    first = _authorize(authority)
    second = _rotate(authority, first)
    third = _revoke(authority, first, second)
    reactivation = _artifact(
        authority,
        _payload(
            authority,
            revision=4,
            previous=_digest(third),
            kind="ROTATE",
            old_id="provisioner/key-v2",
            old_fingerprint=_digest(b"verifier v2"),
            new_id="provisioner/key-v3",
            new_fingerprint=_digest(b"verifier v3"),
        ),
    )
    _deny(authority, (first, second, third, reactivation))


@pytest.mark.parametrize(
    "field,value",
    [
        ("semantic_revision", True),
        ("semantic_revision", 0),
        ("event_kind", "SUPERSEDE"),
        ("new_verifier_key_id", "*"),
        ("new_verifier_fingerprint", "sha256:" + "A" * 64),
        ("producer_ref", "../producer"),
        ("installation_id", _uuid(11).upper()),
        ("schema", "dohamusic/scoped-provisioning-authority-event/v2"),
        ("algorithm", "none"),
    ],
)
def test_strict_types_identifiers_and_wire_contract(authority, field, value):
    payload = {**_payload(authority), field: value}
    _deny(authority, (_artifact(authority, payload),))


def test_float_revision_is_rejected_from_raw_wire_before_signature_check(authority):
    artifact = _authorize(authority)
    changed = artifact.replace(b'"semantic_revision":1', b'"semantic_revision":1.0')
    assert changed != artifact
    _deny(authority, (changed,))


@pytest.mark.parametrize(
    "artifact",
    [
        b"",
        b"\xff",
        b"{}",
        b"[]",
        b"{" * 1000,
        b"x" * 16_385,
        b'{"payload":{},"payload":{},"signature":""}',
        b'{"payload":1.5,"signature":""}',
        b'{"payload":NaN,"signature":""}',
    ],
)
def test_malformed_duplicate_and_nonfinite_input_fail_closed(authority, artifact):
    _deny(authority, (artifact,))


def test_payload_tamper_and_signature_encoding_fail_closed(authority):
    envelope = json.loads(_authorize(authority))
    envelope["payload"]["producer_ref"] = "initializer/attacker"
    _deny(authority, (json.dumps(envelope).encode(),))
    envelope = json.loads(_authorize(authority))
    envelope["signature"] = envelope["signature"] + "="
    _deny(authority, (json.dumps(envelope).encode(),))


def test_expected_scope_requires_exact_builtin_strings(authority):
    class Hostile(str):
        def __eq__(self, other):
            raise AssertionError("hostile equality called")

        __hash__ = str.__hash__

    with pytest.raises(ValueError):
        replace(authority[2], producer_ref=Hostile(authority[2].producer_ref))


def test_parallel_verification_is_deterministic_and_does_not_mutate(authority):
    first = _authorize(authority)
    second = _rotate(authority, first)
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(lambda _: _verify(authority, (first, second)), range(32)))
    assert all(receipt == receipts[0] for receipt in receipts)
    assert receipts[0].semantic_revision == 2


def test_crypto_exception_has_no_allow_fallback(authority, monkeypatch):
    def unavailable(_):
        raise UnsupportedAlgorithm("fixture detail must not escape")

    monkeypatch.setattr(module.Ed25519PublicKey, "from_public_bytes", unavailable)
    _deny(authority, (_authorize(authority),))


@pytest.mark.parametrize("artifacts", [[], [_digest(b"not bytes")], None, ()])
def test_history_container_and_event_bytes_are_exact(authority, artifacts):
    _deny(authority, artifacts)


def test_foreign_expected_or_root_types_are_denied(authority):
    _deny(authority, (_authorize(authority),), expected=None)
    _deny(authority, (_authorize(authority),), root=None)
