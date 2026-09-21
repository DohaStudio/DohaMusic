"""Exact external-journal transaction ownership; never admission authority.

The owner accepts only a live provider-registry AdmissionAttempt.  It adopts the
exact independent journal transaction already bound into that attempt, performs
one append guarded by journal v1 CAS, repeats the non-journal final guards, and
treats only a returned Session.commit() as a known committed result.  An
exception raised by commit is deliberately ambiguous and requires a future
authoritative reconciler; this module never retries it.
"""

from __future__ import annotations

import json
from contextlib import suppress
from dataclasses import dataclass
from enum import Enum
from threading import RLock

from sqlalchemy.orm import Session

from backend.bootstrap_authority.admission_attempt import (
    AdmissionAttemptDenied,
    _AdmissionAttemptProvider,
    _AttemptRecord,
    _correlation_digest,
)
from backend.bootstrap_authority.confirmation_lineage_correlation import (
    _authenticity_arguments,
)
from backend.bootstrap_authority.currentness_witness_handoff import _correlation_arguments
from backend.bootstrap_authority.journal_repository import JournalHead, JournalRepository
from backend.bootstrap_authority.lifecycle_verifier import digest


class AdmissionTransactionDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("ADMISSION_TRANSACTION_DENIED")


class _AdmissionCommitOutcome(Enum):
    COMMITTED = "COMMITTED"
    NOT_COMMITTED = "NOT_COMMITTED"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"


@dataclass(frozen=True, slots=True, repr=False)
class _ReconciliationIdentity:
    installation_ids: tuple[str, ...]
    journal_id: str
    attempt_id: str
    event_id: str
    event_revision: int
    event_digest: str
    expected_head_digest: str
    expected_head_revision: int
    expected_semantic_revision: int
    correlation_digest: str


@dataclass(frozen=True, slots=True, repr=False)
class _AdmissionCommitResult:
    """A report, not a receipt, credential, admission or retry capability."""

    outcome: _AdmissionCommitOutcome
    reconciliation: _ReconciliationIdentity


def _identity(record: _AttemptRecord) -> _ReconciliationIdentity:
    candidate = record.candidate
    return _ReconciliationIdentity(
        tuple(sorted({scope[0] for scope in candidate.affected_scopes})),
        candidate.journal_id,
        record.attempt_id,
        candidate.event_id,
        candidate.event_revision,
        candidate.event_digest,
        candidate.expected_head_digest,
        candidate.expected_head_revision,
        candidate.expected_semantic_revision,
        record.correlation_digest,
    )


class _AdmissionJournalTransactionOwner:
    """Internal one-shot owner of an attempt's exact journal transaction."""

    def __init__(self, *, attempts, journal_repository):
        if (
            type(attempts) is not _AdmissionAttemptProvider
            or type(journal_repository) is not JournalRepository
            or attempts._currentness._correlations._observations._journal is not journal_repository
            or not isinstance(journal_repository.session, Session)
        ):
            raise AdmissionTransactionDenied()
        self._attempts = attempts
        self._journal = journal_repository
        self._lock = RLock()

    @staticmethod
    def _require_transaction(record: _AttemptRecord) -> None:
        session = record.journal_session
        if (
            not isinstance(session, Session)
            or session.get_nested_transaction() is not None
            or session.get_transaction() is not record.journal_transaction
            or not record.journal_transaction.is_active
        ):
            raise AdmissionTransactionDenied()

    def _require_expected_head(self, record: _AttemptRecord) -> None:
        candidate = record.candidate
        expected = JournalHead(
            candidate.journal_id,
            candidate.expected_head_revision,
            candidate.expected_semantic_revision,
            candidate.expected_head_digest,
            record.currentness_record.binding.root_key_id,
            record.currentness_record.binding.journal.last_key_id,
        )
        self._journal.read_public_history()
        if self._journal.read_public_head() != expected:
            raise AdmissionTransactionDenied()

    def _require_final_guard(self, record: _AttemptRecord) -> None:
        """Revalidate private lifetimes plus the exact post-append journal state."""
        self._require_transaction(record)
        currentness = self._attempts._currentness
        witness = record.currentness_record
        correlation = witness.correlation_record
        if (
            self._attempts._records.get(record.handle) is not record
            or self._attempts._by_witness.get(record.currentness_witness) is not record.handle
            or currentness._records.get(record.currentness_witness) is not witness
            or witness.invalidated
            or currentness._correlations._records.get(witness.correlation_handle) is not correlation
            or record.journal_session is not self._journal.session
            or correlation.journal_transaction is not record.journal_transaction
            or _correlation_digest(witness) != record.correlation_digest
            or digest(record.candidate.canonical_event) != record.candidate.event_digest
        ):
            raise AdmissionTransactionDenied()

        currentness._lifetime._require_live_binding(
            attempt=witness.attempt,
            witness=witness.witness,
            lease=witness.lease,
            session=witness.session,
            freshly_verified_binding=witness.binding,
            exact_scope=witness.exact_scope,
        )
        currentness._serialization._require_live(
            witness.lease,
            session=witness.session,
            scopes=witness.binding.affected_scopes,
        )
        correlation_arguments = _correlation_arguments(correlation)
        currentness._correlations._authenticity._require_open(
            correlation.authenticity_handle,
            **_authenticity_arguments(correlation_arguments),
        )
        currentness._correlations._observations._lineage._require_current(
            correlation.lineage_handle,
            confirmation_handle=correlation.confirmation_handle,
            expected_payload=correlation.expected_payload,
            action=correlation.action,
            lineage=correlation.lineage,
        )
        payload = json.loads(record.candidate.canonical_event)["payload"]
        previous = record.currentness_record.binding.journal
        expected = JournalHead(
            record.candidate.journal_id,
            record.candidate.event_revision,
            record.candidate.semantic_revision,
            record.candidate.event_digest,
            payload["new_key_id"],
            payload["new_key_id"] or previous.last_key_id,
        )
        self._journal.read_public_history()
        if self._journal.read_public_head() != expected:
            raise AdmissionTransactionDenied()
        self._require_transaction(record)

    @staticmethod
    def _consume(record: _AttemptRecord, attempts: _AdmissionAttemptProvider) -> None:
        with suppress(Exception):
            attempts._invalidate(record)

    @staticmethod
    def _cleanup_failed_transaction(record: _AttemptRecord, *, commit_started: bool) -> None:
        if not commit_started:
            try:
                record.journal_session.rollback()
            except Exception:
                with suppress(Exception):
                    record.journal_session.close()
            return
        # A failed rollback or an ambiguous commit must not leak a reusable
        # transaction/connection. Closing cannot make the outcome authoritative.
        with suppress(Exception):
            record.journal_session.close()

    def commit(
        self,
        admission_attempt,
        *,
        currentness_witness,
        **currentness_arguments,
    ) -> _AdmissionCommitResult:
        record = None
        reconciliation = None
        commit_started = False
        with self._lock:
            try:
                record = self._attempts._require_prepared(
                    admission_attempt,
                    currentness_witness=currentness_witness,
                    **currentness_arguments,
                )
                reconciliation = _identity(record)
                if record.journal_session is not self._journal.session:
                    raise AdmissionTransactionDenied()
                self._require_transaction(record)
                self._require_expected_head(record)
                candidate = record.candidate
                self._journal.append_public_event(
                    candidate.canonical_event,
                    candidate.canonical_manifest,
                    expected=candidate.expected,
                )
                self._require_final_guard(record)
                commit_started = True
                record.journal_session.commit()
            except AdmissionAttemptDenied:
                raise AdmissionTransactionDenied() from None
            except Exception:
                if record is None or reconciliation is None:
                    raise AdmissionTransactionDenied() from None
                outcome = (
                    _AdmissionCommitOutcome.RECONCILIATION_REQUIRED
                    if commit_started
                    else _AdmissionCommitOutcome.NOT_COMMITTED
                )
                self._cleanup_failed_transaction(record, commit_started=commit_started)
                self._consume(record, self._attempts)
                return _AdmissionCommitResult(outcome, reconciliation)

            self._consume(record, self._attempts)
            return _AdmissionCommitResult(_AdmissionCommitOutcome.COMMITTED, reconciliation)


__all__ = ["AdmissionTransactionDenied"]
