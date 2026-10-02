"""Disposable SQLite fixture owners, deliberately NOT imported by production."""

import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.bootstrap_authority.ibla.checkpoint import CheckpointRepository
from backend.bootstrap_authority.ibla.codec import encode_event, parse_event
from backend.bootstrap_authority.ibla.contracts import Binding, Head
from backend.bootstrap_authority.ibla.repository import LedgerRepository
from backend.bootstrap_authority.ibla.schema import install_empty_store
from backend.bootstrap_authority.lifecycle_verifier import digest


def uid(n):
    return str(UUID(int=n))


BINDING = Binding(
    uid(1),
    uid(2),
    digest(b"anchor fixture"),
    uid(3),
    uid(4),
    uid(5),
    digest(b"proof fixture"),
    uid(6),
    uid(7),
    digest(b"designation fixture"),
    1,
)


def engine(path, *, readonly=False):
    uri = Path(path).resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    result = create_engine(
        "sqlite+pysqlite://",
        poolclass=NullPool,
        creator=lambda: sqlite3.connect(uri, uri=True, timeout=0.0, check_same_thread=False),
    )

    @event.listens_for(result, "connect")
    def configure(dbapi, _):
        dbapi.execute("PRAGMA synchronous=EXTRA")
        if readonly:
            dbapi.execute("PRAGMA query_only=ON")

    return result


def provision(path, role, binding=BINDING):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Fixture-only explicit exclusive creation. Never a runtime missing-file fallback.
    with path.open("xb"):
        pass
    e = engine(path)
    try:
        with e.begin() as c:
            install_empty_store(c, role=role, binding=binding)
    finally:
        e.dispose()


def stores(root):
    lp, h = Path(root) / "ledger" / "lp.sqlite", Path(root) / "keeper" / "h.sqlite"
    provision(lp, "L")
    provision(h, "H")
    return lp, h


@contextmanager
def session(path, *, readonly=False):
    e = engine(path, readonly=readonly)
    try:
        with Session(e) as s, s.begin():
            s.execute(text("BEGIN" if readonly else "BEGIN IMMEDIATE"))
            yield s
    finally:
        e.dispose()


@contextmanager
def ledger(path, *, readonly=False, binding=BINDING):
    with session(path, readonly=readonly) as s:
        yield LedgerRepository(s, binding)


@contextmanager
def keeper(lp, h, *, binding=BINDING):
    # H writer owns only H + separate read-only L; no L write connection.
    with session(h) as hs, session(lp, readonly=True) as ls:
        yield CheckpointRepository(
            hs,
            binding,
            ledger_reader=LedgerRepository(ls, binding),
            recorded_at="2026-10-01T00:00:00Z",
        )


def candidate(expected=None, *, number=100, kind=None, binding=BINDING):
    expected = expected if expected is not None else Head()
    return encode_event(
        binding,
        event_id=uid(number),
        operation_id=uid(number + 10000),
        expected=expected,
        kind=kind or ("COMMISSION" if expected.revision == 0 else "HISTORY_BLOCK"),
        evidence_digest=digest(b"public fixture evidence"),
        recorded_at="2026-10-01T00:00:00Z",
    )


def advance(lp, h, *, number=100, kind=None):
    with ledger(lp, readonly=True) as repo:
        expected = repo.read().head
    wire = candidate(expected, number=number, kind=kind)
    with keeper(lp, h) as repo:
        repo.prepare(wire, expected=repo.read().head)
    with ledger(lp) as repo:
        result = repo.append(wire, expected=expected)
    with keeper(lp, h) as repo:
        repo.confirm(result.operation_id, result.fingerprint)
    return result


def process_stage(lp, h, stage, number=101):
    # Spawned interpreter exercises real commits, fresh imports/connections and abrupt exit.
    import os

    with ledger(lp, readonly=True) as repo:
        expected = repo.read().head
    wire = candidate(expected, number=number)
    event = parse_event(wire, BINDING)
    with keeper(lp, h) as repo:
        repo.prepare(wire, expected=repo.read().head)
    if stage == "prepared":
        os._exit(0)
    with ledger(lp) as repo:
        repo.append(wire, expected=expected)
    if stage == "appended":
        os._exit(0)
    with keeper(lp, h) as repo:
        repo.confirm(event.operation_id, event.fingerprint)
    os._exit(0)


def process_read(lp, h, queue):
    with keeper(lp, h) as repo:
        queue.put(asdict(repo.read_correlated()))
