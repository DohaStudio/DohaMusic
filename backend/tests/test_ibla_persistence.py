"""Public persistence mechanics in disposable independent stores; no authority fixtures."""

import inspect
import json
from dataclasses import asdict
from unittest.mock import patch

import pytest
import rfc8785
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.bootstrap_authority.ibla.checkpoint import CheckpointRepository
from backend.bootstrap_authority.ibla.codec import parse_event
from backend.bootstrap_authority.ibla.contracts import (
    Head,
    IblaConflict,
    IblaDenied,
    UnavailableIblaPersistence,
)
from backend.bootstrap_authority.ibla.repository import LedgerRepository
from backend.bootstrap_authority.ibla.schema import install_empty_store
from backend.bootstrap_authority.lifecycle_verifier import digest
from backend.tests.ibla_support import (
    BINDING,
    advance,
    candidate,
    engine,
    keeper,
    ledger,
    provision,
    session,
    stores,
    uid,
)


def test_three_phases_and_replay(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    with keeper(lp, hp) as h:
        view = h.read_correlated()
        assert view.state == "CONFIRMED"
        assert view.confirmed == Head(1, first.digest)
        assert view.head.revision == 2
    second = advance(lp, hp, number=101)
    with ledger(lp) as repo:
        assert repo.append(second.envelope, expected=Head(1, first.digest)) == second
        assert repo.read().head.revision == 2
    with keeper(lp, hp) as h:
        result = h.confirm(second.operation_id, second.fingerprint)
        assert result == h.confirm(second.operation_id, second.fingerprint)
        assert h.read().head.revision == 4
        assert h.prepare(second.envelope, expected=Head()) == result


def test_pending_absence_is_uncertain_not_retry(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    wire = candidate(Head(1, first.digest), number=101)
    event = parse_event(wire, BINDING)
    with keeper(lp, hp) as h:
        h.prepare(wire, expected=h.read().head)
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.confirm(event.operation_id, event.fingerprint)
    with keeper(lp, hp) as h:
        assert h.read().state == "PREPARED"
        h.mark_uncertain(event.operation_id, event.fingerprint)
    with keeper(lp, hp) as h:
        before = h.read()
        assert h.mark_uncertain(event.operation_id, event.fingerprint).state == "UNCERTAIN"
        assert h.read() == before
    with keeper(lp, hp) as h, pytest.raises(IblaConflict):
        h.prepare(candidate(Head(1, first.digest), number=102), expected=h.read().head)
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.read_correlated()
    with ledger(lp, readonly=True) as repo:
        assert repo.read().head.revision == 1


def test_caller_rollback_and_no_repository_transaction_ownership(tmp_path):
    lp, _ = stores(tmp_path)
    with pytest.raises(RuntimeError, match="caller"), ledger(lp) as repo:
        with (
            patch.object(repo.session, "commit", side_effect=AssertionError),
            patch.object(repo.session, "rollback", side_effect=AssertionError),
        ):
            repo.append(candidate(), expected=Head())
        raise RuntimeError("caller")
    with ledger(lp, readonly=True) as repo:
        assert repo.read().head == Head()
    for cls in (LedgerRepository, CheckpointRepository):
        assert ".commit(" not in inspect.getsource(cls)
        assert ".rollback(" not in inspect.getsource(cls)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema", "unsupported"),
        ("revision", True),
        ("revision", 1.0),
        ("revision", 9007199254740992),
        ("kind", "INITIAL_AUTHORIZATION_CONSUMED"),
        ("kind", "GENESIS"),
        ("kind", "AUTHORITY_TRANSITION"),
        ("previous_digest", "sha256:" + "a" * 64),
        ("event_id", "bad"),
        ("evidence_digest", "private raw material"),
    ],
)
def test_invalid_envelope(field, value):
    payload = json.loads(candidate())
    payload[field] = value
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    with pytest.raises((ValueError, TypeError)):
        parse_event(raw, BINDING)


@pytest.mark.parametrize(
    "raw", [b"{}", b"\xff", b" " * 16385, b'{"schema":1,"schema":2}', b'{"x":NaN}', b'{"x":1.2}']
)
def test_noncanonical_bytes(raw):
    with pytest.raises((ValueError, TypeError, UnicodeError)):
        parse_event(raw, BINDING)


@pytest.mark.parametrize("field", list(asdict(BINDING)))
def test_every_exact_binding_field(field):
    values = asdict(BINDING)
    values[field] = (
        2
        if field == "authority_epoch"
        else digest(b"different")
        if field.endswith("_digest")
        else uid(500)
    )
    other = type(BINDING)(**values)
    with pytest.raises(ValueError):
        parse_event(candidate(), other)


def test_wrong_bool_epoch_even_python_equality():
    payload = json.loads(candidate())
    payload["binding"]["authority_epoch"] = True
    with pytest.raises(ValueError):
        parse_event(rfc8785.dumps(payload), BINDING)


def test_unknown_field_and_retire_terminal(tmp_path):
    payload = json.loads(candidate())
    payload["secret"] = "not accepted"
    with pytest.raises(ValueError):
        parse_event(rfc8785.dumps(payload), BINDING)
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    terminal = advance(lp, hp, number=101, kind="RETIRE")
    with ledger(lp) as repo, pytest.raises(IblaConflict):
        repo.append(
            candidate(Head(2, terminal.digest), number=102), expected=Head(2, terminal.digest)
        )


def test_conflicting_operation_never_rewritten(tmp_path):
    lp, hp = stores(tmp_path)
    first = advance(lp, hp)
    payload = json.loads(first.envelope)
    payload["evidence_digest"] = digest(b"different evidence")
    wire = rfc8785.dumps(payload)
    with ledger(lp) as repo, pytest.raises(IblaConflict):
        repo.append(wire, expected=Head())
    with keeper(lp, hp) as h, pytest.raises(IblaConflict):
        h.prepare(wire, expected=h.read().head)
    with keeper(lp, hp) as h:
        assert h.read_correlated().confirmed == Head(1, first.digest)


def test_confirmation_rejects_public_summary_and_uncommitted_writer(tmp_path):
    lp, hp = stores(tmp_path)
    with session(hp) as hs, session(lp) as ls:
        h = CheckpointRepository(hs, BINDING, ledger_reader=LedgerRepository(ls, BINDING))
        with pytest.raises(IblaDenied):
            h.prepare(candidate(), expected=Head())
    with session(hp) as hs, pytest.raises(IblaDenied):
        CheckpointRepository(hs, BINDING, ledger_reader=object())


def test_same_directory_is_not_independent(tmp_path):
    lp, hp = tmp_path / "l.sqlite", tmp_path / "h.sqlite"
    provision(lp, "L")
    provision(hp, "H")
    with keeper(lp, hp) as h, pytest.raises(IblaDenied):
        h.prepare(candidate(), expected=Head())


def test_missing_sources_never_created_and_production_unavailable(tmp_path):
    missing = tmp_path / "missing.sqlite"
    e = engine(missing)
    with pytest.raises(SQLAlchemyError), e.connect():
        pass
    e.dispose()
    assert not missing.exists()
    for value in (None, candidate(), BINDING, {"approved": True}):
        with pytest.raises(IblaDenied, match="^IBLA_UNAVAILABLE$"):
            UnavailableIblaPersistence().open(value)
    assert not missing.exists()


def test_nonempty_database_is_not_migrated(tmp_path):
    lp, _ = stores(tmp_path)
    e = engine(lp)
    with e.begin() as c, pytest.raises(IblaDenied):
        install_empty_store(c, role="H", binding=BINDING)
    e.dispose()


def test_error_poison_and_transaction_lifetime(tmp_path):
    lp, hp = stores(tmp_path)
    with ledger(lp) as repo:
        repo.read()
    with pytest.raises(IblaDenied):
        repo.read()
    with keeper(lp, hp) as h:
        with pytest.raises(IblaDenied):
            h.read_correlated()
        with pytest.raises(IblaDenied):
            h.read()


def test_io_error_is_safe_and_no_unsafe_reuse(tmp_path):
    lp, _ = stores(tmp_path)
    with ledger(lp) as repo:
        with (
            patch.object(repo.session, "execute", side_effect=OSError("secret/path")),
            pytest.raises(IblaDenied, match="^IBLA_UNAVAILABLE$") as exc,
        ):
            repo.read()
        assert "secret" not in str(exc.value)
        with pytest.raises(IblaDenied):
            repo.read()


def test_query_plan_uses_head_revision_and_operation_indexes(tmp_path):
    lp, hp = stores(tmp_path)
    advance(lp, hp)
    with ledger(lp, readonly=True) as repo:
        queries = [
            "SELECT * FROM ibla_head WHERE singleton=1",
            "SELECT * FROM ibla_events WHERE revision=1",
            "SELECT * FROM ibla_events WHERE operation_id='test'",
        ]
        for query in queries:
            plan = repo.session.execute(text("EXPLAIN QUERY PLAN " + query)).all()
            assert "SEARCH" in " ".join(str(row) for row in plan)
        plan = repo.session.execute(
            text("EXPLAIN QUERY PLAN SELECT * FROM ibla_events ORDER BY revision")
        ).all()
        assert "TEMP B-TREE" not in " ".join(str(row) for row in plan)
