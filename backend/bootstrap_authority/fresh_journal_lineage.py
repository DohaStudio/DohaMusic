"""Fresh public-journal/held-lineage observation, never currentness authority.

This is a narrow prerequisite for a future reviewed currentness adapter.  It
correlates a complete public journal read with the already-held private source
chain while both caller-owned transactions remain active.  Public journal
integrity, pin equality and an opaque observation are still NOT authenticated
provisioning, a CurrentnessWitness, admission or authorization.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session, SessionTransaction

from backend.bootstrap_authority.journal_repository import (
    JournalHead,
    JournalRepository,
    PublicKeyHistory,
)
from backend.bootstrap_authority.live_lineage_reader import _LivePolicyLineageSnapshots
from backend.bootstrap_authority.witness_lifetime import _MINT, _Handle


class FreshJournalLineageDenied(RuntimeError):
    def __init__(self) -> None:
        super().__init__("DEPLOYMENT_FRESH_JOURNAL_LINEAGE_DENIED")


@dataclass(frozen=True, slots=True)
class _JournalSnapshot:
    head: JournalHead
    history: tuple[PublicKeyHistory, ...]


@dataclass(slots=True, repr=False)
class _Observation:
    lineage_handle: _Handle
    confirmation_handle: _Handle
    journal_session: Session
    journal_transaction: SessionTransaction
    snapshot: _JournalSnapshot


class _FreshJournalLineageObservations:
    """Provider-internal correlation only; no production port or witness mint."""

    def __init__(self, *, lineage_snapshots, journal_repository):
        if (
            type(lineage_snapshots) is not _LivePolicyLineageSnapshots
            or type(journal_repository) is not JournalRepository
            or not isinstance(journal_repository.session, Session)
        ):
            raise FreshJournalLineageDenied()
        self._lineage = lineage_snapshots
        self._journal = journal_repository
        self._observations: dict[_Handle, _Observation] = {}

    @staticmethod
    def _root_transaction(session: Session) -> SessionTransaction:
        if not isinstance(session, Session) or session.get_nested_transaction() is not None:
            raise FreshJournalLineageDenied()
        transaction = session.get_transaction()
        if transaction is None or not transaction.is_active:
            raise FreshJournalLineageDenied()
        return transaction

    def _deny_chain(self, *, observation_handle=None, lineage_handle, confirmation_handle):
        if observation_handle is not None:
            self._observations.pop(observation_handle, None)
        self._lineage._abandon_chain(
            lineage_handle=lineage_handle,
            confirmation_handle=confirmation_handle,
        )
        raise FreshJournalLineageDenied() from None

    @staticmethod
    def _require_active_projection(snapshot, binding) -> None:
        if (
            type(snapshot) is not _JournalSnapshot
            or type(snapshot.head) is not JournalHead
            or type(snapshot.history) is not tuple
        ):
            raise FreshJournalLineageDenied()
        binding.__post_init__()
        if snapshot.head != binding.journal or snapshot.head != binding.installed_pin:
            raise FreshJournalLineageDenied()
        if any(type(item) is not PublicKeyHistory for item in snapshot.history):
            raise FreshJournalLineageDenied()
        active = tuple(item for item in snapshot.history if item.status == "ACTIVE_ISSUANCE")
        if (
            len(active) != 1
            or type(active[0]) is not PublicKeyHistory
            or active[0].key_id != binding.root_key_id
            or active[0].fingerprint != binding.root_fingerprint
            or active[0].tainted is not False
            or active[0].invalidated_at_revision is not None
        ):
            raise FreshJournalLineageDenied()

    def _read_snapshot(self, binding) -> _JournalSnapshot:
        try:
            history = self._journal.read_public_history()
            head = self._journal.read_public_head()
            snapshot = _JournalSnapshot(head, history)
            self._require_active_projection(snapshot, binding)
            # Re-read after the complete history traversal; a moving head is denial.
            if self._journal.read_public_head() != head:
                raise FreshJournalLineageDenied()
            return snapshot
        except Exception:
            raise FreshJournalLineageDenied() from None

    def _require_source(
        self, *, lineage_handle, confirmation_handle, expected_payload, action, lineage
    ):
        self._lineage._require_current(
            lineage_handle,
            confirmation_handle=confirmation_handle,
            expected_payload=expected_payload,
            action=action,
            lineage=lineage,
        )
        parent = self._lineage._confirmation._records[confirmation_handle]
        # The public journal store must not share the caller/private-source Session.
        if self._journal.session is parent.session:
            raise FreshJournalLineageDenied()
        return parent.pin_facts.binding

    @contextmanager
    def _open_observation(
        self, *, lineage_handle, confirmation_handle, expected_payload, action, lineage
    ):
        handle = None
        try:
            journal_transaction = self._root_transaction(self._journal.session)
            binding = self._require_source(
                lineage_handle=lineage_handle,
                confirmation_handle=confirmation_handle,
                expected_payload=expected_payload,
                action=action,
                lineage=lineage,
            )
            snapshot = self._read_snapshot(binding)
            binding = self._require_source(
                lineage_handle=lineage_handle,
                confirmation_handle=confirmation_handle,
                expected_payload=expected_payload,
                action=action,
                lineage=lineage,
            )
            if self._root_transaction(self._journal.session) is not journal_transaction:
                raise FreshJournalLineageDenied()
            if self._read_snapshot(binding) != snapshot:
                raise FreshJournalLineageDenied()
            handle = _Handle(_MINT)
            self._observations[handle] = _Observation(
                lineage_handle,
                confirmation_handle,
                self._journal.session,
                journal_transaction,
                snapshot,
            )
            try:
                yield handle
            finally:
                self._observations.pop(handle, None)
        except Exception:
            self._deny_chain(
                observation_handle=handle,
                lineage_handle=lineage_handle,
                confirmation_handle=confirmation_handle,
            )

    def _require_fresh(
        self,
        handle,
        *,
        lineage_handle,
        confirmation_handle,
        expected_payload,
        action,
        lineage,
    ) -> None:
        if type(handle) is not _Handle or handle not in self._observations:
            raise FreshJournalLineageDenied()
        record = self._observations[handle]
        try:
            if (
                record.lineage_handle is not lineage_handle
                or record.confirmation_handle is not confirmation_handle
                or record.journal_session is not self._journal.session
                or self._root_transaction(record.journal_session) is not record.journal_transaction
            ):
                raise FreshJournalLineageDenied()
            binding = self._require_source(
                lineage_handle=lineage_handle,
                confirmation_handle=confirmation_handle,
                expected_payload=expected_payload,
                action=action,
                lineage=lineage,
            )
            if self._read_snapshot(binding) != record.snapshot:
                raise FreshJournalLineageDenied()
            self._require_source(
                lineage_handle=lineage_handle,
                confirmation_handle=confirmation_handle,
                expected_payload=expected_payload,
                action=action,
                lineage=lineage,
            )
        except Exception:
            self._deny_chain(
                observation_handle=handle,
                lineage_handle=lineage_handle,
                confirmation_handle=confirmation_handle,
            )
