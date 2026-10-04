"""Local transaction owners. H and L writes are separate; repositories only flush."""

import sqlite3
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from backend.bootstrap_authority.ibla.checkpoint import CheckpointRepository
from backend.bootstrap_authority.ibla.contracts import IblaDenied
from backend.bootstrap_authority.ibla.repository import LedgerRepository


class _Owners:
    def __init__(self, source, binding, recorded_at):
        self.source, self.binding, self.recorded_at = source, binding, recorded_at

    def __repr__(self):
        return "<IBLA local transaction owners>"

    @contextmanager
    def _write(self, index):
        files = self.source.files[5 + index]
        files.require_unchanged()
        uri = "file:/" + files._journal_path.replace("\\", "/") + "?mode=rw"

        def connect():
            files.require_unchanged()
            c = sqlite3.connect(uri, uri=True, timeout=0, check_same_thread=True)
            try:
                c.execute("PRAGMA synchronous=EXTRA")
                if c.execute("PRAGMA journal_mode").fetchone() != ("delete",):
                    raise IblaDenied()
                files.require_unchanged()
                return c
            except Exception:
                c.close()
                raise

        engine = create_engine("sqlite+pysqlite://", creator=connect, poolclass=NullPool)
        try:
            with Session(engine) as session, session.begin():
                session.execute(text("BEGIN IMMEDIATE"))
                yield session
            files.require_unchanged()
        finally:
            engine.dispose()

    def read(self):
        self.source.require_live()
        with (
            Session(self.source.engines[0]) as ls,
            Session(self.source.engines[1]) as hs,
            ls.begin(),
            hs.begin(),
        ):
            ls.execute(text("BEGIN"))
            hs.execute(text("BEGIN"))
            if any(s.execute(text("PRAGMA query_only")).scalar_one() != 1 for s in (ls, hs)):
                raise IblaDenied()
            ledger = LedgerRepository(ls, self.binding, version=2)
            keeper = CheckpointRepository(
                hs, self.binding, ledger_reader=ledger, recorded_at=self.recorded_at, version=2
            )
            lv, hv = keeper._ledger(), keeper.read()
        self.source.require_live()
        return lv, hv

    def checkpoint(self, action, *args, check=None, registration=None, **kwargs):
        self.source.require_live()
        with self._write(1) as hs:
            with Session(self.source.engines[0]) as ls, ls.begin():
                ls.execute(text("BEGIN"))
                keeper = CheckpointRepository(
                    hs,
                    self.binding,
                    ledger_reader=LedgerRepository(ls, self.binding, version=2),
                    recorded_at=self.recorded_at,
                    version=2,
                )
                if registration is not None:
                    writer, record = registration
                    if action != "prepare" or args != (record.event.envelope,):
                        raise IblaDenied()
                    record.writer_h_transaction = hs.get_transaction()
                    try:
                        result = keeper._prepare_registration(writer, record, **kwargs)
                    finally:
                        record.writer_h_transaction = None
                else:
                    result = getattr(keeper, action)(*args, **kwargs)
            # The independent L read is closed before current source checks/commit.
            if check is not None:
                check()
        self.source.require_live()
        return result
