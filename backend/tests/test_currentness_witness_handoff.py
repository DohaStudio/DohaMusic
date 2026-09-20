"""Single-attempt CurrentnessWitness handoff regression; never admission tests."""

from __future__ import annotations

import copy
import pickle
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from threading import Barrier
from unittest.mock import Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.currentness_witness_handoff import (
    CurrentnessWitnessHandoffDenied,
    _CurrentnessWitnessHandoff,
)
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.bootstrap_authority.journal_schema_v1 import migrate_empty_journal
from backend.bootstrap_authority.witness_lifetime import WitnessLifetimeDenied
from backend.tests.test_bootstrap_lifecycle_journal import JOURNAL
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_confirmation_lineage_correlation import correlated
from backend.tests.test_provisioning_authority_source import uid


@pytest.fixture
def currentness_journal_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'currentness-journal.sqlite'}")
    with engine.begin() as connection:
        migrate_empty_journal(connection)
    with Session(engine) as session, session.begin():
        JournalRepository(session).initialize_public_identity(JOURNAL)
    yield engine
    engine.dispose()


@contextmanager
def live_handoff(tmp_path, engine):
    with correlated(tmp_path, engine, register_currentness=False) as context:
        correlations, call, observations, authenticity = context
        with correlations._open_correlation(**call) as correlation_handle:
            lifetime = correlations._authenticity._confirmation._serialization._lifetime
            assert len(lifetime._attempts) == 1
            attempt = next(iter(lifetime._attempts))
            handoff = _CurrentnessWitnessHandoff(
                correlations=correlations,
                witness_lifetime=lifetime,
            )
            exact_scope = call["pin_facts"].binding.affected_scopes[0]
            yield (
                handoff,
                attempt,
                correlation_handle,
                exact_scope,
                call,
                lifetime,
                correlations,
                observations,
                authenticity,
            )


def issue_args(context):
    handoff, attempt, correlation_handle, exact_scope, call, *_ = context
    return handoff, {
        "attempt": attempt,
        "correlation_handle": correlation_handle,
        "exact_scope": exact_scope,
        **call,
    }


def test_native_witness_is_opaque_single_attempt_and_not_admission(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        with handoff._open_witness(**args) as witness:
            handoff._require_current(witness, **args)
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with pytest.raises(TypeError, match="OPAQUE_HANDLE"):
                    operation(witness)
            for operation in ("admit", "revalidate"):
                with pytest.raises(CurrentnessUnavailable):
                    ports = UnavailableCurrentnessPorts()
                    if operation == "admit":
                        ports.admit_with_private_ceremony_witness(witness)
                    else:
                        ports.revalidate_private_currentness_witness(witness)
            for name in ("admit", "authorize", "rights", "durable"):
                assert not hasattr(witness, name)
        with pytest.raises(CurrentnessWitnessHandoffDenied):
            handoff._require_current(witness, **args)


def test_duplicate_issue_is_denied_without_destroying_winner(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        with handoff._open_witness(**args) as winner:
            with (
                pytest.raises(CurrentnessWitnessHandoffDenied),
                handoff._open_witness(**args),
            ):
                pytest.fail("one attempt issued a second witness")
            handoff._require_current(winner, **args)


def test_actual_preflight_failure_permanently_rejects_attempt(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        wrong_scope = (uid(904), uid(905), uid(906))
        with (
            pytest.raises(CurrentnessWitnessHandoffDenied),
            handoff._open_witness(**dict(args, exact_scope=wrong_scope)),
        ):
            pytest.fail("wrong scope issued a witness")
        with (
            pytest.raises(CurrentnessWitnessHandoffDenied),
            handoff._open_witness(**args),
        ):
            pytest.fail("rejected attempt was reactivated")


def test_foreign_attempt_and_witness_cannot_destroy_live_attempt(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        forged = dict(args, attempt=object())
        with (
            pytest.raises(CurrentnessWitnessHandoffDenied),
            handoff._open_witness(**forged),
        ):
            pytest.fail("foreign attempt issued a witness")
        with (
            pytest.raises(CurrentnessWitnessHandoffDenied),
            handoff._open_witness(**dict(args, correlation_handle=object())),
        ):
            pytest.fail("foreign correlation issued a witness")
        with handoff._open_witness(**args) as witness:
            with pytest.raises(CurrentnessWitnessHandoffDenied):
                handoff._require_current(object(), **args)
            handoff._require_current(witness, **args)


@pytest.mark.parametrize(
    "attack",
    [
        "attempt",
        "correlation",
        "scope",
        "lease",
        "lease-release",
        "transaction",
        "provider-rejection",
        "correlation-stale",
        "journal-head",
        "lineage",
        "pin",
        "source",
        "material",
        "confirmation",
    ],
)
def test_native_witness_revalidation_failure_is_one_way(
    tmp_path, currentness_journal_engine, attack
):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        lifetime, correlations, observations = context[5:8]
        original = dict(args)
        with handoff._open_witness(**args) as witness:
            if attack == "attempt":
                args["attempt"] = object()
            elif attack == "correlation":
                args["correlation_handle"] = object()
            elif attack == "scope":
                args["exact_scope"] = (uid(901), uid(902), uid(903))
            elif attack == "lease":
                args["lease"] = object()
            elif attack == "lease-release":
                lifetime._release_lease(original["lease"])
            elif attack == "transaction":
                args["session"].rollback()
                args["session"].begin()
            elif attack == "provider-rejection":
                lifetime._reject_attempt(original["attempt"], witness=witness)
            elif attack == "correlation-stale":
                correlations._records.pop(original["correlation_handle"])
            elif attack == "journal-head":
                current = observations._journal.read_public_head()
                observations._journal.read_public_head = Mock(
                    return_value=replace(current, revision=current.revision + 1)
                )
            elif attack == "lineage":
                args["fresh_lineage"] = object()
            elif attack == "pin":
                args["pin_facts"] = object()
            elif attack == "source":
                args["expected_source"] = object()
            elif attack == "confirmation":
                args["expected_payload"] = object()
            else:
                args["expected_material"] = replace(args["expected_material"], material_revision=2)
            with pytest.raises(CurrentnessWitnessHandoffDenied):
                handoff._require_current(witness, **args)
            with pytest.raises(CurrentnessWitnessHandoffDenied):
                handoff._require_current(witness, **original)
            assert witness not in handoff._records


def test_bool_int_and_hostile_objects_cannot_forge_witness(tmp_path, currentness_journal_engine):
    if not native():
        return

    class Hostile:
        def __hash__(self):
            raise AssertionError("hostile hash reached")

        def __eq__(self, other):
            raise AssertionError("hostile equality reached")

    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        for forged in (True, 1, Hostile()):
            with pytest.raises(CurrentnessWitnessHandoffDenied):
                handoff._require_current(forged, **args)
        for forged in (True, 1, Hostile()):
            with (
                pytest.raises(CurrentnessWitnessHandoffDenied),
                handoff._open_witness(**dict(args, attempt=forged)),
            ):
                pytest.fail("forged attempt issued a witness")
        with handoff._open_witness(**args) as witness:
            handoff._require_current(witness, **args)


def test_concurrent_issue_has_exactly_one_winner(tmp_path, currentness_journal_engine, monkeypatch):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        lifetime, correlations = context[5:7]
        attempt_record = lifetime._lookup(args["attempt"])
        correlation_record = correlations._records[args["correlation_handle"]]
        binding = correlation_record.pin_facts.binding
        monkeypatch.setattr(
            handoff,
            "_preflight",
            lambda **kwargs: (attempt_record, correlation_record, binding),
        )
        monkeypatch.setattr(correlations, "_require_open", lambda *a, **kw: None)
        monkeypatch.setattr(correlations, "_abandon_all", lambda *a, **kw: None)
        monkeypatch.setattr(handoff._serialization, "_require_live", lambda *a, **kw: None)
        monkeypatch.setattr(lifetime, "_require_live_binding", lambda *a, **kw: None)
        barrier = Barrier(2)

        def issue(_):
            manager = handoff._open_witness(**args)
            try:
                manager.__enter__()
            except CurrentnessWitnessHandoffDenied:
                barrier.wait()
                return "denied"
            barrier.wait()
            manager.__exit__(None, None, None)
            return "winner"

        with ThreadPoolExecutor(max_workers=2) as executor:
            assert sorted(executor.map(issue, range(2))) == ["denied", "winner"]


def test_consumer_exception_rejects_witness_and_attempt(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        lifetime = context[5]
        with (
            pytest.raises(CurrentnessWitnessHandoffDenied),
            handoff._open_witness(**args),
        ):
            raise OSError("injected consumer failure")
        assert not handoff._records
        with pytest.raises(WitnessLifetimeDenied):
            lifetime._lookup(args["attempt"])


def test_cleanup_failure_quarantines_witness_and_attempt(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_handoff(tmp_path, currentness_journal_engine) as context:
        handoff, args = issue_args(context)
        lifetime, correlations = context[5:7]
        manager = handoff._open_witness(**args)
        witness = manager.__enter__()
        original = correlations._abandon_all
        monkeypatch.setattr(
            correlations,
            "_abandon_all",
            Mock(side_effect=OSError("injected cleanup failure")),
        )
        with pytest.raises(CurrentnessWitnessHandoffDenied):
            manager.__exit__(None, None, None)
        monkeypatch.setattr(correlations, "_abandon_all", original)
        assert witness not in handoff._records
        with pytest.raises(WitnessLifetimeDenied):
            lifetime._lookup(args["attempt"])


def test_constructor_requires_shared_lifetime():
    from backend.bootstrap_authority.witness_lifetime import _ProviderWitnessLifetime

    for correlations, lifetime in (
        (object(), object()),
        (None, None),
        (True, _ProviderWitnessLifetime()),
    ):
        with pytest.raises(CurrentnessWitnessHandoffDenied):
            _CurrentnessWitnessHandoff(
                correlations=correlations,
                witness_lifetime=lifetime,
            )
