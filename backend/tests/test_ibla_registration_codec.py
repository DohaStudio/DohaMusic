"""Portable strict ADR-111 profiles and byte-stable domain-separated hashes."""

from dataclasses import asdict
from datetime import UTC, datetime, timedelta

import pytest
import rfc8785

from backend.bootstrap_authority.ibla.codec import control_wire, parse_control
from backend.bootstrap_authority.ibla.contracts import IblaDenied
from backend.bootstrap_authority.ibla.registration_codec import (
    CONFIRMATION_DOMAIN,
    EVENT_DOMAIN,
    INTENT_DOMAIN,
    OPERATION_DOMAIN,
    PURPOSE,
    REGISTRATION_FIELDS,
    parse_event,
    signed,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.tests.ibla_source_support import payloads, sign
from backend.tests.ibla_support import BINDING, Head, uid


@pytest.fixture(name="profiles")
def codec_profiles():
    a, c, root, initializer, *_ = payloads()
    now = datetime.now(UTC).replace(microsecond=0)
    start = (now - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    end = (now + timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    h = {"revision": 1, "digest": digest(b"original commission")}
    r = dict(
        schema="dohamusic/ibla-registration-intent/v1",
        purpose=PURPOSE,
        registration_id=uid(4000),
        operation_id=uid(4001),
        binding=asdict(BINDING),
        inventory_digest=a["inventory_digest"],
        registration_scope_digest=digest(b"scopes"),
        intended_journal_id=a["journal_id"],
        expected_l_head=h,
        expected_h_head=dict(h),
        expected_h_confirmed=dict(h),
        writer_ref=a["ledger_custodian_ref"],
        initializer_ref=a["initializer_ref"],
        root_key_id=a["root_key_id"],
        initializer_key_id=a["initializer_key_id"],
        positive_origin_digest=a["positive_origin_digest"],
        commissioning_confirmation_digest=digest(rfc8785.dumps(c)),
        issued_at=start,
        expires_at=end,
        recorded_at=start,
    )
    q = dict(
        schema="dohamusic/ibla-registration-confirmation/v1",
        purpose="IBLA_REGISTRATION_CONFIRMATION_ONLY",
        intent_digest=digest(INTENT_DOMAIN + rfc8785.dumps(r)),
        initializer_ref=r["initializer_ref"],
        initializer_key_id=r["initializer_key_id"],
        original_confirmation_ref="independent-registration-original",
        original_confirmation_digest=digest(b"independent registration original"),
        issued_at=start,
        expires_at=end,
    )
    return r, q, root, initializer, now


def event(r, q):
    nested = {k: r[k] for k in REGISTRATION_FIELDS if k in r}
    nested.update(
        intent_digest=digest(INTENT_DOMAIN + rfc8785.dumps(r)),
        confirmation_digest=digest(CONFIRMATION_DOMAIN + rfc8785.dumps(q)),
        observation_id=uid(6000),
    )
    return dict(
        schema="dohamusic/ibla-ledger-event/v2",
        binding=r["binding"],
        event_id=r["registration_id"],
        operation_id=r["operation_id"],
        revision=2,
        previous_digest=r["expected_l_head"]["digest"],
        kind="REGISTRATION_COMMITTED",
        evidence_digest=nested["intent_digest"],
        recorded_at=r["recorded_at"],
        registration=nested,
    )


def test_exact_profiles_and_domains(profiles):
    r, q, root, initializer, now = profiles
    for p, key, confirmation, domain in (
        (r, root, False, INTENT_DOMAIN),
        (q, initializer, True, CONFIRMATION_DOMAIN),
    ):
        payload, d, _ = signed(
            sign(key, domain, p),
            confirmation=confirmation,
            public=key.public_key().public_bytes_raw(),
            fingerprint=digest(key.public_key().public_bytes_raw()),
            checked_at=now,
        )
        assert payload == p and d == digest(domain + rfc8785.dumps(p))
    wire = rfc8785.dumps(event(r, q))
    e = parse_event(wire, BINDING)
    assert e.digest == digest(EVENT_DOMAIN + wire)
    assert e.fingerprint == digest(OPERATION_DOMAIN + wire)
    cw = control_wire(
        BINDING,
        sequence=2,
        previous=digest(b"h prefix"),
        kind="PREPARED",
        confirmed=Head(1, e.previous_digest),
        pending=wire,
        recorded_at=r["recorded_at"],
        version=2,
    )
    assert parse_control(cw, BINDING, version=2)[2] == e
    with pytest.raises(ValueError):
        parse_control(cw, BINDING)


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema", "unsupported"),
        ("purpose", "INITIAL_AUTHORIZATION"),
        ("extra", True),
        ("revision", True),
        ("revision", 3),
        ("revision", 9007199254740992),
        ("previous_digest", digest(b"wrong")),
        ("kind", "INITIAL_SEALED"),
        ("event_id", uid(7000)),
        ("operation_id", uid(4000)),
        ("evidence_digest", digest(b"wrong")),
        ("recorded_at", "2026-10-04T00:00:00+00:00"),
    ],
)
def test_malformed_event(profiles, key, value):
    r, q, *_ = profiles
    p = event(r, q)
    p[key] = value
    with pytest.raises(ValueError):
        parse_event(rfc8785.dumps(p), BINDING)


@pytest.mark.parametrize(
    "key,value",
    [
        ("purpose", "COMMISSION_ONLY"),
        ("extra", 1),
        ("writer_ref", "é"),
        ("root_key_id", "x" * 129),
        ("inventory_digest", "0" * 64),
        ("issued_at", "2099-01-01T00:00:00Z"),
        ("expires_at", "2099-01-01T00:00:00Z"),
        ("recorded_at", "2000-01-01T00:00:00Z"),
        ("registration_id", uid(4001)),
    ],
)
def test_malformed_intent(profiles, key, value):
    r, _, root, _, now = profiles
    r[key] = value
    with pytest.raises((ValueError, IblaDenied)):
        signed(
            sign(root, INTENT_DOMAIN, r),
            confirmation=False,
            public=root.public_key().public_bytes_raw(),
            fingerprint=digest(root.public_key().public_bytes_raw()),
            checked_at=now,
        )
