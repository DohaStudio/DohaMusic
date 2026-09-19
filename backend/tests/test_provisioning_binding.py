"""Disposable PUBLIC comparison fixtures, never authenticated human/source proof."""

import copy
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, fields, replace
from uuid import UUID

import pytest

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.bootstrap_authority.pin_facts import PinComparisonFacts
from backend.bootstrap_authority.provisioning_binding import (
    InitializerConfirmationFacts,
    PolicyLineageFacts,
    PolicySnapshotFacts,
    ProvisioningActionFacts,
    ProvisioningBindingDenied,
    action_comparison_digest,
    policy_snapshot_digest,
    require_action_binding,
    require_current_lineage_matches,
    require_successor_matches,
)
from backend.tests.test_bootstrap_witness_lifetime import SCOPE, binding
from backend.tests.test_designation_source_custody import ACCOUNT, SYSTEM, acl, policy


def uid(number):
    return str(UUID(int=number))


def action(revision=1, predecessor=None, salt=0):
    pin = PinComparisonFacts(SCOPE[0], digest(b"installation public proof"), binding())
    snapshot = PolicySnapshotFacts(
        uid(50), revision, SCOPE[0], pin.installation_proof_key_fingerprint, uid(51), policy()
    )
    confirmation = InitializerConfirmationFacts(
        uid(100 + revision + salt),
        "confirmation/test",
        digest(b"unsigned original confirmation"),
        "initializer/test",
        uid(200 + revision + salt),
        policy_snapshot_digest(snapshot),
        pin,
    )
    return ProvisioningActionFacts(confirmation.action_id, snapshot, confirmation, predecessor)


def history():
    first = action()
    second = action(2, action_comparison_digest(first))
    old = PolicyLineageFacts(uid(52), SCOPE[0], uid(51), (first,), ("ACTIVE",))
    new = replace(old, actions=(first, second), statuses=("SUPERSEDED", "ACTIVE"))
    return old, new


def test_binding_is_immutable_public_comparison_only():
    record = action()
    assert (
        require_action_binding(
            action=record,
            policy=record.policy,
            pin=record.confirmation.pin,
            confirmation=record.confirmation,
        )
        is None
    )
    assert policy_snapshot_digest(copy.deepcopy(record.policy)) == policy_snapshot_digest(
        record.policy
    )
    assert action_comparison_digest(copy.deepcopy(record)) == action_comparison_digest(record)
    with pytest.raises(FrozenInstanceError):
        record.action_id = uid(999)
    assert "initializer/test" not in repr(record)
    ports = UnavailableCurrentnessPorts()
    for value in (record, record.policy, record.confirmation, history()[0], True):
        with pytest.raises(CurrentnessUnavailable):
            ports.admit_with_private_ceremony_witness(value)
        with pytest.raises(CurrentnessUnavailable):
            ports.revalidate_private_currentness_witness(value)


@pytest.mark.parametrize("name", [field.name for field in fields(PolicySnapshotFacts)])
def test_every_policy_field_bound_in_snapshot_digest(name):
    original = action().policy
    changes = {
        "policy_id": uid(55),
        "revision": 2,
        "installation_id": uid(56),
        "installation_proof_key_fingerprint": digest(b"different proof"),
        "source_id": uid(57),
        "custody": replace(policy(), record_identity=(2**64 - 1, b"z" * 16)),
        "profile_version": 2,
    }
    if name == "profile_version":
        with pytest.raises(ProvisioningBindingDenied):
            replace(original, profile_version=2)
    else:
        changed = replace(original, **{name: changes[name]})
        assert policy_snapshot_digest(original) != policy_snapshot_digest(changed)
        with pytest.raises(ProvisioningBindingDenied):
            replace(action(), policy=changed)


@pytest.mark.parametrize(
    "change",
    [
        {"root_identity": (2, b"r" * 16)},
        {"record_identity": (2, b"f" * 16)},
        {"owner_sid": SYSTEM},
        {"allowed_sids": (ACCOUNT,), "dacl": acl(ACCOUNT)},
        {"dacl": acl(SYSTEM, ACCOUNT)},
    ],
)
def test_complete_custody_not_path_or_sid_digest_only(change):
    original = action().policy
    changed = replace(original, custody=replace(policy(), **change))
    assert policy_snapshot_digest(original) != policy_snapshot_digest(changed)


@pytest.mark.parametrize("name", [field.name for field in fields(InitializerConfirmationFacts)])
def test_confirmation_exact_link_and_external_comparison(name):
    record = action()
    changes = {
        "provenance_id": uid(999),
        "original_confirmation_ref": "confirmation/other",
        "original_confirmation_digest": digest(b"other original"),
        "initializer_ref": "initializer/other",
        "action_id": uid(998),
        "policy_digest": digest(b"other policy"),
        "pin": replace(
            record.confirmation.pin, binding=replace(binding(), designation_id=uid(997))
        ),
    }
    changed = replace(record.confirmation, **{name: changes[name]})
    with pytest.raises(ProvisioningBindingDenied):
        require_action_binding(
            action=record, policy=record.policy, pin=record.confirmation.pin, confirmation=changed
        )


@pytest.mark.parametrize("bad", [True, 1.0, 0, -1, 2**53, "1", None])
def test_revision_and_profile_type_confusion_denied(bad):
    with pytest.raises(ProvisioningBindingDenied):
        replace(action().policy, revision=bad)
    with pytest.raises(ProvisioningBindingDenied):
        replace(action().policy, profile_version=bad)


def test_custom_equality_hash_never_runs():
    class Hostile(str):
        def __eq__(self, other):
            pytest.fail("custom equality")

        def __hash__(self):
            pytest.fail("custom hash")

    for name in ("policy_id", "installation_id", "source_id", "installation_proof_key_fingerprint"):
        with pytest.raises(ProvisioningBindingDenied):
            replace(action().policy, **{name: Hostile(getattr(action().policy, name))})
    for name in ("provenance_id", "initializer_ref", "action_id", "policy_digest"):
        with pytest.raises(ProvisioningBindingDenied):
            replace(action().confirmation, **{name: Hostile(getattr(action().confirmation, name))})


@pytest.mark.parametrize("bad", [{}, True, object(), "ACTIVE", None])
def test_public_substitution_is_denied(bad):
    record = action()
    with pytest.raises(ProvisioningBindingDenied):
        require_action_binding(
            action=bad,
            policy=record.policy,
            pin=record.confirmation.pin,
            confirmation=record.confirmation,
        )


def test_prefix_successor_and_stale_cas_preconditions_only():
    old, new = history()
    assert (
        require_successor_matches(previous=old, expected=copy.deepcopy(old), successor=new) is None
    )
    with pytest.raises(ProvisioningBindingDenied):
        require_successor_matches(previous=new, expected=old, successor=new)
    with pytest.raises(ProvisioningBindingDenied):
        require_current_lineage_matches(observed=old, expected=new)
    # Multiple callers can pass a PURE predicate: no storage CAS winner claimed.
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert (
            list(
                pool.map(
                    lambda _: require_successor_matches(previous=old, expected=old, successor=new),
                    range(8),
                )
            )
            == [None] * 8
        )


@pytest.mark.parametrize(
    "statuses", [("ACTIVE", "ACTIVE"), ("SUPERSEDED", "REVOKED"), ("SUPERSEDED", "SUPERSEDED")]
)
def test_duplicate_current_and_terminal_head_denied(statuses):
    _, new = history()
    with pytest.raises(ProvisioningBindingDenied):
        candidate = replace(new, statuses=statuses)
        require_current_lineage_matches(observed=candidate, expected=candidate)


@pytest.mark.parametrize(
    "change", ["anchor", "prefix", "terminal", "duplicate", "partial", "reset"]
)
def test_replace_upsert_truncate_reset_and_prefix_rewrite_denied(change):
    old, new = history()
    with pytest.raises(ProvisioningBindingDenied):
        if change == "anchor":
            candidate = replace(new, anchor_id=uid(900))
        elif change == "prefix":
            other = action(salt=9)
            candidate = replace(
                new, actions=(other, action(2, action_comparison_digest(other), salt=9))
            )
        elif change == "terminal":
            candidate = replace(new, statuses=("REVOKED", "ACTIVE"))
        elif change == "duplicate":
            candidate = replace(new, actions=(old.actions[0], old.actions[0]))
        elif change == "partial":
            candidate = replace(new, actions=(new.actions[-1],), statuses=("ACTIVE",))
        else:
            candidate = replace(new, actions=(action(salt=10),), statuses=("ACTIVE",))
        require_successor_matches(previous=old, expected=old, successor=candidate)


@pytest.mark.parametrize("field", ["predecessor_digest", "confirmation", "policy", "action_id"])
def test_malformed_or_wrong_predecessor_action_denied(field):
    _, new = history()
    record = new.actions[-1]
    changes = {
        "predecessor_digest": None,
        "confirmation": {},
        "policy": None,
        "action_id": uid(999),
    }
    with pytest.raises(ProvisioningBindingDenied):
        replace(record, **{field: changes[field]})


def test_old_confirmation_replay_in_new_action_denied():
    old, new = history()
    first = old.actions[0]
    with pytest.raises(ProvisioningBindingDenied):
        replace(new.actions[-1], confirmation=first.confirmation)
    second = new.actions[-1]
    repeated = replace(
        second,
        confirmation=replace(second.confirmation, provenance_id=first.confirmation.provenance_id),
    )
    with pytest.raises(ProvisioningBindingDenied):
        replace(new, actions=(first, repeated))


def test_replaced_terminal_prefix_never_reactivated_or_rewritten():
    _, new = history()
    third = action(3, action_comparison_digest(new.actions[-1]))
    successor = replace(
        new, actions=(*new.actions, third), statuses=("SUPERSEDED", "SUPERSEDED", "ACTIVE")
    )
    require_successor_matches(previous=new, expected=new, successor=successor)
    with pytest.raises(ProvisioningBindingDenied):
        replace(successor, statuses=("ACTIVE", "SUPERSEDED", "ACTIVE"))
    changed = replace(successor, statuses=("REVOKED", "SUPERSEDED", "ACTIVE"))
    with pytest.raises(ProvisioningBindingDenied):
        require_successor_matches(previous=new, expected=new, successor=changed)


@pytest.mark.parametrize("field", [field.name for field in fields(binding())])
def test_pin_binding_every_field_revalidated_and_compared(field):
    record = action()
    hostile = copy.deepcopy(record.confirmation.pin)
    # Bypass frozen construction to simulate malformed in-process PUBLIC values.
    object.__setattr__(hostile.binding, field, True)
    with pytest.raises(ProvisioningBindingDenied):
        require_action_binding(
            action=record, policy=record.policy, pin=hostile, confirmation=record.confirmation
        )


@pytest.mark.parametrize(
    "actions,statuses",
    [((), ()), ([], []), ((None,) * 257, ("ACTIVE",) * 257), ((None,), ()), ((None,), ("ACTIVE",))],
)
def test_bounded_complete_lineage_required(actions, statuses):
    with pytest.raises(ProvisioningBindingDenied):
        PolicyLineageFacts(uid(52), SCOPE[0], uid(51), actions, statuses)


def test_single_installation_complete_manifest_not_silently_filtered():
    record = action()
    pin = record.confirmation.pin
    multi = replace(
        pin,
        binding=replace(
            binding(),
            affected_scopes=tuple(
                sorted((*binding().affected_scopes, (uid(999), uid(998), uid(997))))
            ),
        ),
    )
    with pytest.raises(ProvisioningBindingDenied):
        require_action_binding(
            action=record, policy=record.policy, pin=multi, confirmation=record.confirmation
        )


def test_observed_toctou_facts_change_is_not_old_history_currentness():
    old, new = history()
    require_current_lineage_matches(observed=old, expected=old)
    with pytest.raises(ProvisioningBindingDenied):
        require_current_lineage_matches(observed=old, expected=new)
    # Comparison cannot detect an unobserved restore or permanently abandon a
    # live lease. That remains existing context/independent-reader responsibility.
    require_current_lineage_matches(observed=old, expected=old)
