"""Live lineage record mechanics with disposable facts; never admission authority."""

import copy
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
import rfc8785

from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.live_lineage_reader import (
    FIELDS,
    LINEAGE_RECORD_FILE,
    LINEAGE_SCHEMA,
    _LivePolicyLineageSnapshots,
    parse_live_lineage_record,
)
from backend.bootstrap_authority.pin_facts import PrivateFactsDenied
from backend.bootstrap_authority.provisioning_binding import (
    PolicyLineageFacts,
    action_comparison_digest,
    lineage_comparison_digest,
)
from backend.bootstrap_authority.windows_fact_files import _WindowsFactFiles
from backend.tests.test_bootstrap_private_pin_reader import fixture, native
from backend.tests.test_confirmation_payload import _bind_canonical
from backend.tests.test_confirmation_snapshot import live, setup
from backend.tests.test_designation_source_custody import process_account, provision_fixture_acl
from backend.tests.test_provisioning_binding import action as public_action
from backend.tests.test_provisioning_binding import history, uid


def public_values():
    action = public_action()
    lineage = PolicyLineageFacts(
        uid(52), action.policy.installation_id, action.policy.source_id, (action,), ("ACTIVE",)
    )
    return action, lineage, action.confirmation.pin


def value(action, lineage, pin):
    head = pin.binding.journal
    return {
        "schema": LINEAGE_SCHEMA,
        "journal_id": head.journal_id,
        "journal_revision": head.revision,
        "journal_trust_revision": head.trust_revision,
        "journal_head_digest": head.head_digest,
        "installation_id": lineage.installation_id,
        "anchor_id": lineage.anchor_id,
        "source_id": lineage.source_id,
        "lineage_digest": lineage_comparison_digest(lineage),
        "head_action_digest": action_comparison_digest(action),
        "confirmation_id": action.confirmation.provenance_id,
        "original_confirmation_digest": action.confirmation.original_confirmation_digest,
        "initializer_ref": action.confirmation.initializer_ref,
        "policy_digest": action.confirmation.policy_digest,
        "designation_digest": pin.binding.designation_record_digest,
        "semantic_revision": action.policy.revision,
        "predecessor_digest": action.predecessor_digest,
        "status": "ACTIVE",
    }


def raw(action=None, lineage=None, pin=None, **changes):
    if action is None:
        action, lineage, pin = public_values()
    record = value(action, lineage, pin)
    record.update(changes)
    return rfc8785.dumps(record)


def test_exact_live_record_is_canonical_comparison_not_authority():
    action, lineage, pin = public_values()
    data = raw(action, lineage, pin)
    assert parse_live_lineage_record(data, lineage=lineage, action=action, pin=pin) == digest(data)
    for target in (lineage, action, pin, data, True):
        for attribute in ("admit", "authorize", "currentness_witness", "signature"):
            assert not hasattr(target, attribute)


@pytest.mark.parametrize(
    "data",
    [b"", b"\xff", b"{}", b"[]", b"null", b'{"schema":"a","schema":"b"}', b"x" * 1_048_577],
    ids=("empty", "utf8", "object", "array", "null", "duplicate", "oversize"),
)
def test_malformed_record_fails_closed(data):
    action, lineage, pin = public_values()
    with pytest.raises(PrivateFactsDenied):
        parse_live_lineage_record(data, lineage=lineage, action=action, pin=pin)


@pytest.mark.parametrize("change", ["missing", "extra", "nested", "bool", "float", "spacing"])
def test_no_partial_type_confused_or_noncanonical_record(change):
    action, lineage, pin = public_values()
    record = value(action, lineage, pin)
    if change == "missing":
        record.pop("anchor_id")
    elif change == "extra":
        record["authorized"] = "true"
    elif change == "nested":
        record["anchor_id"] = {"value": record["anchor_id"]}
    elif change == "bool":
        record["journal_revision"] = True
    elif change == "float":
        record["journal_revision"] = 1.0
    data = (
        json.dumps(record, separators=(",", ":")).encode()
        if change in {"spacing", "float"}
        else rfc8785.dumps(record)
    )
    with pytest.raises(PrivateFactsDenied):
        parse_live_lineage_record(data, lineage=lineage, action=action, pin=pin)


@pytest.mark.parametrize(
    ("field", "changed"),
    [
        ("journal_id", uid(900)),
        ("journal_revision", 2),
        ("journal_trust_revision", 2),
        ("journal_head_digest", digest(b"fork")),
        ("installation_id", uid(901)),
        ("anchor_id", uid(902)),
        ("source_id", uid(903)),
        ("lineage_digest", digest(b"stale")),
        ("head_action_digest", digest(b"action")),
        ("confirmation_id", uid(904)),
        ("original_confirmation_digest", digest(b"confirmation")),
        ("initializer_ref", "initializer/other"),
        ("policy_digest", digest(b"policy")),
        ("designation_digest", digest(b"designation")),
        ("semantic_revision", 2),
        ("predecessor_digest", digest(b"predecessor")),
        ("status", "REVOKED"),
    ],
)
def test_every_current_head_fact_is_exact(field, changed):
    action, lineage, pin = public_values()
    with pytest.raises(PrivateFactsDenied):
        parse_live_lineage_record(
            raw(action, lineage, pin, **{field: changed}),
            lineage=lineage,
            action=action,
            pin=pin,
        )


def test_stale_terminal_predecessor_and_public_alias_fail_closed():
    action, lineage, pin = public_values()
    terminal = replace(lineage, statuses=("REVOKED",))
    with pytest.raises(PrivateFactsDenied):
        parse_live_lineage_record(
            raw(action, lineage, pin), lineage=terminal, action=action, pin=pin
        )
    _, successor_lineage = history()
    successor = successor_lineage.actions[-1]
    changed = replace(successor, predecessor_digest=digest(b"wrong"))
    with pytest.raises(PrivateFactsDenied):
        parse_live_lineage_record(
            raw(
                successor,
                successor_lineage,
                successor.confirmation.pin,
            ),
            lineage=successor_lineage,
            action=changed,
            pin=successor.confirmation.pin,
        )
    alias = copy.deepcopy(lineage)
    object.__setattr__(alias, "anchor_id", uid(999))
    with pytest.raises(PrivateFactsDenied):
        parse_live_lineage_record(raw(action, lineage, pin), lineage=alias, action=action, pin=pin)


def test_concurrent_reads_are_deterministic_without_shared_authority_state():
    action, lineage, pin = public_values()
    data = raw(action, lineage, pin)
    with ThreadPoolExecutor(8) as pool:
        results = list(
            pool.map(
                lambda _: parse_live_lineage_record(data, lineage=lineage, action=action, pin=pin),
                range(64),
            )
        )
    assert results == [digest(data)] * 64


def setup_reader(tmp_path, confirmation):
    path = tmp_path / LINEAGE_RECORD_FILE
    path.write_bytes(b"placeholder")
    provision_fixture_acl(path, process_account())
    files = _WindowsFactFiles(str(tmp_path))
    handle = files._open(str(path), directory=False)
    try:
        identity = files._check(handle, str(path), directory=False)[:2]
    finally:
        files._close([handle])
    policy = replace(confirmation._files._policy, record_identity=identity)
    return (
        _LivePolicyLineageSnapshots(
            trusted_root=str(tmp_path),
            confirmation_snapshots=confirmation,
            lineage_policy=policy,
        ),
        path,
    )


def test_native_confirmation_to_live_lineage_handoff_and_stale_reuse_denial(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        confirmation, designation, confirmation_path, _, policy = setup(fx, tmp_path)
        reader, lineage_path = setup_reader(tmp_path, confirmation)
        with live(fx, confirmation, designation, policy) as inputs:
            expected_payload = _bind_canonical(inputs, confirmation_path)
            lineage_path.write_bytes(raw(inputs["action"], inputs["lineage"], inputs["pin_facts"]))
            with (
                confirmation._open_snapshot(**inputs) as confirmation_handle,
                reader._open_current(
                    confirmation_handle=confirmation_handle,
                    expected_payload=expected_payload,
                    action=inputs["action"],
                    lineage=inputs["lineage"],
                ) as handle,
            ):
                reader._require_current(
                    handle,
                    confirmation_handle=confirmation_handle,
                    expected_payload=expected_payload,
                    action=inputs["action"],
                    lineage=inputs["lineage"],
                )
                with pytest.raises(OSError):
                    lineage_path.write_bytes(b"replacement")
                with pytest.raises(PrivateFactsDenied):
                    reader._require_current(
                        handle,
                        confirmation_handle=confirmation_handle,
                        expected_payload=replace(expected_payload, replay_id=uid(999)),
                        action=inputs["action"],
                        lineage=inputs["lineage"],
                    )
                with pytest.raises(PrivateFactsDenied):
                    reader._require_current(
                        handle,
                        confirmation_handle=confirmation_handle,
                        expected_payload=expected_payload,
                        action=inputs["action"],
                        lineage=inputs["lineage"],
                    )


def test_native_lineage_file_identity_is_distinct_and_required(tmp_path):
    if not native():
        return
    with fixture(tmp_path) as fx:
        confirmation, _, _, _, _ = setup(fx, tmp_path)
        with pytest.raises(PrivateFactsDenied):
            _LivePolicyLineageSnapshots(
                trusted_root=str(tmp_path),
                confirmation_snapshots=confirmation,
                lineage_policy=confirmation._files._policy,
            )
        reader, path = setup_reader(tmp_path, confirmation)
        assert path.name == LINEAGE_RECORD_FILE
        assert reader._files._policy.record_identity != confirmation._files._policy.record_identity
        assert set(value(public_action(), *public_values()[1:]).keys()) == FIELDS
