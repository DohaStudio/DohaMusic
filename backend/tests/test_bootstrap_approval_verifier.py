"""Disposable-key issuance integrity only, not a bootstrap ceremony/consume simulation."""

from __future__ import annotations

import base64
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace
from datetime import UTC, datetime
from uuid import UUID

import pytest
import rfc8785
from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from backend.bootstrap_authority import approval_verifier as module
from backend.bootstrap_authority.approval_verifier import (
    APPROVAL_SCHEMA,
    SIGNATURE_DOMAIN,
    ApprovalIntegrityError,
    ApprovalIntegrityErrorCode,
    verify_issuance_integrity,
)
from backend.bootstrap_authority.contracts import ExpectedApprovalScope, PinnedRootVerifier

NOW = datetime(2026, 9, 18, 9, tzinfo=UTC)


def _uuid(number: int) -> str:
    return str(UUID(int=number))


def _digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


@pytest.fixture
def ceremony():
    # Deterministic disposable material is created in memory, never persisted/provisioned.
    key = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
    public = key.public_key().public_bytes_raw()
    root = PinnedRootVerifier(
        root_key_id="root/test-v1",
        designation_id=_uuid(2),
        deployment_owner_ref="deployment/test-owner",
        designation_digest=_digest(b"test designation"),
        public_key_fingerprint=_digest(public),
        public_key=public,
    )
    scope = ExpectedApprovalScope(
        approval_id=_uuid(1),
        installation_id=_uuid(3),
        installation_proof_key_fingerprint=_digest(b"test installation public key"),
        workspace_id=_uuid(4),
        existing_owner_id=_uuid(5),
        assignment_id=_uuid(6),
        assignment_revision=1,
        custodian_ref="custodian/test-human",
        custodian_proof_key_fingerprint=_digest(b"test custodian public key"),
        governance_provenance_digest=_digest(b"test governance"),
    )
    payload = {
        "schema": APPROVAL_SCHEMA,
        "algorithm": "Ed25519",
        **asdict(scope),
        "root_key_id": root.root_key_id,
        "designation_id": root.designation_id,
        "deployment_owner_ref": root.deployment_owner_ref,
        "designation_digest": root.designation_digest,
        "scope": "FIRST_OWNER_BINDING_ONLY",
        "issued_at": "2026-09-18T08:00:00Z",
        "not_before": "2026-09-18T08:30:00Z",
        "expires_at": "2026-09-19T08:00:00Z",
    }
    return key, root, scope, payload


def _artifact(key, payload, *, domain=SIGNATURE_DOMAIN, message=None):
    signature = key.sign(domain + rfc8785.dumps(payload) if message is None else message)
    return json.dumps(
        {
            "payload": payload,
            "signature": base64.urlsafe_b64encode(signature).rstrip(b"=").decode(),
        },
        ensure_ascii=True,
    ).encode()


def _verify(ceremony, artifact=None, **kwargs):
    key, root, scope, payload = ceremony
    return verify_issuance_integrity(
        _artifact(key, payload) if artifact is None else artifact,
        root=kwargs.get("root", root),
        expected_scope=kwargs.get("expected_scope", scope),
        checked_at=kwargs.get("checked_at", NOW),
    )


def _deny(ceremony, artifact=None, code=None, **kwargs):
    with pytest.raises(ApprovalIntegrityError) as caught:
        _verify(ceremony, artifact, **kwargs)
    if code is not None:
        assert caught.value.code == code
    assert str(caught.value) == caught.value.code.value
    assert caught.value.__cause__ is None


def test_valid_integrity_receipt_is_immutable_and_not_authorization(ceremony):
    receipt = _verify(ceremony)
    assert receipt.approval_id == _uuid(1)
    assert receipt.payload_digest == _digest(rfc8785.dumps(ceremony[3]))
    assert receipt.expires_at == datetime(2026, 9, 19, 8, tzinfo=UTC)
    with pytest.raises(FrozenInstanceError):
        receipt.assignment_revision = 2
    for attribute in (
        "authorized",
        "active",
        "principal_id",
        "consume",
        "grant",
        "_provider_witness",
    ):
        assert not hasattr(receipt, attribute)
    assert "public_key=" not in repr(ceremony[1])


def test_wire_whitespace_and_object_order_do_not_change_jcs_signature(ceremony):
    key, _, _, payload = ceremony
    envelope = json.loads(_artifact(key, payload))
    envelope["payload"] = dict(reversed(list(payload.items())))
    artifact = json.dumps(envelope, indent=3).encode()
    assert _verify(ceremony, artifact) == _verify(ceremony)


def test_repeated_parallel_integrity_checks_do_not_claim_one_time_consumption(ceremony):
    with ThreadPoolExecutor(max_workers=4) as pool:
        receipts = list(pool.map(lambda _: _verify(ceremony), range(8)))
    assert all(receipt == receipts[0] for receipt in receipts)
    # Reuse is mathematically valid; future status/journal/consume must reject replay.


@pytest.mark.parametrize(
    "field",
    list(
        asdict(
            ExpectedApprovalScope(
                _uuid(1),
                _uuid(3),
                _digest(b"i"),
                _uuid(4),
                _uuid(5),
                _uuid(6),
                1,
                "custodian/test",
                _digest(b"c"),
                _digest(b"g"),
            )
        )
    ),
)
def test_every_independent_exact_scope_mismatch_denied(ceremony, field):
    _, _, scope, _ = ceremony
    old = getattr(scope, field)
    wrong = (
        2
        if type(old) is int
        else (
            _digest(b"other")
            if old.startswith("sha256:")
            else ("custodian/other" if field == "custodian_ref" else _uuid(999))
        )
    )
    _deny(
        ceremony,
        expected_scope=replace(scope, **{field: wrong}),
        code=ApprovalIntegrityErrorCode.SCOPE_MISMATCH,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("root_key_id", "root/other"),
        ("designation_id", _uuid(99)),
        ("deployment_owner_ref", "deployment/other"),
        ("designation_digest", _digest(b"other")),
        ("public_key_fingerprint", _digest(b"wrong fingerprint")),
    ],
)
def test_root_designation_and_fingerprint_mismatch(ceremony, field, value):
    _deny(
        ceremony,
        root=replace(ceremony[1], **{field: value}),
        code=ApprovalIntegrityErrorCode.ROOT_MISMATCH,
    )


def test_wrong_public_root_even_with_matching_fingerprint_is_not_trusted(ceremony):
    public = Ed25519PrivateKey.from_private_bytes(bytes(reversed(range(32)))).public_key()
    raw = public.public_bytes_raw()
    _deny(
        ceremony,
        root=replace(ceremony[1], public_key=raw, public_key_fingerprint=_digest(raw)),
        code=ApprovalIntegrityErrorCode.INVALID_SIGNATURE,
    )


@pytest.mark.parametrize(
    "domain",
    [b"", b"DohaMusicDeploymentBootstrapApprovalV1", b"DohaMusicDeploymentBootstrapApprovalV2\x00"],
)
def test_signature_domain_is_fixed_including_nul(ceremony, domain):
    _deny(
        ceremony,
        _artifact(ceremony[0], ceremony[3], domain=domain),
        code=ApprovalIntegrityErrorCode.INVALID_SIGNATURE,
    )


def test_non_jcs_json_signature_and_payload_tampering_denied(ceremony):
    key, _, _, payload = ceremony
    _deny(
        ceremony,
        _artifact(key, payload, message=SIGNATURE_DOMAIN + json.dumps(payload).encode()),
        code=ApprovalIntegrityErrorCode.INVALID_SIGNATURE,
    )
    envelope = json.loads(_artifact(key, payload))
    envelope["payload"]["expires_at"] = "2026-09-19T07:59:59Z"
    _deny(
        ceremony, json.dumps(envelope).encode(), code=ApprovalIntegrityErrorCode.INVALID_SIGNATURE
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("algorithm", "Ed448"),
        ("algorithm", "none"),
        ("schema", "other/v1"),
        ("scope", "RIGHTS_ISSUE"),
        ("workspace_id", "*"),
        ("workspace_id", _uuid(4).replace("-", "")),
        ("assignment_revision", True),
        ("assignment_revision", 0),
        ("assignment_revision", (1 << 53)),
        ("custodian_ref", "../private"),
        ("custodian_ref", "*"),
        ("root_key_id", "ROOT_\ud800"),
        ("designation_digest", "sha256:" + "A" * 64),
        ("issued_at", "2026-09-18T08:00:00+00:00"),
        ("issued_at", "2026-09-18T08:00:00.000Z"),
        ("issued_at", "2026-02-30T08:00:00Z"),
        ("expires_at", "2026-09-19T08:00:01Z"),
        ("not_before", "2026-09-18T07:59:59Z"),
        ("expires_at", "2026-09-18T08:30:00Z"),
        ("installation_id", None),
        ("custodian_ref", {}),
    ],
)
def test_invalid_signed_payload_contract(ceremony, field, value):
    envelope = json.loads(_artifact(ceremony[0], ceremony[3]))
    envelope["payload"][field] = value
    _deny(ceremony, json.dumps(envelope).encode(), code=ApprovalIntegrityErrorCode.INVALID_PAYLOAD)


@pytest.mark.parametrize(
    "artifact",
    [
        b"",
        b"\xff",
        b"[]",
        b"null",
        b"{}",
        b"{" * 2000,
        b"\xef\xbb\xbf{}",
        b"x" * 16385,
        b'{"payload":{},"payload":{},"signature":""}',
        b'{"payload":{"x":1,"x":2},"signature":""}',
        b'{"payload":NaN,"signature":""}',
        b'{"payload":1.5,"signature":""}',
        b"[" * 2000 + b"]" * 2000,
    ],
)
def test_malformed_artifact_is_safe_error(ceremony, artifact):
    _deny(ceremony, artifact, code=ApprovalIntegrityErrorCode.MALFORMED_ARTIFACT)


@pytest.mark.parametrize("change", ["public_key", "status", "principal_id", "extra", "missing"])
def test_unknown_envelope_payload_and_target_principal_fields_denied(ceremony, change):
    envelope = json.loads(_artifact(ceremony[0], ceremony[3]))
    if change == "public_key":
        envelope["public_key"] = "attacker supplied verifier"
    elif change == "missing":
        del envelope["payload"]["assignment_revision"]
    else:
        envelope["payload"][change] = "attacker supplied authority"
    _deny(
        ceremony, json.dumps(envelope).encode(), code=ApprovalIntegrityErrorCode.MALFORMED_ARTIFACT
    )


@pytest.mark.parametrize(
    "signature", ["", "A" * 85, "A" * 87, "A" * 86 + "==", "+" * 86, "A" * 85 + "B", None]
)
def test_signature_encoding_length_and_unused_bits_are_strict(ceremony, signature):
    envelope = json.loads(_artifact(ceremony[0], ceremony[3]))
    envelope["signature"] = signature
    _deny(
        ceremony, json.dumps(envelope).encode(), code=ApprovalIntegrityErrorCode.MALFORMED_ARTIFACT
    )


@pytest.mark.parametrize(
    "when", [datetime(2026, 9, 18, 8, 29, 59, tzinfo=UTC), datetime(2026, 9, 19, 8, tzinfo=UTC)]
)
def test_issuance_window_not_before_and_expiry_are_exclusive_at_end(ceremony, when):
    _deny(ceremony, checked_at=when, code=ApprovalIntegrityErrorCode.OUTSIDE_ISSUANCE_WINDOW)


def test_exact_not_before_allowed(ceremony):
    assert _verify(ceremony, checked_at=datetime(2026, 9, 18, 8, 30, tzinfo=UTC))


@pytest.mark.parametrize(
    "when",
    [
        datetime(2026, 9, 18),
        "2026-09-18T09:00:00Z",
        None,
        datetime.fromisoformat("2026-09-18T09:00:00+01:00"),
    ],
)
def test_non_utc_or_untyped_check_time_denied(ceremony, when):
    _deny(ceremony, checked_at=when, code=ApprovalIntegrityErrorCode.INVALID_CHECK_TIME)


def test_crypto_library_unavailable_does_not_fallback(ceremony, monkeypatch):
    def unavailable(_):
        raise UnsupportedAlgorithm("sensitive library input")

    monkeypatch.setattr(module.Ed25519PublicKey, "from_public_bytes", unavailable)
    _deny(ceremony, code=ApprovalIntegrityErrorCode.VERIFIER_UNAVAILABLE)


@pytest.mark.parametrize(
    "field,value",
    [
        ("public_key", b"short"),
        ("public_key", bytearray(32)),
        ("root_key_id", None),
        ("designation_id", "not UUID"),
        ("public_key_fingerprint", "sha256:invalid"),
    ],
)
def test_root_input_validation(ceremony, field, value):
    with pytest.raises(ValueError):
        replace(ceremony[1], **{field: value})


@pytest.mark.parametrize("revision", [True, 0, -1, 1.0, "1", (1 << 53)])
def test_expected_scope_revision_validation(ceremony, revision):
    with pytest.raises(ValueError):
        replace(ceremony[2], assignment_revision=revision)


def test_safe_integer_maximum_supported(ceremony):
    key, root, scope, payload = ceremony
    payload = {**payload, "assignment_revision": (1 << 53) - 1}
    assert verify_issuance_integrity(
        _artifact(key, payload),
        root=root,
        expected_scope=replace(scope, assignment_revision=(1 << 53) - 1),
        checked_at=NOW,
    )


def test_rfc8032_section_7_1_test_1_public_verification_vector():
    # Official public vector only: no RFC private seed copied into the repository.
    public = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
    signature = bytes.fromhex(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555f"
        "b8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    )
    Ed25519PublicKey.from_public_bytes(public).verify(signature, b"")
    with pytest.raises(InvalidSignature):
        Ed25519PublicKey.from_public_bytes(public).verify(signature, SIGNATURE_DOMAIN)


def test_rfc8785_section_3_2_3_utf16_property_sorting_vector():
    keys = ["\u20ac", "\r", "\ufb33", "1", "\U0001f600", "\u0080", "\u00f6"]
    canonical = rfc8785.dumps(dict.fromkeys(keys, "v"))
    expected = '{"\\r":"v","1":"v","\u0080":"v","ö":"v","€":"v","😀":"v","דּ":"v"}'
    assert canonical == expected.encode("utf-8")


def test_rfc8785_number_rendering_and_invalid_unicode():
    assert rfc8785.dumps([333333333.33333329, 1e30, 4.50, 2e-3, 1e-27]) == (
        b"[333333333.3333333,1e+30,4.5,0.002,1e-27]"
    )
    with pytest.raises(rfc8785.CanonicalizationError):
        rfc8785.dumps("\ud800")


def test_corrupted_signature_and_future_issuance_denied(ceremony):
    key, _, _, payload = ceremony
    envelope = json.loads(_artifact(key, payload))
    raw = bytearray(base64.urlsafe_b64decode(envelope["signature"] + "=="))
    raw[0] ^= 1
    envelope["signature"] = base64.urlsafe_b64encode(raw).rstrip(b"=").decode()
    _deny(
        ceremony, json.dumps(envelope).encode(), code=ApprovalIntegrityErrorCode.INVALID_SIGNATURE
    )
    future = {**payload, "issued_at": "2026-09-18T10:00:00Z", "not_before": "2026-09-18T10:00:00Z"}
    _deny(ceremony, _artifact(key, future), code=ApprovalIntegrityErrorCode.OUTSIDE_ISSUANCE_WINDOW)


def test_float_revision_and_duplicate_signed_key_denied_before_canonicalization(ceremony):
    artifact = _artifact(ceremony[0], ceremony[3])
    for changed in (
        artifact.replace(b'"assignment_revision": 1', b'"assignment_revision": 1.0'),
        artifact.replace(
            b'"assignment_revision": 1', b'"assignment_revision": 1, "assignment_revision": 1'
        ),
    ):
        _deny(ceremony, changed, code=ApprovalIntegrityErrorCode.MALFORMED_ARTIFACT)


def test_noncanonical_uuid_case_and_untyped_inputs(ceremony):
    with pytest.raises(ValueError):
        replace(ceremony[2], workspace_id="aaaaaaaa-AAAA-aaaa-aaaa-aaaaaaaaaaaa")
    _deny(ceremony, root=None, code=ApprovalIntegrityErrorCode.INVALID_PAYLOAD)
    _deny(ceremony, expected_scope=None, code=ApprovalIntegrityErrorCode.INVALID_PAYLOAD)
    _deny(ceremony, artifact="not bytes", code=ApprovalIntegrityErrorCode.MALFORMED_ARTIFACT)
