"""Isolated public facts/disposable signatures, never a production ceremony."""

import base64
import json
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock
from uuid import UUID

import pytest
import rfc8785
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.bootstrap_authority.currentness_ports import (
    CurrentnessUnavailable,
    UnavailableCurrentnessPorts,
)
from backend.bootstrap_authority.journal_repository import JournalRepository
from backend.bootstrap_authority.journal_schema_v1 import migrate_empty_journal
from backend.bootstrap_authority.lifecycle_verifier import (
    DOMAIN,
    SCHEMA,
    LifecycleExpectations,
    LifecycleIntegrityError,
    digest,
    verify_lifecycle_integrity,
)

NOW = datetime(2026, 9, 18, 10, tzinfo=UTC)
JOURNAL = str(UUID(int=1))
SCOPES = ((str(UUID(int=2)), str(UUID(int=3)), str(UUID(int=4))),)
MANIFEST = rfc8785.dumps(
    [dict(zip(("installation_id", "workspace_id", "existing_owner_id"), SCOPES[0], strict=True))]
)


def keys():
    return {
        f"root/test-{i}": Ed25519PrivateKey.from_private_bytes(bytes([i]) * 32) for i in range(1, 6)
    }


def event(revision=1, previous=None, kind="GENESIS", old=None, new="root/test-1"):
    material = keys()
    p = {
        "schema": SCHEMA,
        "algorithm": "Ed25519",
        "journal_id": JOURNAL,
        "event_id": str(UUID(int=100 + revision)),
        "revision": revision,
        "previous_event_digest": previous,
        "previous_trust_revision": revision - 1,
        "trust_revision": revision,
        "designation_id": str(UUID(int=5)),
        "deployment_owner_ref": "deployment/test-owner",
        "event_kind": kind,
        "old_key_id": old,
        "old_key_fingerprint": digest(material[old].public_key().public_bytes_raw())
        if old
        else None,
        "new_key_id": new,
        "new_key_fingerprint": digest(material[new].public_key().public_bytes_raw())
        if new
        else None,
        "designation_record_digest": digest(b"disposable external record"),
        "occurred_at": "2026-09-18T09:00:00Z",
        "affected_scope_manifest_digest": digest(MANIFEST),
        "admission_mode": "CROSS_SIGNED_DESIGNATION"
        if kind == "NORMAL_ROTATION"
        else "EXTERNAL_DESIGNATION",
    }
    expected = LifecycleExpectations(
        JOURNAL,
        p["designation_id"],
        p["deployment_owner_ref"],
        p["designation_record_digest"],
        revision,
        previous,
        revision - 1,
        SCOPES,
        tuple((name, key.public_key().public_bytes_raw()) for name, key in material.items()),
        NOW,
        NOW,
    )
    return p, expected


def wire(p, domain=DOMAIN):
    material = keys()
    signers = (
        [p["old_key_id"], p["new_key_id"]]
        if p["event_kind"] == "NORMAL_ROTATION"
        else [p["old_key_id"] if p["event_kind"] == "REVOKE" else p["new_key_id"]]
    )
    signatures = [
        {
            "signer_key_id": name,
            "signature": base64.urlsafe_b64encode(material[name].sign(domain + rfc8785.dumps(p)))
            .rstrip(b"=")
            .decode(),
        }
        for name in sorted(signers)
    ]
    return rfc8785.dumps({"payload": p, "signatures": signatures})


@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'independent-journal.sqlite'}")
    with engine.begin() as connection:
        migrate_empty_journal(connection)
    with Session(engine) as session, session.begin():
        JournalRepository(session).initialize_public_identity(JOURNAL)
    yield engine
    engine.dispose()


def append(session, p, expected):
    return JournalRepository(session).append_public_event(wire(p), MANIFEST, expected=expected)


def genesis(engine):
    p, expected = event()
    with Session(engine) as session, session.begin():
        return append(session, p, expected).event_digest


@pytest.mark.parametrize("kind", ["NORMAL_ROTATION", "REVOKE", "EXTERNAL_REDESIGNATION"])
def test_lifecycle_transitions(engine, kind):
    previous = genesis(engine)
    p, expected = event(
        2, previous, kind, "root/test-1", None if kind == "REVOKE" else "root/test-2"
    )
    with Session(engine) as session, session.begin():
        receipt = append(session, p, expected)
        head = JournalRepository(session).read_public_head()
        assert head.revision == head.trust_revision == 2
        assert head.head_digest == receipt.event_digest
        assert head.current_key_id == p["new_key_id"]
        assert head.last_key_id == (p["new_key_id"] or p["old_key_id"])


def test_redesignation_after_revoke_preserves_terminal_history(engine):
    previous = genesis(engine)
    p, expected = event(2, previous, "REVOKE", "root/test-1", None)
    with Session(engine) as session, session.begin():
        previous = append(session, p, expected).event_digest
    p, expected = event(3, previous, "EXTERNAL_REDESIGNATION", "root/test-1", "root/test-2")
    with Session(engine) as session, session.begin():
        append(session, p, expected)
        assert session.scalar(text("SELECT count(*) FROM deployment_journal_events")) == 3
        assert (
            session.scalar(text("SELECT kind FROM deployment_journal_events WHERE revision=2"))
            == "REVOKE"
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("algorithm", "RSA"),
        ("schema", "wrong"),
        ("journal_id", "*"),
        ("revision", True),
        ("trust_revision", 2),
        ("previous_trust_revision", -1),
        ("old_key_id", "root/test-1"),
        ("new_key_fingerprint", "sha256:" + "0" * 64),
        ("admission_mode", "CROSS_SIGNED_DESIGNATION"),
        ("occurred_at", "2026-09-19T09:00:00Z"),
        ("designation_record_digest", "wrong"),
        ("event_id", "NOT_UUID"),
        ("deployment_owner_ref", "*"),
        ("affected_scope_manifest_digest", "sha256:" + "0" * 64),
    ],
)
def test_payload_negative(field, value):
    p, expected = event()
    p[field] = value
    with pytest.raises(LifecycleIntegrityError, match="^LIFECYCLE_INTEGRITY_DENIED$"):
        verify_lifecycle_integrity(wire(p), MANIFEST, expected=expected)


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"\xff",
        b"{}",
        b"[NaN]",
        b"[1.2]",
        b"[]" * 9000,
        b'{"payload":{},"payload":{},"signatures":[]}',
        b"[[[[[[]]]]]]",
        b'{"payload":{},"signatures":[],"extra":0}',
    ],
    ids=["empty", "utf8", "object", "nan", "float", "oversize", "duplicate", "depth", "extra"],
)
def test_malformed(raw):
    _, expected = event()
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(raw, MANIFEST, expected=expected)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "extra", "padding", "bad", "unknown"])
def test_signature_negative(mutation):
    p, expected = event()
    value = json.loads(wire(p))
    item = value["signatures"][0]
    if mutation == "missing":
        value["signatures"] = []
    elif mutation in {"duplicate", "extra"}:
        value["signatures"].append(dict(item))
    elif mutation == "padding":
        item["signature"] += "=="
    elif mutation == "bad":
        item["signature"] = "A" * 86
    else:
        item["extra"] = True
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(rfc8785.dumps(value), MANIFEST, expected=expected)


def test_domain_and_cross_signature():
    p, expected = event()
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(wire(p, b"wrong\x00"), MANIFEST, expected=expected)
    p, expected = event(2, digest(b"previous"), "NORMAL_ROTATION", "root/test-1", "root/test-2")
    value = json.loads(wire(p))
    assert verify_lifecycle_integrity(wire(p), MANIFEST, expected=expected)
    value["signatures"].pop()
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(rfc8785.dumps(value), MANIFEST, expected=expected)


@pytest.mark.parametrize(
    "manifest",
    [
        b"[]",
        b"{}",
        b"\xff",
        MANIFEST + b" ",
        rfc8785.dumps(json.loads(MANIFEST) * 2),
        b"[" + b" " * 1_048_576 + b"]",
    ],
    ids=["empty", "object", "utf8", "whitespace", "duplicate", "oversize"],
)
def test_manifest_negative_or_whitespace(manifest):
    p, expected = event()
    if manifest == MANIFEST + b" ":
        assert verify_lifecycle_integrity(wire(p), manifest, expected=expected)
    else:
        with pytest.raises(LifecycleIntegrityError):
            verify_lifecycle_integrity(wire(p), manifest, expected=expected)


@pytest.mark.parametrize(
    "change",
    [
        {"journal_id": str(UUID(int=9))},
        {"revision": 2},
        {"authoritative_scopes": ()},
        {"designation_record_digest": digest(b"wrong")},
        {"checked_at": NOW.replace(tzinfo=None)},
        {"clock_high_water": NOW + timedelta(seconds=1)},
        {"public_keys": ()},
    ],
)
def test_expectations_negative(change):
    p, expected = event()
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(wire(p), MANIFEST, expected=replace(expected, **change))


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM deployment_journal_guard",
        "DELETE FROM deployment_journal_events",
        "UPDATE deployment_journal_guard SET revision=0,trust_revision=0,head_digest=NULL,"
        "current_key_id=NULL,last_key_id=NULL",
        "UPDATE deployment_journal_guard SET current_key_id='forged'",
        "UPDATE deployment_journal_events SET kind='REVOKE'",
        "INSERT OR REPLACE INTO deployment_journal_guard SELECT * FROM deployment_journal_guard",
        "INSERT OR REPLACE INTO deployment_journal_events SELECT * FROM deployment_journal_events",
        "INSERT OR REPLACE INTO deployment_journal_schema VALUES(1)",
        "DELETE FROM deployment_journal_schema",
        "UPDATE deployment_journal_schema SET version=1",
        "INSERT INTO deployment_journal_guard(singleton,journal_id) VALUES(1,'replacement') "
        "ON CONFLICT(singleton) DO UPDATE SET revision=0",
    ],
)
def test_sql_bypass_denied_default_sqlite(engine, sql):
    genesis(engine)
    with Session(engine) as session:
        assert session.scalar(text("PRAGMA recursive_triggers")) == 0
        with pytest.raises(IntegrityError):
            session.execute(text(sql))
        session.rollback()
        assert JournalRepository(session).read_public_head().revision == 1


@pytest.mark.parametrize("kind", ["NORMAL_ROTATION", "REVOKE"])
def test_revoked_key_cannot_sign_current_event(engine, kind):
    previous = genesis(engine)
    p, expected = event(2, previous, "REVOKE", "root/test-1", None)
    with Session(engine) as session, session.begin():
        previous = append(session, p, expected).event_digest
    p, expected = event(
        3, previous, kind, "root/test-1", "root/test-2" if kind == "NORMAL_ROTATION" else None
    )
    with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
        append(session, p, expected)


def test_terminal_reactivation_and_historical_predecessor_denied(engine):
    previous = genesis(engine)
    p, expected = event(2, previous, "NORMAL_ROTATION", "root/test-1", "root/test-2")
    with Session(engine) as session, session.begin():
        previous = append(session, p, expected).event_digest
    for old, new in (("root/test-2", "root/test-1"), ("root/test-1", "root/test-3")):
        p, expected = event(3, previous, "EXTERNAL_REDESIGNATION", old, new)
        with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
            append(session, p, expected)


def test_atomic_rollback_and_lost_response(engine):
    p, expected = event()
    with Session(engine) as session:
        append(session, p, expected)
        session.rollback()  # Crash before caller commit leaves no event/pointer change.
        assert JournalRepository(session).read_public_head().revision == 0
    previous = genesis(engine)  # Durable commit, simulate lost response/restart.
    with Session(engine) as session:
        assert JournalRepository(session).read_public_head().head_digest == previous
        with pytest.raises(IntegrityError):
            append(session, p, expected)  # Never silently retry/re-enroll old head.


def test_trigger_failure_rolls_back_entire_statement(engine):
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TRIGGER injected_failure AFTER UPDATE ON deployment_journal_guard "
            "BEGIN SELECT RAISE(ABORT,'FAULT'); END"
        )
    p, expected = event()
    with Session(engine) as session:
        with pytest.raises(IntegrityError):
            append(session, p, expected)
        assert session.scalar(text("SELECT count(*) FROM deployment_journal_events")) == 0
        assert JournalRepository(session).read_public_head().revision == 0


def test_concurrent_rotation_revoke_same_head_one_winner(engine):
    previous = genesis(engine)

    def run(kind):
        p, expected = event(
            2, previous, kind, "root/test-1", None if kind == "REVOKE" else "root/test-2"
        )
        try:
            with Session(engine) as session, session.begin():
                append(session, p, expected)
            return "winner"
        except IntegrityError:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(run, ("NORMAL_ROTATION", "REVOKE"))) == ["stale", "winner"]
    with Session(engine) as session:
        assert JournalRepository(session).read_public_head().revision == 2
        assert session.scalar(text("SELECT count(*) FROM deployment_journal_events")) == 2


def test_repository_never_owns_transaction(engine):
    p, expected = event()
    with Session(engine) as session:
        session.commit = Mock(side_effect=AssertionError("repository commit"))
        session.rollback = Mock(side_effect=AssertionError("repository rollback"))
        append(session, p, expected)
        assert session.commit.call_count == session.rollback.call_count == 0


def test_schema_migration_rollback_and_app_db_rejection(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.sqlite'}")
    with engine.connect() as connection:
        migrate_empty_journal(connection)
        connection.rollback()
        assert not connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).all()
        migrate_empty_journal(connection)
        connection.commit()
        with pytest.raises(RuntimeError, match="JOURNAL_DATABASE_NOT_EMPTY"):
            migrate_empty_journal(connection)
    engine.dispose()
    with create_engine("sqlite://").begin() as connection:
        connection.exec_driver_sql("CREATE TABLE user_data(id INTEGER)")
        with pytest.raises(RuntimeError, match="JOURNAL_DATABASE_NOT_EMPTY"):
            migrate_empty_journal(connection)


@pytest.mark.parametrize("operation", ["read", "admit", "revalidate"])
def test_public_metadata_never_current_authority(operation):
    ports = UnavailableCurrentnessPorts()
    with pytest.raises(CurrentnessUnavailable):
        if operation == "read":
            ports.read_private_provisioning_witness()
        elif operation == "admit":
            ports.admit_with_private_ceremony_witness({"verified": True})
        else:
            ports.revalidate_private_currentness_witness({"status": "ACTIVE_ISSUANCE"})


def _process_attempt(url, previous, kind):
    engine = create_engine(url)
    p, expected = event(
        2, previous, kind, "root/test-1", None if kind == "REVOKE" else "root/test-2"
    )
    try:
        with Session(engine) as session, session.begin():
            append(session, p, expected)
        return "winner"
    except IntegrityError:
        return "stale"
    finally:
        engine.dispose()


def test_cross_process_same_head_cas(engine):
    previous = genesis(engine)
    with ProcessPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                _process_attempt,
                [str(engine.url)] * 2,
                [previous] * 2,
                ["NORMAL_ROTATION", "REVOKE"],
            )
        )
    assert sorted(results) == ["stale", "winner"]


@pytest.mark.parametrize("value", [0, -1, True, 9007199254740992])
def test_safe_integer_counter_bounds(value):
    p, expected = event()
    envelope = json.loads(wire(p))
    envelope["payload"]["revision"] = value
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(json.dumps(envelope).encode(), MANIFEST, expected=expected)


def test_manifest_order_count_and_exact_membership():
    p, expected = event()
    scopes = json.loads(MANIFEST)
    other = {**scopes[0], "installation_id": str(UUID(int=9))}
    for entries in ([other, scopes[0]], scopes * 4097, [other]):
        raw = rfc8785.dumps(entries)
        p["affected_scope_manifest_digest"] = digest(raw)
        with pytest.raises(LifecycleIntegrityError):
            verify_lifecycle_integrity(wire(p), raw, expected=expected)


def test_signer_order_and_external_redesignation_not_old_signature():
    p, expected = event(2, digest(b"previous"), "NORMAL_ROTATION", "root/test-1", "root/test-2")
    value = json.loads(wire(p))
    value["signatures"].reverse()
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(rfc8785.dumps(value), MANIFEST, expected=expected)
    p, expected = event(
        2, digest(b"previous"), "EXTERNAL_REDESIGNATION", "root/test-1", "root/test-2"
    )
    value = json.loads(wire(p))
    value["signatures"][0]["signer_key_id"] = "root/test-1"
    with pytest.raises(LifecycleIntegrityError):
        verify_lifecycle_integrity(rfc8785.dumps(value), MANIFEST, expected=expected)


def test_missing_identity_and_non_sqlite_schema(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'uninitialized.sqlite'}")
    with engine.begin() as connection:
        migrate_empty_journal(connection)
    with Session(engine) as session, pytest.raises(RuntimeError, match="JOURNAL_UNAVAILABLE"):
        JournalRepository(session).read_public_head()
    engine.dispose()
    connection = Mock()
    connection.dialect.name = "postgresql"
    with pytest.raises(RuntimeError, match="UNVERIFIED_JOURNAL_BACKEND"):
        migrate_empty_journal(connection)


def test_duplicate_identity_stale_hash_and_fingerprint_reuse(engine):
    previous = genesis(engine)
    with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
        JournalRepository(session).initialize_public_identity(JOURNAL)
    p, expected = event(2, digest(b"stale"), "NORMAL_ROTATION", "root/test-1", "root/test-2")
    with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
        append(session, p, expected)
    # Direct SQL cannot substitute a previously recorded fingerprint under a new ID.
    with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
        session.execute(
            text(
                "INSERT INTO deployment_journal_events "
                "SELECT :event,journal_id,2,:previous,:digest,'NORMAL_ROTATION',"
                "new_key_id,new_fingerprint,'root/alias',new_fingerprint,envelope "
                "FROM deployment_journal_events WHERE revision=1"
            ),
            {"event": str(UUID(int=999)), "previous": previous, "digest": digest(b"alias")},
        )


def test_history_terminal_taint_and_pin_rollback(engine):
    previous = genesis(engine)
    with Session(engine) as session:
        installed = JournalRepository(session).read_public_head()
    p, expected = event(2, previous, "REVOKE", "root/test-1", None)
    with Session(engine) as session, session.begin():
        previous = append(session, p, expected).event_digest
    p, expected = event(3, previous, "EXTERNAL_REDESIGNATION", "root/test-1", "root/test-2")
    with Session(engine) as session, session.begin():
        append(session, p, expected)
        repository = JournalRepository(session)
        history = repository.read_public_history()
        assert history[0].status == "REVOKED"
        assert history[0].tainted and history[0].invalidated_at_revision == 2
        assert history[1].status == "ACTIVE_ISSUANCE"
        with pytest.raises(RuntimeError, match="JOURNAL_PIN_MISMATCH"):
            repository.require_public_pin_match(installed)
        repository.require_public_pin_match(repository.read_public_head())
        # Matching public values still cannot pass the private currentness port.
        with pytest.raises(CurrentnessUnavailable):
            UnavailableCurrentnessPorts().revalidate_private_currentness_witness(
                repository.read_public_head()
            )


def test_history_detects_truncation_even_if_privileged_trigger_removal(engine):
    genesis(engine)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER deployment_journal_events_delete")
        connection.exec_driver_sql("DELETE FROM deployment_journal_events")
    with Session(engine) as session, pytest.raises(RuntimeError, match="JOURNAL_INCONSISTENT"):
        JournalRepository(session).read_public_history()


def test_null_event_identity_denied_at_database_boundary(engine):
    # SQLite TEXT PRIMARY KEY alone permits NULL; no reliance on Python UUID validation.
    p, expected = event()
    canonical = wire(p)
    with Session(engine) as session, pytest.raises(IntegrityError), session.begin():
        session.execute(
            text(
                "INSERT INTO deployment_journal_events VALUES "
                "(NULL,:journal,1,NULL,:digest,'GENESIS',NULL,NULL,:key,:fingerprint,:wire)"
            ),
            {
                "journal": JOURNAL,
                "digest": digest(canonical),
                "key": p["new_key_id"],
                "fingerprint": p["new_key_fingerprint"],
                "wire": canonical,
            },
        )
    with Session(engine) as session:
        assert JournalRepository(session).read_public_head().revision == 0
