"""Corruption/rollback are injected only into disposable, closed fixture stores."""

import json
import shutil
import sqlite3

import pytest
import rfc8785
from sqlalchemy.exc import SQLAlchemyError

from backend.bootstrap_authority.ibla.contracts import Head, IblaDenied
from backend.tests.ibla_support import BINDING, advance, candidate, keeper, ledger, stores


def tamper(path, mutate):
    with sqlite3.connect(path) as connection:
        triggers = connection.execute(
            "SELECT name,sql FROM sqlite_master WHERE type='trigger'"
        ).fetchall()
        for name, _ in triggers:
            connection.execute('DROP TRIGGER "' + name + '"')
        mutate(connection)
        for _, sql in triggers:
            connection.execute(sql)


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ibla_events SET digest='bad' WHERE revision=1",
        "UPDATE ibla_events SET envelope=x'ff' WHERE revision=1",
        "DELETE FROM ibla_events WHERE revision=1",
        "UPDATE ibla_events SET previous_digest='bad' WHERE revision=2",
        "UPDATE ibla_head SET digest='bad'",
        "UPDATE ibla_head SET revision=1",
        "UPDATE ibla_identity SET binding=x'7b7d'",
    ],
)
def test_corrupt_ledger_fails_closed(tmp_path, sql):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    advance(lp, hp, number=101)
    tamper(lp, lambda c: c.execute(sql))
    with ledger(lp, readonly=True) as repo, pytest.raises(IblaDenied):
        repo.read()
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.read_correlated()


@pytest.mark.parametrize(
    "field,value",
    [
        ("ledger_id", "00000000-0000-0000-0000-000000000099"),
        ("authority_epoch", 2),
        ("authority_epoch", True),
    ],
)
def test_persisted_envelope_wrong_binding(tmp_path, field, value):
    lp, hp = stores(tmp_path)
    advance(lp, hp)

    def mutate(c):
        p = json.loads(c.execute("SELECT envelope FROM ibla_events").fetchone()[0])
        p["binding"][field] = value
        c.execute("UPDATE ibla_events SET envelope=?", (rfc8785.dumps(p),))

    tamper(lp, mutate)
    with ledger(lp, readonly=True) as repo, pytest.raises(IblaDenied):
        repo.read()


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE ibla_events SET envelope=x'7b7d' WHERE revision=2",
        "UPDATE ibla_events SET fingerprint='wrong' WHERE revision=1",
        "DELETE FROM ibla_events WHERE revision=1",
        "UPDATE ibla_head SET digest='wrong'",
        "UPDATE ibla_identity SET binding=x'7b7d'",
    ],
)
def test_checkpoint_corruption(tmp_path, sql):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    tamper(hp, lambda c: c.execute(sql))
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.read_correlated()


@pytest.mark.parametrize("role", ["L", "H"])
def test_exact_schema_and_version(tmp_path, role):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    path = lp if role == "L" else hp
    with sqlite3.connect(path) as c:
        c.execute("CREATE TABLE surprise (value TEXT)")
    context = ledger(lp, readonly=True) if role == "L" else keeper(lp, hp)
    with context as repo, pytest.raises(IblaDenied):
        repo.read()


@pytest.mark.parametrize("role", ["L", "H"])
@pytest.mark.parametrize("table", ["ibla_identity", "ibla_head", "ibla_events"])
@pytest.mark.parametrize("operation", ["DELETE", "UPDATE", "REPLACE"])
def test_sql_immutability_including_replace(tmp_path, role, table, operation):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    path = lp if role == "L" else hp
    with sqlite3.connect(path) as c:
        if operation == "DELETE":
            sql = "DELETE FROM " + table
        elif operation == "UPDATE":
            column = "version" if table == "ibla_identity" else "revision"
            sql = "UPDATE " + table + " SET " + column + "=" + column
        else:
            sql = "INSERT OR REPLACE INTO " + table + " SELECT * FROM " + table
        with pytest.raises(sqlite3.IntegrityError):
            c.execute(sql)


def test_replace_cannot_steal_operation_identity(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    with sqlite3.connect(lp) as c, pytest.raises(sqlite3.IntegrityError):
        c.execute(
            "INSERT OR REPLACE INTO ibla_events SELECT 2,'other',operation_id,"
            "fingerprint,digest,'different','HISTORY_BLOCK',envelope FROM ibla_events"
        )
    with ledger(lp, readonly=True) as repo:
        assert len(repo.read().events) == 1
        assert repo.read().head.digest == first.digest


@pytest.mark.parametrize("which", ["L", "H"])
def test_one_store_rollback_mismatch(tmp_path, which):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    backup = tmp_path / "old.sqlite"
    target = lp if which == "L" else hp
    shutil.copyfile(target, backup)
    advance(lp, hp, number=101)
    shutil.copyfile(backup, target)
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.read_correlated()


def test_delete_recreate_l_and_missing_h_deny(tmp_path):
    from backend.tests.ibla_support import provision

    lp, hp = stores(tmp_path)
    advance(lp, hp)
    lp.unlink()
    provision(lp, "L", BINDING)
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.read_correlated()
    hp.unlink()
    with pytest.raises(SQLAlchemyError), keeper(lp, hp) as h:
        h.read()
    assert not hp.exists()  # No automatic H self-enrollment.


def test_fresh_empty_h_not_confirmed_authority(tmp_path):
    from backend.tests.ibla_support import provision

    lp, hp = stores(tmp_path)
    advance(lp, hp)
    hp.unlink()
    provision(hp, "H")  # Explicit attack fixture, not an operational API.
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.read_correlated()
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.prepare(candidate(), expected=Head())


def test_consistent_full_rollback_NOT_GUARANTEED(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    old_l, old_h = tmp_path / "old-l", tmp_path / "old-h"
    shutil.copyfile(lp, old_l)
    shutil.copyfile(hp, old_h)
    advance(lp, hp, number=101)
    shutil.copyfile(old_l, lp)
    shutil.copyfile(old_h, hp)
    # Remaining observations cannot detect a consistent old prefix. This test
    # documents an explicit limitation, NOT anti-rollback security success.
    with keeper(lp, hp) as h:
        assert h.read_correlated().confirmed == Head(1, first.digest)


def test_last_prepared_h_rollback_NOT_GUARANTEED(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    old_h = tmp_path / "old-h"
    shutil.copyfile(hp, old_h)
    with keeper(lp, hp) as h:
        h.prepare(candidate(Head(1, first.digest), number=101), expected=h.read().head)
    shutil.copyfile(old_h, hp)
    with keeper(lp, hp) as h:
        assert h.read_correlated().confirmed == Head(1, first.digest)


@pytest.mark.parametrize("role", ["L", "H"])
def test_unsupported_persisted_version(tmp_path, role):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    path = lp if role == "L" else hp

    def mutate(c):
        c.execute("PRAGMA ignore_check_constraints=ON")
        c.execute("UPDATE ibla_identity SET version=2")

    tamper(path, mutate)
    context = ledger(lp, readonly=True) if role == "L" else keeper(lp, hp)
    with context as repo, pytest.raises(IblaDenied):
        repo.read()
