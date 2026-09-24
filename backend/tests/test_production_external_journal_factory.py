"""Production runtime opens only a verified, already provisioned journal."""

from __future__ import annotations

import shutil
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
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
