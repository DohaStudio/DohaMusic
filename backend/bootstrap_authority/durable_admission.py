"""Durable Admission orchestration over existing authority components.

The orchestrator creates no authority of its own.  It prepares one exact
AdmissionAttempt, delegates the only write/commit to its Transaction Owner,
and delegates every ambiguous outcome to the read-only Commit Reconciler.
Only a known commit or an exact reconciled commit is reported as success.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.bootstrap_authority.admission_attempt import (
    AdmissionAttemptDenied,
    _AdmissionAttemptProvider,
)
from backend.bootstrap_authority.admission_reconciliation import (
    AdmissionReconciliationDenied,
    _AdmissionCommitReconciler,
    _ReconciliationOutcome,
)
from backend.bootstrap_authority.admission_transaction import (
    AdmissionTransactionDenied,
    _AdmissionCommitOutcome,
    _AdmissionJournalTransactionOwner,
    _ReconciliationHandoff,
    _ReconciliationIdentity,
)


class DurableAdmissionDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DURABLE_ADMISSION_DENIED")


class _DurableAdmissionOutcome(Enum):
    COMMITTED_EXACT = "COMMITTED_EXACT"
    NOT_COMMITTED = "NOT_COMMITTED"
    CONFLICT = "CONFLICT"
    UNAVAILABLE = "UNAVAILABLE"


class _DurableAdmissionProvenance(Enum):
    DIRECT_COMMIT = "DIRECT_COMMIT"
    RECONCILED_COMMIT = "RECONCILED_COMMIT"
    DIRECT_NOT_COMMITTED = "DIRECT_NOT_COMMITTED"
    RECONCILED_NOT_COMMITTED = "RECONCILED_NOT_COMMITTED"
    RECONCILIATION_CONFLICT = "RECONCILIATION_CONFLICT"
    RECONCILIATION_UNAVAILABLE = "RECONCILIATION_UNAVAILABLE"


@dataclass(frozen=True, slots=True, repr=False)
class _DurableAdmissionResult:
    """Internal report; the verified external journal remains authority."""

    outcome: _DurableAdmissionOutcome
    provenance: _DurableAdmissionProvenance
    identity: _ReconciliationIdentity
    reconciliation: _ReconciliationHandoff | None


class _DurableAdmissionOrchestrator:
    """One-way coordinator for the exact Provider/Owner/Reconciler chain."""

    def __init__(self, *, attempts, transaction_owner, reconciler):
        if (
            type(attempts) is not _AdmissionAttemptProvider
            or type(transaction_owner) is not _AdmissionJournalTransactionOwner
            or type(reconciler) is not _AdmissionCommitReconciler
            or transaction_owner._attempts is not attempts
            or reconciler._owner is not transaction_owner
        ):
            raise DurableAdmissionDenied()
        self._attempts = attempts
        self._owner = transaction_owner
        self._reconciler = reconciler

    @staticmethod
    def _result(outcome, provenance, identity, reconciliation=None):
        if (
            type(outcome) is not _DurableAdmissionOutcome
            or type(provenance) is not _DurableAdmissionProvenance
            or type(identity) is not _ReconciliationIdentity
            or (reconciliation is not None and type(reconciliation) is not _ReconciliationHandoff)
        ):
            raise DurableAdmissionDenied()
        return _DurableAdmissionResult(outcome, provenance, identity, reconciliation)

    def reconcile(self, handoff) -> _DurableAdmissionResult:
        """Replay only the existing read-only reconciliation authority."""
        try:
            result = self._reconciler.reconcile(handoff)
            result = self._reconciler._consume_result(result, handoff=handoff)
        except AdmissionReconciliationDenied:
            raise DurableAdmissionDenied() from None
        outcomes = {
            _ReconciliationOutcome.COMMITTED_EXACT: (
                _DurableAdmissionOutcome.COMMITTED_EXACT,
                _DurableAdmissionProvenance.RECONCILED_COMMIT,
            ),
            _ReconciliationOutcome.NOT_COMMITTED: (
                _DurableAdmissionOutcome.NOT_COMMITTED,
                _DurableAdmissionProvenance.RECONCILED_NOT_COMMITTED,
            ),
            _ReconciliationOutcome.CONFLICT: (
                _DurableAdmissionOutcome.CONFLICT,
                _DurableAdmissionProvenance.RECONCILIATION_CONFLICT,
            ),
            _ReconciliationOutcome.UNAVAILABLE: (
                _DurableAdmissionOutcome.UNAVAILABLE,
                _DurableAdmissionProvenance.RECONCILIATION_UNAVAILABLE,
            ),
        }
        try:
            outcome, provenance = outcomes[result.outcome]
        except (KeyError, TypeError):
            raise DurableAdmissionDenied() from None
        return self._result(outcome, provenance, result.identity, handoff)

    def admit(
        self,
        *,
        currentness_witness,
        artifact,
        manifest,
        expected,
        **currentness_arguments,
    ) -> _DurableAdmissionResult:
        try:
            with self._attempts._open_attempt(
                currentness_witness=currentness_witness,
                artifact=artifact,
                manifest=manifest,
                expected=expected,
                **currentness_arguments,
            ) as attempt:
                commit_result = self._owner.commit(
                    attempt,
                    currentness_witness=currentness_witness,
                    **currentness_arguments,
                )
            record = self._owner._require_result(
                commit_result,
                admission_attempt=attempt,
            )
        except (AdmissionAttemptDenied, AdmissionTransactionDenied):
            raise DurableAdmissionDenied() from None

        if record.outcome is _AdmissionCommitOutcome.COMMITTED:
            self._owner._release_known_result(
                commit_result,
                admission_attempt=attempt,
            )
            return self._result(
                _DurableAdmissionOutcome.COMMITTED_EXACT,
                _DurableAdmissionProvenance.DIRECT_COMMIT,
                record.identity,
            )
        if record.outcome is _AdmissionCommitOutcome.NOT_COMMITTED:
            self._owner._release_known_result(
                commit_result,
                admission_attempt=attempt,
            )
            return self._result(
                _DurableAdmissionOutcome.NOT_COMMITTED,
                _DurableAdmissionProvenance.DIRECT_NOT_COMMITTED,
                record.identity,
            )
        if record.outcome is _AdmissionCommitOutcome.RECONCILIATION_REQUIRED:
            return self.reconcile(record.handoff)
        raise DurableAdmissionDenied()


__all__ = ["DurableAdmissionDenied"]
