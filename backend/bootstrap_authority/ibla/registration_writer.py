"""ADR-111 exact direct consumer, never an IA issuer or production factory."""

import os
import time
from dataclasses import asdict, dataclass
from threading import get_native_id

from backend.bootstrap_authority.ibla.codec import control_wire, parse_control
from backend.bootstrap_authority.ibla.contracts import Head, IblaConflict, IblaDenied
from backend.bootstrap_authority.ibla.registration_codec import head, parse_event
from backend.bootstrap_authority.ibla.registration_owners import _Owners
from backend.bootstrap_authority.ibla.registration_source import (
    _HeldRegistration,
    _RegistrationOriginals,
)
from backend.bootstrap_authority.ibla.repository import LedgerRepository
from backend.bootstrap_authority.ibla.source_codec import POSSESSION_DOMAIN
from backend.bootstrap_authority.lifecycle_verifier import _read


@dataclass(frozen=True, slots=True, repr=False)
class _RegistrationResult:
    operation_id: str
    fingerprint: str
    envelope: bytes
    target: Head
    post: bool
    current_h_head: Head
    current_h_state: str

    def __repr__(self):
        return "<IBLA registration audit result>"


def _result(lv, hv, operation_id, fingerprint):
    candidates = [e for e in lv.events if e.operation_id == operation_id]
    pending = parse_event(hv.pending, lv.binding) if hv.pending is not None else None
    event = candidates[0] if candidates else pending
    if event is None or event.operation_id != operation_id:
        raise IblaDenied()
    if event.fingerprint != fingerprint:
        raise IblaConflict()
    if event.kind != "REGISTRATION_COMMITTED":
        raise IblaDenied()
    if candidates and pending is not None and pending.envelope != event.envelope:
        raise IblaConflict()
    return _RegistrationResult(
        operation_id,
        fingerprint,
        event.envelope,
        Head(event.revision, event.digest),
        bool(candidates),
        hv.head,
        hv.state,
    )


class UnavailableIblaRegistrationWriter:
    def register(self, *args, **kwargs):
        raise IblaDenied()


class _RegistrationCommitWriter:
    def __init__(self, originals):
        if type(originals) is not _RegistrationOriginals:
            raise IblaDenied()
        self._originals, self._provider = originals, None

    def __repr__(self):
        return "<IBLA registration commit writer>"

    def _preflight(self, provider, record):
        if provider._consumer is not self or (
            self._provider is not None and self._provider is not provider
        ):
            raise IblaDenied()
        self._provider = provider
        if record.writer is not None or record.delivered:
            raise IblaConflict()
        authority = _HeldRegistration(self._originals, record.source)
        r = authority.intent
        snapshot = record.source.tuple
        if (
            r["binding"] != asdict(snapshot[0])
            or head(r["expected_l_head"]) != snapshot[1]
            or head(r["expected_h_head"]) != snapshot[2].head
            or head(r["expected_h_confirmed"]) != snapshot[2].confirmed
        ):
            raise IblaConflict()
        message = _read(record.message[len(POSSESSION_DOMAIN) :], 16384, 6)
        event = parse_event(authority.event(message["observation_id"]), record.source.binding)
        wire = control_wire(
            record.source.binding,
            sequence=snapshot[2].head.revision + 1,
            previous=snapshot[2].head.digest,
            kind="PREPARED",
            confirmed=snapshot[1],
            pending=event.envelope,
            recorded_at=r["recorded_at"],
            version=2,
        )
        parse_control(wire, record.source.binding, version=2)
        record.writer, record.authority, record.event = self, authority, event

    def _frame(self, record, *, preparing=False):
        provider = self._provider
        if (
            provider is None
            or provider._consumer is not self
            or record.writer is not self
            or provider._lookup(record.capability, "capability") is not record
            or not record.proof_used
            or record.verified is None
            or provider._lookup(record.verified, "verified") is not record
            or (
                (not record.preparing or record.delivered or record.delivering)
                if preparing
                else (not record.delivered or not record.delivering)
            )
            or record.writer_deadline is None
            or time.monotonic() >= record.writer_deadline
        ):
            raise IblaDenied()
        return provider

    def _live(self, record, session=None, *, preparing=False):
        provider = self._frame(record, preparing=preparing)
        provider._live(record, read=False)
        record.authority.validate()
        if session is not None and (
            record.writer_transaction is not session.get_transaction()
            or not record.writer_transaction.is_active
            or session.in_nested_transaction()
            or not session.connection().connection.driver_connection.in_transaction
        ):
            raise IblaDenied()

    def _preparing(self, record, session=None):
        if session is None:
            self._live(record, preparing=True)
        else:
            # H owns an independent L read here. Full source checks run before
            # opening that pass and again after it ends, immediately before commit.
            provider = self._frame(record, preparing=True)
            if (
                record.owner != (os.getpid(), get_native_id())
                or record.invalid
                or provider._shutdown
            ):
                raise IblaDenied()
        if record.writer_prepared is not None:
            raise IblaConflict()
        if session is not None and (
            record.writer_h_transaction is not session.get_transaction()
            or not record.writer_h_transaction.is_active
            or session.in_nested_transaction()
            or not session.connection().connection.driver_connection.in_transaction
        ):
            raise IblaDenied()

    def _prepare(self, record):
        self._preparing(record)
        owner = _Owners(
            record.source, record.source.binding, record.authority.intent["recorded_at"]
        )
        owner.checkpoint(
            "prepare",
            record.event.envelope,
            expected=head(record.authority.intent["expected_h_head"]),
            check=lambda: self._preparing(record),
            registration=(self, record),
        )
        # Only the successful original synchronous frame may reach final delivery.
        # An exception/lost response above cannot set this marker or be resumed.
        self._preparing(record)
        lv, hv = owner.read()
        self._require_pending(record, lv, hv)
        record.writer_prepared = hv.head

    def _require_pending(self, record, lv, hv):
        r, event = record.authority.intent, record.event
        if (
            lv.head != head(r["expected_l_head"])
            or len(lv.events) != 1
            or lv.events[0].kind != "COMMISSION"
            or hv.state != "PREPARED"
            or hv.pending != event.envelope
            or hv.confirmed != head(r["expected_h_confirmed"])
            or hv.head.revision != head(r["expected_h_head"]).revision + 1
            or (record.writer_prepared is not None and hv.head != record.writer_prepared)
        ):
            raise IblaConflict()
        # Full canonical history has already checked the predecessor and fingerprint.
        if parse_event(hv.pending, lv.binding).fingerprint != event.fingerprint:
            raise IblaConflict()

    def _reverify(self, record, *, preparing=True):
        self._live(record, preparing=preparing)
        if record.writer_prepared is None:
            raise IblaDenied()
        owner = _Owners(
            record.source, record.source.binding, record.authority.intent["recorded_at"]
        )
        lv, hv = owner.read()
        self._require_pending(record, lv, hv)
        self._live(record, preparing=preparing)

    def _append(self, record, session):
        self._live(record, session)
        repo = LedgerRepository(session, record.source.binding, version=2)
        lv = repo.read()
        event, expected = record.event, head(record.authority.intent["expected_l_head"])
        if (
            lv.head != expected
            or len(lv.events) != 1
            or lv.events[0].kind != "COMMISSION"
            or any(e.operation_id == event.operation_id for e in lv.events)
        ):
            raise IblaConflict()
        # Private flush/CAS path is tied to this registry frame and actual root transaction.
        self._live(record, session)
        repo._insert(
            (
                event.revision,
                event.event_id,
                event.operation_id,
                event.fingerprint,
                event.previous_digest,
                event.digest,
                event.kind,
                event.envelope,
            )
        )
        self._live(record, session)

    def __call__(self, capability):
        try:
            provider = self._provider
            if provider is None:
                raise IblaDenied()
            record = provider._lookup(capability, "capability")
            self._live(record)
            if record.writer_started:
                raise IblaConflict()
            record.writer_started = True
            event, r = record.event, record.authority.intent
            owner = _Owners(record.source, record.source.binding, r["recorded_at"])
            self._reverify(record, preparing=False)
            try:
                with owner._write(0) as session:
                    record.writer_transaction = session.get_transaction()
                    self._append(record, session)
                    self._live(record, session)
            finally:
                # Ended/ambiguous L transaction can NEVER acquire another write permission.
                record.writer_transaction = None
            # Only the keeper reads ACTUAL committed L and moves H forward.
            owner.checkpoint("confirm", event.operation_id, event.fingerprint)
            lv, hv = owner.read()
            result = _result(lv, hv, event.operation_id, event.fingerprint)
            if not result.post or hv.state != "CONFIRMED" or hv.confirmed != lv.head:
                raise IblaDenied()
            return result
        except IblaDenied:
            raise
        except Exception:
            raise IblaDenied() from None
