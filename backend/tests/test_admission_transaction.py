"""Admission journal transaction ownership and commit-boundary regression."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from backend.bootstrap_authority.admission_attempt import AdmissionAttemptDenied
from backend.bootstrap_authority.admission_transaction import (
    AdmissionTransactionDenied,
    _AdmissionCommitOutcome,
    _AdmissionJournalTransactionOwner,
)
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.tests.test_admission_attempt import live_attempt
from backend.tests.test_bootstrap_private_pin_reader import native

pytest_plugins = ("backend.tests.test_currentness_witness_handoff",)


def owner(value):
    provider, _, _, _, context, _ = value
    return _AdmissionJournalTransactionOwner(
        attempts=provider,
        journal_repository=context[7]._journal,
    )


def commit(value):
    provider, attempt, witness, arguments, _, _ = value
    return owner(value).commit(
        attempt,
        currentness_witness=witness,
        **arguments,
    )


def test_commit_is_only_success_linearization_point(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, arguments, context, _ = value
        journal_session = context[7]._journal.session
        original = journal_session.commit
        observed = []

        def committed():
            assert context[7]._journal.read_public_head().revision == 2
            observed.append("commit")
            original()

        journal_session.commit = committed
        result = commit(value)
        assert observed == ["commit"]
        assert result.outcome is _AdmissionCommitOutcome.COMMITTED
        assert result.identity.event_revision == 2
        assert result.identity.event_digest.startswith("sha256:")
        assert result.identity.attempt_id
        with pytest.raises(AdmissionAttemptDenied):
            provider._require_prepared(
                attempt,
                currentness_witness=witness,
                **arguments,
            )
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 2


def test_append_and_flush_are_not_success(tmp_path, currentness_journal_engine, monkeypatch):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner = owner(value)
        journal = value[4][7]._journal
        original = journal.append_public_event

        def fail_after_flush(*args, **kwargs):
            original(*args, **kwargs)
            raise OSError("after flush")

        monkeypatch.setattr(journal, "append_public_event", fail_after_flush)
        result = commit(value)
        assert result.outcome is _AdmissionCommitOutcome.NOT_COMMITTED
        assert transaction_owner is not None
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 1


def test_commit_exception_is_unknown_even_when_commit_happened(
    tmp_path, currentness_journal_engine
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, arguments, context, _ = value
        journal_session = context[7]._journal.session
        original = journal_session.commit

        def lose_response():
            original()
            raise ConnectionError("commit response lost")

        journal_session.commit = lose_response
        result = commit(value)
        assert result.outcome is _AdmissionCommitOutcome.RECONCILIATION_REQUIRED
        assert result.identity.journal_id
        with pytest.raises(AdmissionTransactionDenied):
            owner(value).commit(
                attempt,
                currentness_witness=witness,
                **arguments,
            )
        assert not provider._records
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 2


def test_commit_exception_never_guesses_not_committed(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        journal_session = value[4][7]._journal.session

        def fail_during_commit():
            raise ConnectionError("commit transport failed")

        journal_session.commit = fail_during_commit
        result = commit(value)
        assert result.outcome is _AdmissionCommitOutcome.RECONCILIATION_REQUIRED
        assert result.identity.event_id
        assert not journal_session.in_transaction()
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 1


@pytest.mark.parametrize("failure", ["append", "final-guard", "rollback"])
def test_definite_failure_rolls_back_and_consumes_without_resurrection(
    tmp_path, currentness_journal_engine, monkeypatch, failure
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        provider, attempt, witness, arguments, context, _ = value
        transaction_owner = owner(value)
        journal_session = context[7]._journal.session
        if failure == "append":
            monkeypatch.setattr(
                context[7]._journal,
                "append_public_event",
                Mock(side_effect=OSError("append failed")),
            )
        elif failure == "final-guard":
            monkeypatch.setattr(
                transaction_owner,
                "_require_final_guard",
                Mock(side_effect=OSError("guard moved")),
            )
        else:
            original = journal_session.rollback

            def rollback_failure():
                original()
                raise OSError("cleanup failed")

            monkeypatch.setattr(journal_session, "rollback", rollback_failure)
            monkeypatch.setattr(
                context[7]._journal,
                "append_public_event",
                Mock(side_effect=OSError("append failed")),
            )
        result = transaction_owner.commit(
            attempt,
            currentness_witness=witness,
            **arguments,
        )
        if failure == "rollback":
            monkeypatch.setattr(journal_session, "rollback", original)
        assert result.outcome is _AdmissionCommitOutcome.NOT_COMMITTED
        assert not provider._records
        with pytest.raises(AdmissionAttemptDenied):
            provider._require_prepared(
                attempt,
                currentness_witness=witness,
                **arguments,
            )
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 1


@pytest.mark.parametrize("attack", [object(), True, 1, None])
def test_forged_or_copied_fields_cannot_call_owner(tmp_path, currentness_journal_engine, attack):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        _, _, witness, arguments, _, _ = value
        with pytest.raises(AdmissionTransactionDenied):
            owner(value).commit(
                attack,
                currentness_witness=witness,
                **arguments,
            )


def test_wrong_journal_owner_is_denied(tmp_path, currentness_journal_engine):
    if not native():
        return
    with (
        live_attempt(tmp_path, currentness_journal_engine) as value,
        Session(currentness_journal_engine) as other,
        pytest.raises(AdmissionTransactionDenied),
    ):
        _AdmissionJournalTransactionOwner(
            attempts=value[0],
            journal_repository=JournalRepository(other),
        )


def test_final_guard_rechecks_private_lineage_after_append(
    tmp_path, currentness_journal_engine, monkeypatch
):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner = owner(value)
        journal = value[4][7]._journal
        correlation = value[4][6]
        handle = value[3]["correlation_handle"]
        original = journal.append_public_event

        def move_lineage(*args, **kwargs):
            receipt = original(*args, **kwargs)
            correlation._records.pop(handle)
            return receipt

        monkeypatch.setattr(journal, "append_public_event", move_lineage)
        result = transaction_owner.commit(
            value[1],
            currentness_witness=value[2],
            **value[3],
        )
        assert result.outcome is _AdmissionCommitOutcome.NOT_COMMITTED
    with Session(currentness_journal_engine) as session:
        assert JournalRepository(session).read_public_head().revision == 1


def test_same_attempt_has_at_most_one_commit_winner(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        transaction_owner = owner(value)
        result = transaction_owner.commit(
            value[1],
            currentness_witness=value[2],
            **value[3],
        )
        assert result.outcome is _AdmissionCommitOutcome.COMMITTED
        with pytest.raises(AdmissionTransactionDenied):
            transaction_owner.commit(
                value[1],
                currentness_witness=value[2],
                **value[3],
            )


def test_result_is_not_admission_or_retry_capability(tmp_path, currentness_journal_engine):
    if not native():
        return
    with live_attempt(tmp_path, currentness_journal_engine) as value:
        result = commit(value)
        for name in ("admit", "authorize", "rights", "retry", "reconcile", "receipt"):
            assert not hasattr(result, name)
