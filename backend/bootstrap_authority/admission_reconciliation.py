"""Read-only authoritative reconciliation of an ambiguous journal commit.

This foundation consumes only an opaque handoff minted by the exact transaction
owner.  It opens two independent read snapshots, verifies complete journal v1
history through JournalRepository, and never appends, retries or repairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.bootstrap_authority.admission_transaction import (
    _AdmissionCommitOutcome,
    _AdmissionJournalTransactionOwner,
    _identity,
    _ReconciliationHandoff,
    _ReconciliationIdentity,
    _ReconciliationRecord,
)
from backend.bootstrap_authority.journal_repository import (
    JournalEvent,
    JournalHead,
    JournalRepository,
)


class AdmissionReconciliationDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("ADMISSION_RECONCILIATION_DENIED")


class _ReconciliationOutcome(Enum):
    COMMITTED_EXACT = "COMMITTED_EXACT"
    NOT_COMMITTED = "NOT_COMMITTED"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True, repr=False)
class _JournalSnapshot:
    head: JournalHead
    events: tuple[JournalEvent, ...]


@dataclass(frozen=True, slots=True, repr=False)
class _ReconciliationResult:
    """Internal audit report; authority remains the verified journal facts."""

    outcome: _ReconciliationOutcome
    identity: _ReconciliationIdentity


class _AdmissionCommitReconciler:
    """Exact-handoff reader over the owner's independently bound journal."""

    def __init__(self, *, transaction_owner, journal_engine):
        if (
            type(transaction_owner) is not _AdmissionJournalTransactionOwner
            or not isinstance(journal_engine, Engine)
            or transaction_owner._journal.session.get_bind() is not journal_engine
        ):
            raise AdmissionReconciliationDenied()
        self._owner = transaction_owner
        self._engine = journal_engine

    def _require_handoff(self, handoff) -> _ReconciliationRecord:
        if type(handoff) is not _ReconciliationHandoff:
            raise AdmissionReconciliationDenied()
        record = self._owner._reconciliations.get(id(handoff))
        if (
            type(record) is not _ReconciliationRecord
            or record.handoff is not handoff
            or record.outcome is not _AdmissionCommitOutcome.RECONCILIATION_REQUIRED
            or _identity(record.attempt) != record.identity
        ):
            raise AdmissionReconciliationDenied()
        return record

    def _read_snapshot(self) -> _JournalSnapshot:
        with Session(self._engine, autoflush=False, expire_on_commit=False) as session:
            repository = JournalRepository(session)
            head = repository.read_public_head()
            events = repository.read_verified_events()
            if repository.read_public_head() != head:
                raise RuntimeError("MOVING_JOURNAL")
            return _JournalSnapshot(head, events)

    @staticmethod
    def _classify(record: _ReconciliationRecord, snapshot: _JournalSnapshot):
        identity = record.identity
        candidate = record.attempt.candidate
        if snapshot.head.journal_id != identity.journal_id:
            return _ReconciliationOutcome.CONFLICT

        exact = []
        partial = []
        for event in snapshot.events:
            matches = (
                event.event_id == identity.event_id,
                event.revision == identity.event_revision,
                event.event_digest == identity.event_digest,
            )
            if all(matches):
                exact.append(event)
            elif any(matches):
                partial.append(event)
        if len(exact) == 1:
            event = exact[0]
            if (
                event.journal_id == identity.journal_id
                and event.previous_digest == identity.expected_head_digest
                and event.envelope == candidate.canonical_event
            ):
                return _ReconciliationOutcome.COMMITTED_EXACT
            return _ReconciliationOutcome.CONFLICT
        if exact or partial:
            return _ReconciliationOutcome.CONFLICT

        head = snapshot.head
        if (
            head.revision == identity.expected_head_revision
            and head.trust_revision == identity.expected_semantic_revision
            and head.head_digest == identity.expected_head_digest
            and identity.event_revision == head.revision + 1
        ):
            return _ReconciliationOutcome.NOT_COMMITTED
        return _ReconciliationOutcome.CONFLICT

    def reconcile(self, handoff) -> _ReconciliationResult:
        record = self._require_handoff(handoff)
        try:
            first = self._read_snapshot()
            second = self._read_snapshot()
        except Exception:
            return _ReconciliationResult(_ReconciliationOutcome.UNAVAILABLE, record.identity)
        if first != second:
            return _ReconciliationResult(_ReconciliationOutcome.UNAVAILABLE, record.identity)
        return _ReconciliationResult(self._classify(record, second), record.identity)


__all__ = ["AdmissionReconciliationDenied"]
