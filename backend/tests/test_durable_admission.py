"""Durable Admission orchestration and authority-boundary regression."""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy.orm import Session

from backend.bootstrap_authority.admission_attempt import _AdmissionAttemptProvider
from backend.bootstrap_authority.admission_reconciliation import (
    _AdmissionCommitReconciler,
    _ReconciliationOutcome,
    _ReconciliationResult,
)
from backend.bootstrap_authority.admission_transaction import (
    _AdmissionCommitOutcome,
    _AdmissionCommitResult,
    _AdmissionJournalTransactionOwner,
)
from backend.bootstrap_authority.durable_admission import (
    DurableAdmissionDenied,
    _DurableAdmissionOrchestrator,
    _DurableAdmissionOutcome,
    _DurableAdmissionProvenance,
)
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.tests.test_admission_attempt import candidate
from backend.tests.test_admission_reconciliation import append_conflict
from backend.tests.test_bootstrap_private_pin_reader import native
from backend.tests.test_currentness_witness_handoff import issue_args, live_handoff

pytest_plugins = ("backend.tests.test_currentness_witness_handoff",)


@contextmanager
def live_orchestration(tmp_path, engine):
    with live_handoff(tmp_path, engine) as context:
        handoff, arguments = issue_args(context)
        attempts = _AdmissionAttemptProvider(currentness_handoff=handoff)
        owner = _AdmissionJournalTransactionOwner(
            attempts=attempts,
            journal_repository=context[7]._journal,
        )
        reconciler = _AdmissionCommitReconciler(
            transaction_owner=owner,
            journal_engine=engine,
        )
        orchestrator = _DurableAdmissionOrchestrator(
            attempts=attempts,
            transaction_owner=owner,
            reconciler=reconciler,
        )
        artifact, manifest, expected = candidate(context)
        with handoff._open_witness(**arguments) as witness:
            call = dict(
                currentness_witness=witness,
                artifact=artifact,
                manifest=manifest,
                expected=expected,
                **arguments,
            )
            yield orchestrator, attempts, owner, reconciler, call, context


def journal_revision(engine):
    with Session(engine) as session:
        return JournalRepository(session).read_public_head().revision


def test_direct_commit_is_the_only_direct_success(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, _, _, call, _ = value
        result = orchestrator.admit(**call)
        assert result.outcome is _DurableAdmissionOutcome.COMMITTED_EXACT
        assert result.provenance is _DurableAdmissionProvenance.DIRECT_COMMIT
        assert result.reconciliation is None
        assert result.identity.event_revision == 2
        assert not value[2]._reconciliations
        for name in ("authorize", "rights", "retry", "append", "commit"):
            assert not hasattr(result, name)
    assert journal_revision(currentness_journal_engine) == 2


def test_precommit_failure_is_not_success_or_retry(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, _, _, call, context = value

        def fail(*_args, **_kwargs):
            raise OSError("append unavailable")

        monkeypatch.setattr(context[7]._journal, "append_public_event", fail)
        result = orchestrator.admit(**call)
        assert result.outcome is _DurableAdmissionOutcome.NOT_COMMITTED
        assert result.provenance is _DurableAdmissionProvenance.DIRECT_NOT_COMMITTED
        assert result.reconciliation is None
        assert not value[2]._reconciliations
        with pytest.raises(DurableAdmissionDenied):
            orchestrator.admit(**call)
    assert journal_revision(currentness_journal_engine) == 1


def test_provider_failure_never_reaches_transaction_owner(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, owner, _, call, _ = value
        observed = []
        monkeypatch.setattr(owner, "commit", lambda *_args, **_kwargs: observed.append("commit"))
        with pytest.raises(DurableAdmissionDenied):
            orchestrator.admit(**{**call, "artifact": b"malformed"})
        assert observed == []
    assert journal_revision(currentness_journal_engine) == 1


@pytest.mark.parametrize(
    ("durable", "expected", "provenance"),
    [
        (
            True,
            _DurableAdmissionOutcome.COMMITTED_EXACT,
            _DurableAdmissionProvenance.RECONCILED_COMMIT,
        ),
        (
            False,
            _DurableAdmissionOutcome.NOT_COMMITTED,
            _DurableAdmissionProvenance.RECONCILED_NOT_COMMITTED,
        ),
    ],
)
def test_ambiguous_commit_is_always_reconciled(
    tmp_path, currentness_journal_engine, durable, expected, provenance
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, _, _, call, context = value
        session = context[7]._journal.session
        original = session.commit

        def lose_response():
            if durable:
                original()
            raise ConnectionError("commit response lost")

        session.commit = lose_response
        result = orchestrator.admit(**call)
        assert result.outcome is expected
        assert result.provenance is provenance
        assert result.reconciliation is not None
        replay = orchestrator.reconcile(result.reconciliation)
        assert replay.outcome is expected
        assert replay.identity is result.identity
    assert journal_revision(currentness_journal_engine) == (2 if durable else 1)


def test_reconciliation_conflict_and_unavailable_fail_closed(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, _, reconciler, call, context = value
        context[7]._journal.session.commit = lambda: (_ for _ in ()).throw(ConnectionError())
        monkeypatch.setattr(
            reconciler,
            "_read_snapshot",
            lambda: (_ for _ in ()).throw(OSError("read unavailable")),
        )
        unavailable = orchestrator.admit(**call)
        assert unavailable.outcome is _DurableAdmissionOutcome.UNAVAILABLE
        assert unavailable.provenance is _DurableAdmissionProvenance.RECONCILIATION_UNAVAILABLE
        assert unavailable.reconciliation is not None
        monkeypatch.undo()
        # The predecessor is still exact, so replay converges without a new
        # witness, attempt, append or commit.
        replay = orchestrator.reconcile(unavailable.reconciliation)
        assert replay.outcome is _DurableAdmissionOutcome.NOT_COMMITTED


def test_reconciliation_conflict_never_becomes_success(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, owner, _, call, context = value
        context[7]._journal.session.commit = lambda: (_ for _ in ()).throw(ConnectionError())
        original = orchestrator.reconcile

        def conflict(handoff):
            record = owner._reconciliations[id(handoff)]
            report = type("Report", (), {"identity": record.identity})()
            append_conflict(currentness_journal_engine, report)
            return original(handoff)

        monkeypatch.setattr(orchestrator, "reconcile", conflict)
        result = orchestrator.admit(**call)
        assert result.outcome is _DurableAdmissionOutcome.CONFLICT
        assert result.provenance is _DurableAdmissionProvenance.RECONCILIATION_CONFLICT


def test_forged_component_results_and_wrong_chain_are_denied(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, attempts, owner, reconciler, call, _ = value
        forged = _AdmissionCommitResult(_AdmissionCommitOutcome.COMMITTED, object(), object())
        monkeypatch.setattr(owner, "commit", lambda *_args, **_kwargs: forged)
        with pytest.raises(DurableAdmissionDenied):
            orchestrator.admit(**call)
        with pytest.raises(DurableAdmissionDenied):
            _DurableAdmissionOrchestrator(
                attempts=attempts,
                transaction_owner=owner,
                reconciler=object(),
            )
        assert reconciler is not None
    assert journal_revision(currentness_journal_engine) == 1


def test_forged_reconciliation_result_cannot_become_success(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, _, reconciler, call, context = value
        context[7]._journal.session.commit = lambda: (_ for _ in ()).throw(ConnectionError())
        monkeypatch.setattr(
            reconciler,
            "_read_snapshot",
            lambda: (_ for _ in ()).throw(OSError()),
        )
        unresolved = orchestrator.admit(**call)
        monkeypatch.undo()
        forged = _ReconciliationResult(_ReconciliationOutcome.COMMITTED_EXACT, unresolved.identity)
        monkeypatch.setattr(reconciler, "reconcile", lambda _handoff: forged)
        with pytest.raises(DurableAdmissionDenied):
            orchestrator.reconcile(unresolved.reconciliation)


def test_overlapping_same_witness_has_at_most_one_orchestration_winner(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, owner, _, call, _ = value
        original = owner.commit
        losers = []

        def reenter(*args, **kwargs):
            with pytest.raises(DurableAdmissionDenied):
                orchestrator.admit(**call)
            losers.append("denied")
            return original(*args, **kwargs)

        monkeypatch.setattr(owner, "commit", reenter)
        winner = orchestrator.admit(**call)
        assert losers == ["denied"]
        assert winner.outcome is _DurableAdmissionOutcome.COMMITTED_EXACT
    assert journal_revision(currentness_journal_engine) == 2


def test_result_construction_failure_never_creates_false_return_or_duplicate(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_orchestration(tmp_path, currentness_journal_engine) as value:
        orchestrator, _, _, _, call, _ = value
        monkeypatch.setattr(
            orchestrator,
            "_result",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("consumer failed")),
        )
        with pytest.raises(RuntimeError, match="consumer failed"):
            orchestrator.admit(**call)
        with pytest.raises(DurableAdmissionDenied):
            orchestrator.admit(**call)
    assert journal_revision(currentness_journal_engine) == 2
