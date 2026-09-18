"""Disposable comparison data only; never actual provisioning/designation evidence."""

import base64
import copy
import json
from dataclasses import FrozenInstanceError, asdict, replace
from uuid import uuid4

import pytest
import rfc8785

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import (
    FIELDS,
    PIN_FACTS_SCHEMA,
    SCOPE_FIELDS,
    PrivateFactsDenied,
    decode_pin_facts,
)
from backend.tests.test_bootstrap_witness_lifetime import SCOPE, binding

INSTALLATION_FP = digest(b"disposable installation public fingerprint")


def value(current=None):
    current = current or binding()
    return {
        "schema": PIN_FACTS_SCHEMA,
        "installation_id": SCOPE[0],
        "installation_proof_key_fingerprint": INSTALLATION_FP,
        "pin": asdict(current.installed_pin),
        "designation_id": current.designation_id,
        "designation_record_digest": current.designation_record_digest,
        "deployment_owner_ref": current.deployment_owner_ref,
        "affected_scopes": [
            dict(zip(SCOPE_FIELDS, scope, strict=True)) for scope in current.affected_scopes
        ],
        "root_key_id": current.root_key_id,
        "root_fingerprint": current.root_fingerprint,
        "root_public_key": base64.urlsafe_b64encode(current.root_public_key).rstrip(b"=").decode(),
        "status": current.status,
        "domain": current.domain,
    }


def decode(data=None, **changes):
    args = dict(
        expected=binding(),
        installation_id=SCOPE[0],
        installation_proof_key_fingerprint=INSTALLATION_FP,
    )
    args.update(changes)
    # Preserve hostile floats/large integers: JCS would normalize 1.0 to 1 or
    # reject the integer BEFORE the real production decoder gets the hostile wire.
    raw = json.dumps(
        value() if data is None else data, sort_keys=True, separators=(",", ":")
    ).encode()
    return decode_pin_facts(raw, **args)


def test_complete_immutable_facts_never_production_authority():
    facts = decode()
    assert facts.binding == binding()
    assert facts.installation_id == SCOPE[0]
    with pytest.raises(FrozenInstanceError):
        facts.installation_id = str(uuid4())
    assert "sha256:" not in repr(facts)
    ports = UnavailableCurrentnessPorts()
    for candidate in (facts, facts.binding, value(), copy.deepcopy(facts)):
        with pytest.raises(CurrentnessUnavailable):
            ports.admit_with_private_ceremony_witness(candidate)
        with pytest.raises(CurrentnessUnavailable):
            ports.revalidate_private_currentness_witness(candidate)


@pytest.mark.parametrize("field", sorted(FIELDS))
def test_all_fields_required(field):
    data = value()
    del data[field]
    with pytest.raises(PrivateFactsDenied):
        decode(data)


@pytest.mark.parametrize("field", ["verified", "private_key", "current", "journal", "authority"])
def test_unknown_or_public_substitution_denied(field):
    data = value()
    data[field] = True
    with pytest.raises(PrivateFactsDenied):
        decode(data)


@pytest.mark.parametrize(
    "field,changed",
    [
        ("schema", "dohamusic/deployment-bootstrap-approval/v1"),
        ("domain", PIN_FACTS_SCHEMA),
        ("installation_id", str(uuid4())),
        ("installation_proof_key_fingerprint", digest(b"wrong")),
        ("designation_id", str(uuid4())),
        ("designation_record_digest", digest(b"wrong")),
        ("deployment_owner_ref", "owner/wrong"),
        ("root_key_id", "root/wrong"),
        ("root_fingerprint", digest(b"wrong")),
        ("root_public_key", "A" * 43),
        ("status", "REVOKED"),
        ("status", "RETIRED"),
        ("status", "COMPROMISED"),
        ("affected_scopes", []),
        ("affected_scopes", None),
        ("root_public_key", None),
        ("root_public_key", "!" * 43),
        ("root_public_key", "A" * 43 + "="),
    ],
)
def test_mismatched_or_malformed_fact(field, changed):
    data = value()
    data[field] = changed
    with pytest.raises(PrivateFactsDenied):
        decode(data)


@pytest.mark.parametrize("counter", ["revision", "trust_revision"])
@pytest.mark.parametrize("changed", [True, False, 1.0, 0, 2, 9007199254740992])
def test_counters_strict(counter, changed):
    data = value()
    data["pin"][counter] = changed
    with pytest.raises(PrivateFactsDenied):
        decode(data)


@pytest.mark.parametrize("field", list(value()["pin"]))
def test_pin_complete(field):
    data = value()
    del data["pin"][field]
    with pytest.raises(PrivateFactsDenied):
        decode(data)


@pytest.mark.parametrize("field", SCOPE_FIELDS)
def test_scope_exact_and_complete(field):
    data = value()
    data["affected_scopes"][0][field] = str(uuid4())
    with pytest.raises(PrivateFactsDenied):
        decode(data)
    del data["affected_scopes"][0][field]
    with pytest.raises(PrivateFactsDenied):
        decode(data)


def test_partial_complete_manifest_not_accepted():
    extra = tuple(str(uuid4()) for _ in range(3))
    current = replace(binding(), affected_scopes=tuple(sorted((SCOPE, extra))))
    data = value(current)
    assert decode(data, expected=current).binding == current
    data["affected_scopes"].pop()
    with pytest.raises(PrivateFactsDenied):
        decode(data, expected=current)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"{}",
        b"[]",
        b"true",
        b"\xff",
        b'{"schema":"a","schema":"b"}',
        b'{"revision":NaN}',
        b'{"revision":1.0}',
        b" " * 1_048_577,
        b"[" * 1000 + b"]" * 1000,
    ],
    ids=lambda raw: f"wire-size-{len(raw)}",
)
def test_strict_bounded_json(raw):
    with pytest.raises(PrivateFactsDenied):
        decode_pin_facts(
            raw,
            expected=binding(),
            installation_id=SCOPE[0],
            installation_proof_key_fingerprint=INSTALLATION_FP,
        )


def test_no_noncanonical_unicode_or_whitespace():
    raw = rfc8785.dumps(value())
    for changed in (
        b" " + raw,
        b"\xef\xbb\xbf" + raw,
        raw.replace(b'"root/test"', b'"root\\u002ftest"'),
    ):
        with pytest.raises(PrivateFactsDenied):
            decode_pin_facts(
                changed,
                expected=binding(),
                installation_id=SCOPE[0],
                installation_proof_key_fingerprint=INSTALLATION_FP,
            )


@pytest.mark.parametrize("field", ["installation_id", "installation_proof_key_fingerprint"])
def test_caller_string_subclass_cannot_spoof_expected(field):
    class Spoof(str):
        def __eq__(self, other):
            return True

    with pytest.raises(PrivateFactsDenied):
        decode(**{field: Spoof("wrong")})
