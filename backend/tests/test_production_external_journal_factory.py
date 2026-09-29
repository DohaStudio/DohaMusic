"""Production runtime opens only a verified, already provisioned journal."""

from __future__ import annotations

import shutil
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from threading import Event, get_ident
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.bootstrap_authority.journal_schema_v1 import (
    IMMUTABILITY_DDL,
    SCHEMA_OBJECT_DDL,
    SCHEMA_VERSION,
    migrate_empty_journal,
)
from backend.bootstrap_authority.production_configuration import JOURNAL_FILE
from backend.bootstrap_authority.production_external_journal import (
    JOURNAL_ROLE,
    ProductionExternalJournalFactory,
    ProductionExternalJournalFactoryDenied,
    ProductionExternalJournalReadiness,
)
from backend.tests.test_bootstrap_lifecycle_journal import JOURNAL, genesis
from backend.tests.test_production_deployment_configuration import (
    encoded,
    expectations,
    payload,
)


def reviewed(path: str, *, journal_id=JOURNAL):
    expected = replace(expectations(), journal_id=journal_id)
    value = payload()
    value["journal_id"] = journal_id
    value["external_journal_path"] = path
    return encoded(value), expected


def schema_ddl(name: str) -> str:
    return next(
        statement
        for statement in SCHEMA_OBJECT_DDL
        if statement.startswith(f"CREATE TRIGGER {name} ")
    )


@pytest.fixture
def journal_path():
    if sys.platform != "win32":
        pytest.skip("native Windows journal path lease")
    parent = Path.cwd() / ".runtime-journals"
    root = parent / f"journal-{uuid4().hex}"
    root.mkdir(parents=True)
    path = root / JOURNAL_FILE
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.begin() as connection:
        migrate_empty_journal(connection)
    with Session(engine) as session, session.begin():
        JournalRepository(session).initialize_public_identity(JOURNAL)
    genesis(engine)
    engine.dispose()
    try:
        yield path
    finally:
        shutil.rmtree(root, ignore_errors=True)
        with suppress(OSError):
            parent.rmdir()


def test_descriptor_exactly_binds_reviewed_configuration_without_opening():
    raw, expected = reviewed(r"E:\DohaMusicJournal\durable-admission-journal-v1.sqlite3")
    descriptor = ProductionExternalJournalFactory._descriptor(raw, expected)
    assert descriptor.installation_id == expected.installation_id
    assert descriptor.deployment_id == expected.deployment_id
    assert descriptor.journal_id == JOURNAL
    assert descriptor.fixed_filename == JOURNAL_FILE
    assert descriptor.journal_schema_version == SCHEMA_VERSION
    assert descriptor.role == JOURNAL_ROLE
    assert (
        descriptor.readiness
        is ProductionExternalJournalReadiness.RUNTIME_FACTORY_READY_EXISTING_JOURNAL_REQUIRED
    )
    with pytest.raises(FrozenInstanceError):
        descriptor.fixed_path = r"E:\replacement.sqlite3"


def test_valid_existing_journal_has_bounded_session_and_exact_snapshot(journal_path):
    raw, expected = reviewed(str(journal_path))
    factory = ProductionExternalJournalFactory()
    with factory.open_existing(raw, expected=expected) as runtime:
        assert runtime.readiness is ProductionExternalJournalReadiness.EXISTING_JOURNAL_VERIFIED
        with runtime.open_session() as capability:
            transaction = capability._transaction
            snapshot = runtime.verified_snapshot(capability)
            assert transaction.is_active
            assert snapshot.head.journal_id == JOURNAL
            assert snapshot.head.revision == 1
            assert len(snapshot.events) == 1
            assert runtime._reconciliation_engine(capability) is capability._session.get_bind()
            for value in (factory, runtime, capability):
                assert not hasattr(value, "commit")
                assert not hasattr(value, "rollback")
                assert not hasattr(value, "admit")
        assert not transaction.is_active
        with pytest.raises(ProductionExternalJournalFactoryDenied):
            runtime.verified_snapshot(capability)


def test_runtime_denies_overlapping_sessions_and_allows_orderly_reopen(journal_path):
    raw, expected = reviewed(str(journal_path))
    with ProductionExternalJournalFactory().open_existing(raw, expected=expected) as runtime:
        with runtime.open_session() as first:
            with pytest.raises(ProductionExternalJournalFactoryDenied), runtime.open_session():
                pass
            with ThreadPoolExecutor(max_workers=1) as pool:

                def overlapping_open():
                    with runtime.open_session():
                        pytest.fail("overlapping root session admitted")

                assert type(pool.submit(overlapping_open).exception(timeout=10)) is (
                    ProductionExternalJournalFactoryDenied
                )
            assert runtime.verified_snapshot(first).head.journal_id == JOURNAL
        with runtime.open_session() as second:
            assert runtime.verified_snapshot(second).head.revision == 1


def test_missing_journal_is_not_created():
    if sys.platform != "win32":
        pytest.skip("native Windows journal path lease")
    root = Path.cwd() / ".runtime-journals" / f"missing-{uuid4().hex}"
    root.mkdir(parents=True)
    path = root / JOURNAL_FILE
    raw, expected = reviewed(str(path))
    try:
        with (
            pytest.raises(ProductionExternalJournalFactoryDenied),
            ProductionExternalJournalFactory().open_existing(raw, expected=expected),
        ):
            pass
        assert not path.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
        with suppress(OSError):
            root.parent.rmdir()


def test_schema_without_identity_or_genesis_is_unavailable(journal_path):
    path = journal_path
    path.unlink()
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.begin() as connection:
        migrate_empty_journal(connection)
    engine.dispose()
    raw, expected = reviewed(str(path))
    with (
        pytest.raises(ProductionExternalJournalFactoryDenied),
        ProductionExternalJournalFactory().open_existing(raw, expected=expected),
    ):
        pass


def test_wrong_journal_identity_is_denied(journal_path):
    wrong = "88888888-8888-4888-8888-888888888888"
    raw, expected = reviewed(str(journal_path), journal_id=wrong)
    with (
        pytest.raises(ProductionExternalJournalFactoryDenied),
        ProductionExternalJournalFactory().open_existing(raw, expected=expected),
    ):
        pass


@pytest.mark.parametrize("damage", ["digest", "truncate", "revision"])
def test_corrupt_truncated_or_reset_history_is_denied(journal_path, damage):
    engine = create_engine(f"sqlite:///{journal_path.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER deployment_journal_events_update")
        connection.exec_driver_sql("DROP TRIGGER deployment_journal_events_delete")
        if damage == "digest":
            connection.exec_driver_sql(
                "UPDATE deployment_journal_events SET event_digest='sha256:' || printf('%064d',0)"
            )
        elif damage == "truncate":
            connection.exec_driver_sql("DELETE FROM deployment_journal_events")
        else:
            connection.exec_driver_sql("DROP TRIGGER deployment_journal_guard_update")
            connection.exec_driver_sql(
                "UPDATE deployment_journal_guard SET revision=0,trust_revision=0,"
                "head_digest=NULL,current_key_id=NULL,last_key_id=NULL"
            )
            connection.exec_driver_sql(schema_ddl("deployment_journal_guard_update"))
        connection.exec_driver_sql(IMMUTABILITY_DDL[2])
        connection.exec_driver_sql(IMMUTABILITY_DDL[3])
    engine.dispose()
    raw, expected = reviewed(str(journal_path))
    with (
        pytest.raises(ProductionExternalJournalFactoryDenied),
        ProductionExternalJournalFactory().open_existing(raw, expected=expected),
    ):
        pass


def test_unsupported_or_modified_schema_is_denied(journal_path):
    engine = create_engine(f"sqlite:///{journal_path.as_posix()}")
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER deployment_journal_guard_delete")
    engine.dispose()
    raw, expected = reviewed(str(journal_path))
    with (
        pytest.raises(ProductionExternalJournalFactoryDenied),
        ProductionExternalJournalFactory().open_existing(raw, expected=expected),
    ):
        pass


def test_wrong_installation_and_path_attacks_fail_before_open(journal_path):
    raw, expected = reviewed(str(journal_path))
    value = payload()
    value["journal_id"] = JOURNAL
    value["external_journal_path"] = str(journal_path)
    value["installation_id"] = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    with (
        pytest.raises(ProductionExternalJournalFactoryDenied),
        ProductionExternalJournalFactory().open_existing(encoded(value), expected=expected),
    ):
        pass

    for attack in (
        r"e:\DohaMusicJournal\durable-admission-journal-v1.sqlite3",
        r"\\server\share\durable-admission-journal-v1.sqlite3",
        r"E:\DohaMusicJournal\..\durable-admission-journal-v1.sqlite3",
        r"E:\DohaMusicJournal\durable-admission-journal-v1.sqlite3:stream",
        r"E:\temp\durable-admission-journal-v1.sqlite3",
    ):
        value = payload()
        value["journal_id"] = JOURNAL
        value["external_journal_path"] = attack
        with (
            pytest.raises(ProductionExternalJournalFactoryDenied),
            ProductionExternalJournalFactory().open_existing(encoded(value), expected=expected),
        ):
            pass


def test_rename_replacement_is_blocked_until_runtime_cleanup(journal_path):
    raw, expected = reviewed(str(journal_path))
    replacement = journal_path.with_name("replacement.sqlite3")
    with (
        ProductionExternalJournalFactory().open_existing(raw, expected=expected),
        pytest.raises(PermissionError),
    ):
        journal_path.replace(replacement)
    journal_path.replace(replacement)
    replacement.replace(journal_path)


def test_thread_substitution_and_factory_subclass_are_denied(journal_path):
    raw, expected = reviewed(str(journal_path))

    class HostileFactory(ProductionExternalJournalFactory):
        pass

    with (
        pytest.raises(ProductionExternalJournalFactoryDenied),
        HostileFactory().open_existing(raw, expected=expected),
    ):
        pass

    with (
        ProductionExternalJournalFactory().open_existing(raw, expected=expected) as runtime,
        runtime.open_session() as capability,
        ThreadPoolExecutor(max_workers=1) as pool,
    ):
        error = pool.submit(runtime.verified_snapshot, capability).exception()
        assert type(error) is ProductionExternalJournalFactoryDenied


def test_factory_open_and_verification_do_not_mutate_journal(journal_path):
    before = journal_path.read_bytes()
    raw, expected = reviewed(str(journal_path))
    with (
        ProductionExternalJournalFactory().open_existing(raw, expected=expected) as runtime,
        runtime.open_session() as capability,
    ):
        runtime.verified_snapshot(capability)
    assert journal_path.read_bytes() == before
    with sqlite3.connect(journal_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM deployment_journal_events").fetchone() == (
            1,
        )


def test_cleanup_finishes_before_next_root_session(journal_path, monkeypatch):
    raw, expected = reviewed(str(journal_path))
    close_started, finish_close, contender_observed = Event(), Event(), Event()
    contender_thread = []
    acquired = []
    transactions = []
    connections = []
    with ProductionExternalJournalFactory().open_existing(raw, expected=expected) as runtime:
        original_lock = runtime._lock

        class ObservedLock:
            def __enter__(self):
                if contender_thread and get_ident() == contender_thread[0]:
                    if not original_lock.acquire(blocking=False):
                        contender_observed.set()
                        original_lock.acquire()
                else:
                    original_lock.acquire()
                return self

            def __exit__(self, *_):
                original_lock.release()

        monkeypatch.setattr(runtime, "_lock", ObservedLock())

        def first_session():
            with runtime.open_session() as first:
                transactions.append(first._transaction)
                connections.append(first._session.connection().connection.driver_connection)
                original_close = first._session.close

                def controlled_close():
                    close_started.set()
                    assert finish_close.wait(10), "cleanup release not signalled"
                    original_close()

                monkeypatch.setattr(first._session, "close", controlled_close)

        def next_session():
            contender_thread.append(get_ident())
            try:
                with runtime.open_session() as second:
                    acquired.append(True)
                    connections.append(second._session.connection().connection.driver_connection)
                    contender_observed.set()
                    assert not transactions[0].is_active
                    assert runtime.verified_snapshot(second).head.revision == 1
            finally:
                contender_observed.set()

        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(first_session)
            assert close_started.wait(10), "cleanup did not start"
            next_future = pool.submit(next_session)
            try:
                assert contender_observed.wait(10), "contender did not reach admission"
                assert transactions[0].is_active
                assert acquired == []
            finally:
                finish_close.set()
            first_future.result(timeout=10)
            next_future.result(timeout=10)
        assert acquired == [True]
        assert connections[0] is connections[1]


def test_close_failure_permanently_denies_runtime(journal_path, monkeypatch):
    raw, expected = reviewed(str(journal_path))
    with ProductionExternalJournalFactory().open_existing(raw, expected=expected) as runtime:
        with (
            pytest.raises(ProductionExternalJournalFactoryDenied) as denied,
            runtime.open_session() as capability,
        ):
            original_close = capability._session.close

            def failed_close():
                raise RuntimeError("private cleanup detail")

            monkeypatch.setattr(capability._session, "close", failed_close)
        assert str(denied.value) == "PRODUCTION_EXTERNAL_JOURNAL_FACTORY_DENIED"
        assert runtime._closed
        assert not runtime._sessions
        with pytest.raises(ProductionExternalJournalFactoryDenied):
            runtime.verified_snapshot(capability)
        with pytest.raises(ProductionExternalJournalFactoryDenied), runtime.open_session():
            pass
        assert not runtime._sessions
        # Explicit fixture cleanup does not make the failed runtime reusable.
        original_close()
        with pytest.raises(ProductionExternalJournalFactoryDenied), runtime.open_session():
            pass


def test_foreign_runtime_capability_is_denied(journal_path):
    raw, expected = reviewed(str(journal_path))
    with (
        ProductionExternalJournalFactory().open_existing(raw, expected=expected) as first,
        ProductionExternalJournalFactory().open_existing(raw, expected=expected) as second,
        first.open_session() as capability,
    ):
        with pytest.raises(ProductionExternalJournalFactoryDenied):
            second.verified_snapshot(capability)
        assert first.verified_snapshot(capability).head.revision == 1


def test_replaced_root_transaction_invalidates_capability(journal_path):
    raw, expected = reviewed(str(journal_path))
    with (
        ProductionExternalJournalFactory().open_existing(raw, expected=expected) as runtime,
        runtime.open_session() as capability,
    ):
        original = capability._transaction
        assert capability._session.get_transaction() is original
        capability._session.rollback()
        replacement = capability._session.begin()
        assert replacement is not original
        assert replacement.is_active
        with pytest.raises(ProductionExternalJournalFactoryDenied):
            runtime.verified_snapshot(capability)
        with pytest.raises(ProductionExternalJournalFactoryDenied):
            runtime._reconciliation_engine(capability)
