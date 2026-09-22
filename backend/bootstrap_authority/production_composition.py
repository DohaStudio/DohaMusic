"""Strict ceremony-scoped composition gate for durable admission.

This module does not discover, provision, or replace production dependencies.
The application composition remains unavailable until reviewed source,
authentication, and deployment configuration adapters are supplied.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum
from threading import RLock

from sqlalchemy.exc import UnboundExecutionError
from sqlalchemy.orm import Session, SessionTransaction

from backend.bootstrap_authority.admission_attempt import _AdmissionAttemptProvider
from backend.bootstrap_authority.admission_reconciliation import _AdmissionCommitReconciler
from backend.bootstrap_authority.admission_transaction import _AdmissionJournalTransactionOwner
from backend.bootstrap_authority.confirmation_authenticity import (
    _OriginalConfirmationAuthenticity,
)
from backend.bootstrap_authority.confirmation_lineage_correlation import (
    _ConfirmationLineageCorrelations,
)
from backend.bootstrap_authority.confirmation_snapshot import _OriginalConfirmationSnapshots
from backend.bootstrap_authority.currentness_witness_handoff import _CurrentnessWitnessHandoff
from backend.bootstrap_authority.designation_snapshot import _DesignationRecordSnapshots
from backend.bootstrap_authority.durable_admission import _DurableAdmissionOrchestrator
from backend.bootstrap_authority.fresh_journal_lineage import _FreshJournalLineageObservations
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.bootstrap_authority.live_lineage_reader import _LivePolicyLineageSnapshots
from backend.bootstrap_authority.private_pin_reader import _PrivatePinFactsReader
from backend.bootstrap_authority.provisioning_authority_source import (
    _ProvisioningAuthoritySourceSnapshots,
)
from backend.bootstrap_authority.provisioning_verifier_material import (
    _ProvisioningVerifierMaterialSnapshots,
)
from backend.bootstrap_authority.windows_serialization import _WindowsCeremonySerialization
from backend.bootstrap_authority.witness_lifetime import _ProviderWitnessLifetime


class ProductionAdmissionCompositionDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PRODUCTION_ADMISSION_COMPOSITION_DENIED")


class ProductionAdmissionUnavailable(RuntimeError):
    def __init__(self) -> None:
        super().__init__("PRODUCTION_ADMISSION_UNAVAILABLE")


class ProductionAdmissionReadiness(Enum):
    COMPOSITION_ROOT_READY = "COMPOSITION_ROOT_READY"
    PRODUCTION_ACTIVATION_UNAVAILABLE = "PRODUCTION_ACTIVATION_UNAVAILABLE"


class UnavailableProductionAdmissionComposition:
    """Production default: missing reviewed dependencies never select a fallback."""

    readiness = ProductionAdmissionReadiness.PRODUCTION_ACTIVATION_UNAVAILABLE

    def activate(self, **_dependencies):
        raise ProductionAdmissionUnavailable()


@dataclass(slots=True, repr=False)
class _ProductionAdmissionScope:
    _root: object
    _token: object
    _orchestrator: _DurableAdmissionOrchestrator
    _caller_session: Session
    _caller_transaction: SessionTransaction
    _journal_session: Session
    _journal_transaction: SessionTransaction

    def admit(self, **arguments):
        self._root._require_active(self)
        return self._orchestrator.admit(**arguments)


@dataclass(frozen=True, slots=True, repr=False)
class _Graph:
    orchestrator: _DurableAdmissionOrchestrator
    attempts: _AdmissionAttemptProvider
    owner: _AdmissionJournalTransactionOwner
    reconciler: _AdmissionCommitReconciler
    handoff: _CurrentnessWitnessHandoff
    correlations: _ConfirmationLineageCorrelations
    observations: _FreshJournalLineageObservations
    authenticity: _OriginalConfirmationAuthenticity
    lineage: _LivePolicyLineageSnapshots
    confirmation: _OriginalConfirmationSnapshots
    material: _ProvisioningVerifierMaterialSnapshots
    authority: _ProvisioningAuthoritySourceSnapshots
    designation: _DesignationRecordSnapshots
    pin: _PrivatePinFactsReader
    serialization: _WindowsCeremonySerialization
    lifetime: _ProviderWitnessLifetime
    journal: JournalRepository


def _exact_graph(orchestrator) -> _Graph:
    if type(orchestrator) is not _DurableAdmissionOrchestrator:
        raise ProductionAdmissionCompositionDenied()
    attempts, owner, reconciler = (
        orchestrator._attempts,
        orchestrator._owner,
        orchestrator._reconciler,
    )
    if (
        type(attempts) is not _AdmissionAttemptProvider
        or type(owner) is not _AdmissionJournalTransactionOwner
        or type(reconciler) is not _AdmissionCommitReconciler
        or owner._attempts is not attempts
        or reconciler._owner is not owner
    ):
        raise ProductionAdmissionCompositionDenied()
    handoff = attempts._currentness
    if type(handoff) is not _CurrentnessWitnessHandoff:
        raise ProductionAdmissionCompositionDenied()
    correlations, lifetime = handoff._correlations, handoff._lifetime
    if (
        type(correlations) is not _ConfirmationLineageCorrelations
        or type(lifetime) is not _ProviderWitnessLifetime
    ):
        raise ProductionAdmissionCompositionDenied()
    authenticity, observations = correlations._authenticity, correlations._observations
    if (
        type(authenticity) is not _OriginalConfirmationAuthenticity
        or type(observations) is not _FreshJournalLineageObservations
    ):
        raise ProductionAdmissionCompositionDenied()
    confirmation, material, lineage, journal = (
        authenticity._confirmation,
        authenticity._material,
        observations._lineage,
        observations._journal,
    )
    if (
        type(confirmation) is not _OriginalConfirmationSnapshots
        or type(material) is not _ProvisioningVerifierMaterialSnapshots
        or type(lineage) is not _LivePolicyLineageSnapshots
        or type(journal) is not JournalRepository
        or lineage._confirmation is not confirmation
        or owner._journal is not journal
    ):
        raise ProductionAdmissionCompositionDenied()
    authority, designation = material._authority, confirmation._designation
    if (
        type(authority) is not _ProvisioningAuthoritySourceSnapshots
        or type(designation) is not _DesignationRecordSnapshots
        or authority._designation is not designation
        or confirmation._designation is not designation
    ):
        raise ProductionAdmissionCompositionDenied()
    pin, serialization = designation._pin, designation._serialization
    if (
        type(pin) is not _PrivatePinFactsReader
        or type(serialization) is not _WindowsCeremonySerialization
        or pin._serialization is not serialization
        or confirmation._serialization is not serialization
        or handoff._serialization is not serialization
        or serialization._lifetime is not lifetime
        or reconciler._engine is not journal.session.get_bind()
    ):
        raise ProductionAdmissionCompositionDenied()
    return _Graph(
        orchestrator,
        attempts,
        owner,
        reconciler,
        handoff,
        correlations,
        observations,
        authenticity,
        lineage,
        confirmation,
        material,
        authority,
        designation,
        pin,
        serialization,
        lifetime,
        journal,
    )


def _require_root_transaction(session, transaction) -> None:
    if (
        not isinstance(session, Session)
        or not isinstance(transaction, SessionTransaction)
        or session.get_transaction() is not transaction
        or session.get_nested_transaction() is not None
        or not session.is_active
        or not transaction.is_active
    ):
        raise ProductionAdmissionCompositionDenied()


class _ProductionAdmissionCompositionRoot:
    """Application-owned gate over one complete, caller-owned ceremony graph.

    The caller owns both root transactions and the surrounding source/Windows
    lease context. This gate owns only activation state. The caller remains
    responsible for orderly witness, lease, source-handle and transaction cleanup;
    the gate never short-circuits those nested provider context managers.
    """

    readiness = ProductionAdmissionReadiness.COMPOSITION_ROOT_READY

    def __init__(self) -> None:
        self._lock = RLock()
        self._active: dict[object, _ProductionAdmissionScope] = {}
        self._used: dict[int, object] = {}
        self._closed = False

    def _validate(self, *, orchestrator, caller_session, caller_transaction) -> _Graph:
        try:
            graph = _exact_graph(orchestrator)
        except ProductionAdmissionCompositionDenied:
            raise
        except (AttributeError, TypeError) as error:
            raise ProductionAdmissionCompositionDenied() from error
        journal_session = graph.journal.session
        journal_transaction = journal_session.get_transaction()
        _require_root_transaction(caller_session, caller_transaction)
        _require_root_transaction(journal_session, journal_transaction)
        try:
            caller_bind = caller_session.get_bind()
        except UnboundExecutionError:
            caller_bind = None
        if (
            caller_session is journal_session
            or (caller_bind is not None and caller_bind is journal_session.get_bind())
            or graph.lifetime._closed
            or len(graph.lifetime._attempts) != 1
            or len(graph.serialization._leases) != 1
            or len(graph.correlations._records) != 1
            or len(graph.observations._observations) != 1
            or len(graph.authenticity._records) != 1
            or graph.attempts._records
            or graph.owner._reconciliations
            or graph.reconciler._results
        ):
            raise ProductionAdmissionCompositionDenied()
        lifetime_record = next(iter(graph.lifetime._attempts.values()))
        lease_record = next(iter(graph.serialization._leases.values()))
        if (
            lifetime_record.session is not caller_session
            or lifetime_record.transaction is not caller_transaction
            or lease_record.session is not caller_session
            or lease_record.transaction is not caller_transaction
        ):
            raise ProductionAdmissionCompositionDenied()
        return graph

    @contextmanager
    def open_scope(self, *, orchestrator, caller_session, caller_transaction):
        graph = None
        owned = False
        token = object()
        try:
            graph = self._validate(
                orchestrator=orchestrator,
                caller_session=caller_session,
                caller_transaction=caller_transaction,
            )
            journal_session = graph.journal.session
            scope = _ProductionAdmissionScope(
                self,
                token,
                graph.orchestrator,
                caller_session,
                caller_transaction,
                journal_session,
                journal_session.get_transaction(),
            )
            with self._lock:
                identity = id(orchestrator)
                if self._closed or identity in self._used or orchestrator in self._active:
                    raise ProductionAdmissionCompositionDenied()
                self._active[orchestrator] = scope
                self._used[identity] = orchestrator
                owned = True
            yield scope
        except Exception:
            raise
        finally:
            if owned:
                with self._lock:
                    self._active.pop(graph.orchestrator, None)

    def _require_active(self, scope) -> None:
        if type(scope) is not _ProductionAdmissionScope:
            raise ProductionAdmissionCompositionDenied()
        with self._lock:
            if self._closed or self._active.get(scope._orchestrator) is not scope:
                raise ProductionAdmissionCompositionDenied()
        _require_root_transaction(scope._caller_session, scope._caller_transaction)
        _require_root_transaction(scope._journal_session, scope._journal_transaction)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._active.clear()
