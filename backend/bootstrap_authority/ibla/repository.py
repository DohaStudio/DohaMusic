"""Complete local-history verification and flush-only public persistence CAS."""

from functools import wraps

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from backend.bootstrap_authority.ibla.codec import binding_wire, parse_event
from backend.bootstrap_authority.ibla.contracts import (
    Head,
    IblaConflict,
    IblaDenied,
    IblaInconsistent,
    LedgerView,
)
from backend.bootstrap_authority.ibla.schema import require_schema


def guarded(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        if self._failed:
            raise IblaDenied()
        try:
            return method(self, *args, **kwargs)
        except IblaDenied:
            self._failed = True
            raise
        except IntegrityError:
            self._failed = True
            raise IblaConflict() from None
        except (SQLAlchemyError, OSError):
            self._failed = True
            raise IblaDenied() from None
        except (ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            self._failed = True
            raise IblaInconsistent() from None

    return call


def database_path(session):
    rows = session.execute(text("PRAGMA database_list")).all()
    main = [row for row in rows if row[1] == "main"]
    extra = [row for row in rows if row[1] != "main"]
    if (
        len(main) != 1
        or not main[0][2]
        or len(extra) > 1
        or any(row[1] != "temp" or row[2] != "" for row in extra)
        or session.execute(text("SELECT name FROM sqlite_temp_master")).first()
    ):
        raise IblaDenied()
    return main[0][2]


class _Repository:
    role = None

    def __init__(self, session, binding, *, version=1):
        if type(session) is not Session:
            raise IblaDenied()
        try:
            binding_wire(binding)
        except (ValueError, TypeError):
            raise IblaInconsistent() from None
        self.session, self.binding = session, binding
        if type(version) is not int or version not in {1, 2}:
            raise IblaDenied()
        self.version = version
        self._failed = False
        self._transaction = session.get_transaction()
        if self._transaction is None or session.in_nested_transaction():
            raise IblaDenied()

    def _check(self):
        # Require an ACTUAL SQLite transaction, not SQLAlchemy's logical autobegin.
        if (
            self.session.get_transaction() is not self._transaction
            or not self._transaction.is_active
            or self.session.in_nested_transaction()
        ):
            raise IblaDenied()
        c = self.session.connection()
        if c.dialect.name != "sqlite" or not c.connection.driver_connection.in_transaction:
            raise IblaDenied()
        database_path(self.session)
        if (
            self.session.execute(text("PRAGMA journal_mode")).scalar_one() != "delete"
            or self.session.execute(text("PRAGMA synchronous")).scalar_one() != 3
        ):
            raise IblaDenied()
        require_schema(self.session, self.role, self.binding, self.version)

    def _head(self):
        rows = self.session.execute(text("SELECT revision,digest FROM ibla_head")).all()
        if len(rows) != 1:
            raise IblaInconsistent()
        result = Head(*rows[0])
        result.validate()
        return result

    def _rows(self):
        return self.session.execute(
            text(
                "SELECT revision,record_id,operation_id,fingerprint,previous_digest,digest,kind,"
                "envelope FROM ibla_events ORDER BY revision"
            )
        ).all()

    def _insert(self, values):
        # One statement, event + unique operation index + projection/CAS in trigger.
        self.session.execute(
            text(
                "INSERT INTO ibla_events VALUES "
                "(:revision,:record,:operation,:fingerprint,:previous,:digest,:kind,:envelope)"
            ),
            dict(
                zip(
                    (
                        "revision",
                        "record",
                        "operation",
                        "fingerprint",
                        "previous",
                        "digest",
                        "kind",
                        "envelope",
                    ),
                    values,
                    strict=True,
                )
            ),
        )
        self.session.flush()


class LedgerRepository(_Repository):
    """Public consistency only. Caller owns rollback/commit, leases and custody.

    All events in the configured domain are read. This v1 subset supports one
    fixed A/epoch/lineage and only commissioning/block/retire public facts. It
    rejects future authority/epoch/alias transitions, never silently skips them.
    """

    role = "L"

    @guarded
    def read(self):
        self._check()
        head = self._head()
        events, ids, operations = [], set(), set()
        previous = None
        retired = False
        for revision, row in enumerate(self._rows(), 1):
            event = parse_event(row.envelope, self.binding, version=self.version)
            if (
                tuple(row)
                != (
                    event.revision,
                    event.event_id,
                    event.operation_id,
                    event.fingerprint,
                    event.previous_digest,
                    event.digest,
                    event.kind,
                    event.envelope,
                )
                or event.revision != revision
                or event.previous_digest != previous
                or event.event_id in ids
                or event.operation_id in operations
                or retired
            ):
                raise IblaInconsistent()
            ids.add(event.event_id)
            operations.add(event.operation_id)
            previous = event.digest
            retired = event.kind == "RETIRE"
            events.append(event)
        if head != Head(len(events), previous) or self._head() != head:
            raise IblaInconsistent()
        return LedgerView(self.binding, head, tuple(events))

    @guarded
    def append(self, envelope, *, expected):
        if type(expected) is not Head:
            raise IblaInconsistent()
        expected.validate()
        candidate = parse_event(envelope, self.binding, version=self.version)
        if candidate.kind == "REGISTRATION_COMMITTED":
            raise IblaDenied()
        if (candidate.revision, candidate.previous_digest) != (
            expected.revision + 1,
            expected.digest,
        ):
            raise IblaConflict()
        view = self.read()
        # Indexed lookup is an accelerator, never a replacement for whole-history validation.
        prior = self.session.execute(
            text("SELECT envelope FROM ibla_events WHERE operation_id=:id"),
            {"id": candidate.operation_id},
        ).scalar_one_or_none()
        if prior is not None:
            if prior != envelope:
                raise IblaConflict()
            return candidate  # Historical result only, no new authority.
        if view.head != expected or (view.events and view.events[-1].kind == "RETIRE"):
            raise IblaConflict()
        self._insert(
            (
                candidate.revision,
                candidate.event_id,
                candidate.operation_id,
                candidate.fingerprint,
                candidate.previous_digest,
                candidate.digest,
                candidate.kind,
                candidate.envelope,
            )
        )
        return candidate
