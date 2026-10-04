"""Independent H control history; confirmation reads L, never a caller head DTO."""

import os
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from backend.bootstrap_authority.contracts import require_digest, require_uuid
from backend.bootstrap_authority.ibla.codec import (
    control_wire,
    parse_control,
    parse_event,
    require_audit_time,
)
from backend.bootstrap_authority.ibla.contracts import (
    CheckpointView,
    Head,
    IblaConflict,
    IblaDenied,
    IblaInconsistent,
)
from backend.bootstrap_authority.ibla.repository import (
    LedgerRepository,
    _Repository,
    database_path,
    guarded,
)


@dataclass(frozen=True, slots=True)
class OperationResult:
    """Historical public result; not a capability or current eligibility proof."""

    operation_id: str
    fingerprint: str
    target: Head
    state: str


class CheckpointRepository(_Repository):
    role = "H"

    def __init__(self, session, binding, *, ledger_reader, recorded_at, version=1):
        super().__init__(session, binding, version=version)
        if type(ledger_reader) is not LedgerRepository or ledger_reader.binding != binding:
            raise IblaDenied()
        try:
            require_audit_time(recorded_at)
        except ValueError:
            raise IblaInconsistent() from None
        self._recorded_at = recorded_at
        self._ledger_reader = ledger_reader
        if ledger_reader.version != version:
            raise IblaDenied()

    def _ledger(self):
        reader = self._ledger_reader
        # Independent read-only connection, not the L writer's uncommitted Session.
        if (
            reader.session is self.session
            or reader.session.execute(text("PRAGMA query_only")).scalar_one() != 1
        ):
            raise IblaDenied()
        paths = []
        for session in (self.session, reader.session):
            paths.append(Path(database_path(session)))
        left, right = paths
        if (
            os.path.samefile(left, right)
            or left.parent == right.parent
            or left.parent in right.parents
            or right.parent in left.parents
        ):
            raise IblaDenied()
        # Different paths are necessary, not proof of independently designated custody.
        return reader.read()

    @guarded
    def read(self):
        self._check()
        head = self._head()
        state, confirmed, pending = "EMPTY", Head(), None
        prior_digest = None
        v2_seen = False
        operations = {}
        rows = self._rows()
        for sequence, row in enumerate(rows, 1):
            p, saved, candidate, control_digest = parse_control(
                row.envelope, self.binding, version=self.version
            )
            v2 = p["schema"] == "dohamusic/ibla-checkpoint-control/v2"
            if v2_seen and not v2:
                raise IblaInconsistent()
            v2_seen = v2_seen or v2
            if (
                tuple(row)
                != (
                    p["sequence"],
                    control_digest,
                    candidate.operation_id,
                    candidate.fingerprint,
                    p["previous_digest"],
                    control_digest,
                    p["kind"],
                    row.envelope,
                )
                or p["sequence"] != sequence
                or p["previous_digest"] != prior_digest
            ):
                raise IblaInconsistent()
            kind = p["kind"]
            target = Head(candidate.revision, candidate.digest)
            before = Head(candidate.revision - 1, candidate.previous_digest)
            if kind in {"COMMISSIONING_PENDING", "PREPARED"}:
                if (
                    saved != confirmed
                    or before != confirmed
                    or candidate.operation_id in operations
                    or (kind == "COMMISSIONING_PENDING" and state != "EMPTY")
                    or (kind == "PREPARED" and state != "CONFIRMED")
                    or (state == "EMPTY" and kind != "COMMISSIONING_PENDING")
                ):
                    raise IblaInconsistent()
                operations[candidate.operation_id] = candidate.fingerprint
                pending = candidate.envelope
            elif kind in {"CONFIRMED", "UNCERTAIN"}:
                if (
                    state not in {"COMMISSIONING_PENDING", "PREPARED", "UNCERTAIN"}
                    or pending != candidate.envelope
                    or (kind == "UNCERTAIN" and state == "UNCERTAIN")
                    or saved != (target if kind == "CONFIRMED" else confirmed)
                ):
                    raise IblaInconsistent()
                if kind == "CONFIRMED":
                    confirmed, pending = target, None
            state, prior_digest = kind, control_digest
        if head != Head(len(rows), prior_digest) or self._head() != head:
            raise IblaInconsistent()
        return CheckpointView(self.binding, head, state, confirmed, pending)

    def _append_control(self, view, candidate, kind):
        confirmed = (
            Head(candidate.revision, candidate.digest) if kind == "CONFIRMED" else (view.confirmed)
        )
        wire = control_wire(
            self.binding,
            sequence=view.head.revision + 1,
            previous=view.head.digest,
            kind=kind,
            confirmed=confirmed,
            pending=candidate.envelope,
            recorded_at=self._recorded_at,
            version=self.version,
        )
        p, _, _, control_digest = parse_control(wire, self.binding, version=self.version)
        self._insert(
            (
                p["sequence"],
                control_digest,
                candidate.operation_id,
                candidate.fingerprint,
                view.head.digest,
                control_digest,
                kind,
                wire,
            )
        )
        return OperationResult(
            candidate.operation_id,
            candidate.fingerprint,
            Head(candidate.revision, candidate.digest),
            kind,
        )

    def _operation(self, operation_id, fingerprint):
        if type(operation_id) is not str or type(fingerprint) is not str:
            raise IblaInconsistent()
        require_uuid(operation_id)
        require_digest(fingerprint)
        rows = self.session.execute(
            text("SELECT envelope FROM ibla_events WHERE operation_id=:id ORDER BY revision"),
            {"id": operation_id},
        ).all()
        if not rows:
            return None
        p, _, candidate, _ = parse_control(rows[-1][0], self.binding, version=self.version)
        if candidate.fingerprint != fingerprint:
            raise IblaConflict()
        return OperationResult(
            operation_id, fingerprint, Head(candidate.revision, candidate.digest), p["kind"]
        )

    @guarded
    def prepare(self, envelope, *, expected):
        candidate = parse_event(envelope, self.binding, version=self.version)
        if candidate.kind == "REGISTRATION_COMMITTED":
            raise IblaDenied()
        return self._prepare_candidate(envelope, expected=expected)

    @guarded
    def _prepare_registration(self, writer, record, *, expected):
        from backend.bootstrap_authority.ibla.registration_writer import _RegistrationCommitWriter

        if type(writer) is not _RegistrationCommitWriter:
            raise IblaDenied()
        writer._preparing(record, self.session)
        if record.event.kind != "REGISTRATION_COMMITTED" or record.source.binding != self.binding:
            raise IblaDenied()
        result = self._prepare_candidate(record.event.envelope, expected=expected)
        writer._preparing(record, self.session)
        return result

    def _prepare_candidate(self, envelope, *, expected):
        if type(expected) is not Head:
            raise IblaInconsistent()
        expected.validate()
        candidate = parse_event(envelope, self.binding, version=self.version)
        view = self.read()
        ledger = self._ledger()
        prior = self._operation(candidate.operation_id, candidate.fingerprint)
        if prior is not None:
            if prior.state == "CONFIRMED":
                self._require_confirmed(view, ledger)
            return prior  # Never reset/reappend a pending operation.
        if (
            view.head != expected
            or view.state not in {"EMPTY", "CONFIRMED"}
            or ledger.head != view.confirmed
            or Head(candidate.revision - 1, candidate.previous_digest) != view.confirmed
            or (ledger.events and ledger.events[-1].kind == "RETIRE")
        ):
            raise IblaConflict()
        return self._append_control(
            view, candidate, "COMMISSIONING_PENDING" if view.state == "EMPTY" else "PREPARED"
        )

    @guarded
    def confirm(self, operation_id, fingerprint):
        view = self.read()
        ledger = self._ledger()  # Full canonical history from H-owned read-only source.
        prior = self._operation(operation_id, fingerprint)
        if prior is None:
            raise IblaConflict()
        if prior.state == "CONFIRMED":
            self._require_confirmed(view, ledger)
            return prior
        if view.pending is None:
            raise IblaConflict()
        candidate = parse_event(view.pending, self.binding, version=self.version)
        if candidate.operation_id != operation_id or candidate.fingerprint != fingerprint:
            raise IblaConflict()
        if (
            ledger.head != Head(candidate.revision, candidate.digest)
            or not ledger.events
            or ledger.events[-1].envelope != candidate.envelope
        ):
            # Absent does NOT mean never committed; retain barrier for explicit reconcile.
            raise IblaDenied()
        return self._append_control(view, candidate, "CONFIRMED")

    @guarded
    def mark_uncertain(self, operation_id, fingerprint):
        view = self.read()
        prior = self._operation(operation_id, fingerprint)
        if prior is None or prior.state == "CONFIRMED" or view.pending is None:
            raise IblaConflict()
        candidate = parse_event(view.pending, self.binding, version=self.version)
        if candidate.operation_id != operation_id:
            raise IblaConflict()
        if view.state == "UNCERTAIN":
            return prior
        return self._append_control(view, candidate, "UNCERTAIN")

    @staticmethod
    def _require_confirmed(view, ledger):
        if (
            view.state != "CONFIRMED"
            or view.pending is not None
            or view.confirmed.revision == 0
            or ledger.head != view.confirmed
        ):
            raise IblaDenied()

    @guarded
    def read_correlated(self):
        view = self.read()
        self._require_confirmed(view, self._ledger())
        return view  # Persistence correlation only; authenticity/current custody NOT proven.
