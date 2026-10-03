"""Strict ADR-110 wire/signature comparisons; never authority by codec alone."""

import copy
from datetime import UTC, datetime

import pytest
import rfc8785

from backend.bootstrap_authority.ibla.contracts import IblaDenied
from backend.bootstrap_authority.ibla.source_codec import (
    ANCHOR_DOMAIN,
    CONFIRMATION_DOMAIN,
    original,
    signed,
)
from backend.bootstrap_authority.ibla.source_verifier import UnavailableIblaSourceVerifier, _Opaque
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.tests.ibla_source_support import payloads, sign


@pytest.mark.parametrize("confirmation", [False, True])
def test_exact_wire_comparison_is_not_production_authority(confirmation):
    a, c, root, initializer, *_ = payloads()
    key, p, domain = (
        (initializer, c, CONFIRMATION_DOMAIN) if confirmation else (root, a, ANCHOR_DOMAIN)
    )
    raw = sign(key, domain, p)
    actual, _, expiry = signed(
        raw,
        confirmation=confirmation,
        public=key.public_key().public_bytes_raw(),
        fingerprint=digest(key.public_key().public_bytes_raw()),
        checked_at=datetime.now(UTC),
    )
    assert actual == p and expiry > datetime.now(UTC)
    with pytest.raises(IblaDenied, match="^IBLA_UNAVAILABLE$"):
        UnavailableIblaSourceVerifier().open_verified_source(actual)


@pytest.mark.parametrize(
    "change",
    [
        {"purpose": "FIRST_OWNER_BINDING_ONLY"},
        {"algorithm": "RSA"},
        {"authority_epoch": True},
        {"authority_epoch": 1.0},
        {"authority_epoch": 0},
        {"authority_epoch": 2**53},
        {"domain_id": "private-path"},
        {"root_fingerprint": "sha256:wrong"},
        {"unknown": "x"},
        {"expires_at": "2000-01-01T00:00:00Z"},
        {"not_before": "2099-01-01T00:00:00Z"},
        {"expires_at": "2099-01-01T00:00:00Z"},
        {"schema": "unsupported/v2"},
    ],
)
def test_strict_fields_counters_purpose_validity_schema(change):
    a, _, root, *_ = payloads()
    a.update(change)
    if change.get("authority_epoch") == 2**53:
        a["authority_epoch"] = 1
        raw = sign(root, ANCHOR_DOMAIN, a).replace(
            b'"authority_epoch":1,', b'"authority_epoch":9007199254740992,'
        )
    else:
        raw = sign(root, ANCHOR_DOMAIN, a)
    if type(change.get("authority_epoch")) is float:
        raw = raw.replace(b'"authority_epoch":1,', b'"authority_epoch":1.0,')
    with pytest.raises(IblaDenied):
        signed(
            raw,
            confirmation=False,
            public=root.public_key().public_bytes_raw(),
            fingerprint=digest(root.public_key().public_bytes_raw()),
            checked_at=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "kind",
    [
        "duplicate",
        "noncanonical",
        "wrong-domain",
        "wrong-key",
        "oversized",
        "truncated",
        "signature",
    ],
)
def test_strict_envelope_and_independent_pinned_signer(kind):
    a, _, root, initializer, *_ = payloads()
    raw = sign(root, ANCHOR_DOMAIN, a)
    public = root.public_key().public_bytes_raw()
    if kind == "duplicate":
        raw = b'{"payload":null,' + raw[1:]
    elif kind == "noncanonical":
        raw = b" " + raw
    elif kind == "wrong-domain":
        raw = sign(root, CONFIRMATION_DOMAIN, a)
    elif kind == "wrong-key":
        public = initializer.public_key().public_bytes_raw()
    elif kind == "oversized":
        raw = b"x" * 1_048_577
    elif kind == "truncated":
        raw = raw[:-1]
    else:
        value = __import__("json").loads(raw)
        value["signature"] = "A" * 86
        raw = rfc8785.dumps(value)
    with pytest.raises(IblaDenied):
        signed(
            raw,
            confirmation=False,
            public=public,
            fingerprint=digest(public),
            checked_at=datetime.now(UTC),
        )


@pytest.mark.parametrize(
    "raw",
    [b"", b" \r\n", b"\xef\xbb\xbftext", b"raw\x00text", b"\xff", b"x" * 1_048_577],
    ids=["empty", "blank", "bom", "nul", "utf8", "oversized"],
)
def test_original_profile(raw):
    with pytest.raises(IblaDenied):
        original(raw)


def test_exact_original_bytes_and_opaque_handle_no_public_construction():
    assert original(b"line\r\n") != original(b"line\n")
    with pytest.raises(IblaDenied):
        _Opaque()
    with pytest.raises(TypeError):
        type("Copied", (_Opaque,), {})
    with pytest.raises(IblaDenied):
        copy.copy(UnavailableIblaSourceVerifier().open_verified_source())
