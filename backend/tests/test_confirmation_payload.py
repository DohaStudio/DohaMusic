"""Canonical payload boundary tests; disposable data, never authenticity proof."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, asdict, replace

import pytest
import rfc8785

from backend.bootstrap_authority.confirmation_payload import (
    CONFIRMATION_ALGORITHM,
    CONFIRMATION_SCHEMA,
    CONFIRMATION_SCOPE,
    ConfirmationPayloadDenied,
    ConfirmationPayloadErrorCode,
    ExpectedConfirmationPayload,
    parse_canonical_confirmation_payload,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.provisioning_binding import PolicyLineageFacts
from backend.tests.test_bootstrap_private_pin_reader import fixture, native
from backend.tests.test_confirmation_snapshot import live, setup
from backend.tests.test_confirmation_snapshot import require as require_snapshot
from backend.tests.test_provisioning_binding import uid


def expected(**changes):
    values = dict(
        confirmation_id=uid(100),
        original_confirmation_ref="original/test",
        initializer_ref="initializer/test",
        installation_id=uid(1),
        installation_proof_key_fingerprint=digest(b"installation key"),
        action_id=uid(200),
        policy_digest=digest(b"policy"),
        designation_digest=digest(b"designation"),
        verifier_key_id="verifier/test-v1",
        verifier_fingerprint=digest(b"verifier key"),
        replay_id=uid(300),
    )
    values.update(changes)
    return ExpectedConfirmationPayload(**values)


def payload(value=None, **changes):
    value = expected() if value is None else value
    result = {
        "schema": CONFIRMATION_SCHEMA,
        "algorithm": CONFIRMATION_ALGORITHM,
        **asdict(value),
        "scope": CONFIRMATION_SCOPE,
    }
    result.update(changes)
    return result


def raw(value=None, **changes):
    return rfc8785.dumps(payload(value, **changes))


def deny(data, *, value=None, code=None):
    with pytest.raises(ConfirmationPayloadDenied) as caught:
        parse_canonical_confirmation_payload(data, expected=expected() if value is None else value)
    if code is not None:
        assert caught.value.code == code
    assert str(caught.value) == caught.value.code.value
    assert caught.value.__cause__ is None


def test_exact_canonical_payload_returns_non_authorizing_immutable_boundary():
    value = expected()
    boundary = parse_canonical_confirmation_payload(raw(value), expected=value)
    assert boundary.payload_digest == digest(raw(value))
    assert boundary.confirmation_id == value.confirmation_id
    with pytest.raises(FrozenInstanceError):
        boundary.replay_id = uid(9)
    for name in ("authenticated", "current", "admit", "authorize", "signature"):
        assert not hasattr(boundary, name)


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"\xff",
        b"null",
        b"[]",
        b"{}",
        b"\xef\xbb\xbf{}",
        b'{"schema":"x","schema":"y"}',
        b'{"number":1}',
        b"{" + b"x" * 1_048_576 + b"}",
    ],
    ids=(
        "empty",
        "utf8",
        "null",
        "array",
        "empty-object",
        "bom",
        "duplicate",
        "number",
        "oversize",
    ),
)
def test_malformed_payload_fails_closed(data):
    deny(data, code=ConfirmationPayloadErrorCode.MALFORMED_PAYLOAD)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda data: b" " + data,
        lambda data: data + b"\n",
        lambda data: json.dumps(json.loads(data), ensure_ascii=True).encode(),
    ],
)
def test_only_exact_jcs_bytes_are_accepted(mutate):
    deny(mutate(raw()), code=ConfirmationPayloadErrorCode.NON_CANONICAL_PAYLOAD)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema", "wrong"),
        ("algorithm", "none"),
        ("scope", "ALL"),
        ("confirmation_id", uid(998)),
        ("installation_id", uid(999)),
        ("action_id", uid(999)),
        ("policy_digest", digest(b"wrong")),
        ("designation_digest", digest(b"wrong")),
        ("initializer_ref", "initializer/other"),
        ("original_confirmation_ref", "original/other"),
        ("installation_proof_key_fingerprint", digest(b"wrong")),
        ("verifier_key_id", "verifier/other"),
        ("verifier_fingerprint", digest(b"wrong")),
        ("replay_id", uid(999)),
    ],
)
def test_wrong_domain_or_expected_binding_fails_closed(field, value):
    code = (
        ConfirmationPayloadErrorCode.MALFORMED_PAYLOAD
        if field in {"schema", "algorithm", "scope"}
        else ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH
    )
    deny(raw(**{field: value}), code=code)


@pytest.mark.parametrize("change", ["missing", "extra", "nested", "bool", "null"])
def test_no_partial_unknown_or_type_confused_payload(change):
    data = payload()
    if change == "missing":
        data.pop("action_id")
    elif change == "extra":
        data["authorized"] = "true"
    elif change == "nested":
        data["initializer_ref"] = {"value": "initializer/test"}
    elif change == "bool":
        data["initializer_ref"] = True
    else:
        data["initializer_ref"] = None
    deny(rfc8785.dumps(data), code=ConfirmationPayloadErrorCode.MALFORMED_PAYLOAD)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("confirmation_id", "not-a-uuid"),
        ("original_confirmation_ref", "*"),
        ("policy_digest", "sha256:ABC"),
        ("verifier_fingerprint", "wrong"),
    ],
)
def test_payload_identifiers_are_validated_before_expectation_comparison(field, value):
    deny(raw(**{field: value}), code=ConfirmationPayloadErrorCode.MALFORMED_PAYLOAD)


def test_hostile_expectation_and_mutable_alias_cannot_compare_or_rebind():
    class Hostile:
        calls = 0

        def __eq__(self, other):
            self.calls += 1
            return True

    hostile = Hostile()
    deny(raw(), value=hostile, code=ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH)
    assert hostile.calls == 0

    class HostileText(str):
        calls = 0

        def __eq__(self, other):
            self.calls += 1
            return True

    hostile_text = HostileText(uid(200))
    value = expected()
    object.__setattr__(value, "action_id", hostile_text)
    deny(raw(), value=value, code=ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH)
    assert hostile_text.calls == 0

    value = expected()
    original = value.action_id
    object.__setattr__(value, "action_id", uid(999))
    deny(raw(expected()), value=value, code=ConfirmationPayloadErrorCode.EXPECTATION_MISMATCH)
    object.__setattr__(value, "action_id", original)


def test_concurrent_parse_is_deterministic_and_has_no_shared_authority_state():
    value, data = expected(), raw()
    with ThreadPoolExecutor(8) as pool:
        receipts = list(
            pool.map(
                lambda _: parse_canonical_confirmation_payload(data, expected=value), range(64)
            )
        )
    assert len({receipt.payload_digest for receipt in receipts}) == 1
    assert len({id(receipt) for receipt in receipts}) == 64


def _bind_canonical(inputs, path):
    action = inputs["action"]
    value = expected(
        confirmation_id=action.confirmation.provenance_id,
        original_confirmation_ref=action.confirmation.original_confirmation_ref,
        initializer_ref=action.confirmation.initializer_ref,
        installation_id=action.policy.installation_id,
        installation_proof_key_fingerprint=action.policy.installation_proof_key_fingerprint,
        action_id=action.action_id,
        policy_digest=action.confirmation.policy_digest,
        designation_digest=inputs["pin_facts"].binding.designation_record_digest,
    )
    data = raw(value)
    path.write_bytes(data)
    confirmation = replace(action.confirmation, original_confirmation_digest=digest(data))
    action = replace(action, confirmation=confirmation)
    lineage = PolicyLineageFacts(
        inputs["lineage"].anchor_id,
        inputs["lineage"].installation_id,
        inputs["lineage"].source_id,
        (action,),
        ("ACTIVE",),
    )
    inputs.update(action=action, lineage=lineage)
    return value


def test_live_raw_snapshot_to_canonical_boundary_handoff_and_stale_reuse_denial(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, path, _, policy = setup(fx, tmp_path)
        with live(fx, reader, designation, policy) as inputs:
            value = _bind_canonical(inputs, path)
            with reader._open_snapshot(**inputs) as handle:
                boundary = reader._require_canonical_payload(
                    handle,
                    expected=value,
                    fresh_action=inputs["action"],
                    fresh_lineage=inputs["lineage"],
                )
                assert (
                    boundary.payload_digest
                    == inputs["action"].confirmation.original_confirmation_digest
                )
                with pytest.raises(PrivateFactsDenied):
                    reader._require_canonical_payload(
                        handle,
                        expected=replace(value, replay_id=uid(999)),
                        fresh_action=inputs["action"],
                        fresh_lineage=inputs["lineage"],
                    )
                with pytest.raises(PrivateFactsDenied):
                    require_snapshot(reader, handle, inputs)


def test_public_payload_substitution_cannot_replace_original_snapshot_handle(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        reader, designation, path, _, policy = setup(fx, tmp_path)
        with live(fx, reader, designation, policy) as inputs:
            value = _bind_canonical(inputs, path)
            with reader._open_snapshot(**inputs) as handle:
                copied = copy.deepcopy(value)
                object.__setattr__(copied, "designation_digest", digest(b"other"))
                with pytest.raises(PrivateFactsDenied):
                    reader._require_canonical_payload(
                        handle,
                        expected=copied,
                        fresh_action=inputs["action"],
                        fresh_lineage=inputs["lineage"],
                    )
