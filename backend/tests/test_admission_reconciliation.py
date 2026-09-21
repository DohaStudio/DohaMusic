"""Read-only Admission Commit Reconciler regression."""

from __future__ import annotations

import copy
import pickle
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.bootstrap_authority.admission_reconciliation import (
    AdmissionReconciliationDenied,
    _AdmissionCommitReconciler,
    _ReconciliationOutcome,
)
from backend.bootstrap_authority.admission_transaction import (
    _AdmissionCommitOutcome,
    _AdmissionJournalTransactionOwner,
)
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.tests.test_admission_attempt import live_attempt
from backend.tests.test_bootstrap_lifecycle_journal import append, event
from backend.tests.test_bootstrap_private_pin_reader import native

pytest_plugins = ("backend.tests.test_currentness_witness_handoff",)


def ambiguous(value, *, durable):
    provider, attempt, witness, arguments, context, _ = value
    transaction_owner = _AdmissionJournalTransactionOwner(
        attempts=provider,
        journal_repository=context[7]._journal,
    )
    journal_session = context[7]._journal.session
    original = journal_session.commit

    def lose_response():
        if durable:
            original()
        raise ConnectionError("commit response lost")

    journal_session.commit = lose_response
    result = transaction_owner.commit(
        attempt,
        currentness_witness=witness,
        **arguments,
    )
    assert result.outcome is _AdmissionCommitOutcome.RECONCILIATION_REQUIRED
    return transaction_owner, result


def reconciler(transaction_owner, engine):
    return _AdmissionCommitReconciler(
        transaction_owner=transaction_owner,
        journal_engine=engine,
    )


def append_conflict(engine, result):
    payload, expected = event(
        2,
        result.identity.expected_head_digest,
        "REVOKE",
        "root/test-1",
        None,
    )
    with Session(engine) as session, session.begin():
        append(session, payload, expected)


def test_committed_exact_and_replay_are_read_only(tmp_path, currentness_journal_engine):
    if not native():
        return
    statements = []

    def observe(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lstrip().split(maxsplit=1)[0].upper())

    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=True)
        before = ambiguous_result.identity.event_digest
        reader = reconciler(transaction_owner, currentness_journal_engine)
        sqlalchemy_event.listen(currentness_journal_engine, "before_cursor_execute", observe)
        try:
            first = reader.reconcile(ambiguous_result.reconciliation)
            second = reader.reconcile(ambiguous_result.reconciliation)
        finally:
            sqlalchemy_event.remove(currentness_journal_engine, "before_cursor_execute", observe)
        assert first == second
        assert first.outcome is _ReconciliationOutcome.COMMITTED_EXACT
        assert first.identity.event_digest == before
        assert statements and set(statements) == {"SELECT"}
    with Session(currentness_journal_engine) as session:
        repository = JournalRepository(session)
        assert repository.read_public_head().revision == 2
        assert len(repository.read_verified_events()) == 2


def test_not_committed_requires_exact_complete_predecessor(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=False)
        result = reconciler(transaction_owner, currentness_journal_engine).reconcile(
            ambiguous_result.reconciliation
        )
        assert result.outcome is _ReconciliationOutcome.NOT_COMMITTED
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 1


def test_same_identity_partial_match_is_conflict(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=False)
        append_conflict(currentness_journal_engine, ambiguous_result)
        result = reconciler(transaction_owner, currentness_journal_engine).reconcile(
            ambiguous_result.reconciliation
        )
        assert result.outcome is _ReconciliationOutcome.CONFLICT


def test_truncated_or_malformed_history_is_unavailable(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=False)
        with currentness_journal_engine.begin() as connection:
            connection.exec_driver_sql("DROP TRIGGER deployment_journal_events_delete")
            connection.exec_driver_sql("DELETE FROM deployment_journal_events")
        result = reconciler(transaction_owner, currentness_journal_engine).reconcile(
            ambiguous_result.reconciliation
        )
        assert result.outcome is _ReconciliationOutcome.UNAVAILABLE


def test_head_move_between_snapshots_is_unavailable(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=False)
        reader = reconciler(transaction_owner, currentness_journal_engine)
        original = reader._read_snapshot
        calls = 0

        def moving_snapshot():
            nonlocal calls
            snapshot = original()
            calls += 1
            if calls == 1:
                append_conflict(currentness_journal_engine, ambiguous_result)
            return snapshot

        monkeypatch.setattr(reader, "_read_snapshot", moving_snapshot)
        result = reader.reconcile(ambiguous_result.reconciliation)
        assert result.outcome is _ReconciliationOutcome.UNAVAILABLE


def test_read_failure_and_close_failure_never_become_committed(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=True)
        reader = reconciler(transaction_owner, currentness_journal_engine)
        monkeypatch.setattr(reader, "_read_snapshot", lambda: (_ for _ in ()).throw(OSError()))
        result = reader.reconcile(ambiguous_result.reconciliation)
        assert result.outcome is _ReconciliationOutcome.UNAVAILABLE


def test_connection_close_failure_is_unavailable(tmp_path, currentness_journal_engine, monkeypatch):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=True)
        reader = reconciler(transaction_owner, currentness_journal_engine)
        original = Session.close

        def close_then_fail(session):
            original(session)
            raise OSError("close failed")

        monkeypatch.setattr(Session, "close", close_then_fail)
        result = reader.reconcile(ambiguous_result.reconciliation)
        monkeypatch.setattr(Session, "close", original)
        assert result.outcome is _ReconciliationOutcome.UNAVAILABLE


def test_forged_copied_and_known_outcome_handoffs_are_denied(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=False)
        reader = reconciler(transaction_owner, currentness_journal_engine)
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with pytest.raises(TypeError, match="OPAQUE_RECONCILIATION_HANDOFF"):
                operation(ambiguous_result.reconciliation)
        for forged in (object(), True, 1, ambiguous_result.identity):
            with pytest.raises(AdmissionReconciliationDenied):
                reader.reconcile(forged)


def test_known_commit_result_is_not_a_reconciliation_request(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, arguments, context, _ = value
        transaction_owner = _AdmissionJournalTransactionOwner(
            attempts=provider,
            journal_repository=context[7]._journal,
        )
        committed = transaction_owner.commit(
            attempt,
            currentness_witness=witness,
            **arguments,
        )
        assert committed.outcome is _AdmissionCommitOutcome.COMMITTED
        with pytest.raises(AdmissionReconciliationDenied):
            reconciler(transaction_owner, currentness_journal_engine).reconcile(
                committed.reconciliation
            )


def test_wrong_journal_engine_is_denied(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, _ = ambiguous(value, durable=False)
        from sqlalchemy import create_engine

        other = create_engine(f"sqlite:///{tmp_path / 'other.sqlite'}")
        try:
            with pytest.raises(AdmissionReconciliationDenied):
                _AdmissionCommitReconciler(
                    transaction_owner=transaction_owner,
                    journal_engine=other,
                )
        finally:
            other.dispose()


def test_concurrent_replay_is_deterministic(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=True)
        reader = reconciler(transaction_owner, currentness_journal_engine)
        with ThreadPoolExecutor(max_workers=4) as executor:
            outcomes = tuple(
                executor.map(
                    lambda _: reader.reconcile(ambiguous_result.reconciliation).outcome,
                    range(8),
                )
            )
        assert outcomes == (_ReconciliationOutcome.COMMITTED_EXACT,) * 8


def test_missing_event_never_shortcuts_after_lineage_advance(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=False)
        append_conflict(currentness_journal_engine, ambiguous_result)
        with currentness_journal_engine.begin() as connection:
            # The conflicting row is complete and authoritative. Its absence from
            # an exact-candidate search must not become NOT_COMMITTED.
            count = connection.scalar(text("SELECT count(*) FROM deployment_journal_events"))
        assert count == 2
        result = reconciler(transaction_owner, currentness_journal_engine).reconcile(
            ambiguous_result.reconciliation
        )
        assert result.outcome is _ReconciliationOutcome.CONFLICT


def test_result_is_audit_evidence_not_admission(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner, ambiguous_result = ambiguous(value, durable=True)
        result = reconciler(transaction_owner, currentness_journal_engine).reconcile(
            ambiguous_result.reconciliation
        )
        for name in ("admit", "authorize", "rights", "append", "commit", "retry", "repair"):
            assert not hasattr(result, name)
