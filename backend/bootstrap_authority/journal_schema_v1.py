"""Independent SQLite public journal schema v1, never application DB metadata.

Explicit caller connection migration only. No startup provisioning/default path.
DDL is transactional; downgrade/truncation is intentionally not exposed.
"""

from __future__ import annotations

from sqlalchemy import Connection

SCHEMA_VERSION = 1
DDL = (
    "CREATE TABLE deployment_journal_schema (version INTEGER PRIMARY KEY CHECK(version=1))",
    "INSERT INTO deployment_journal_schema VALUES (1)",
    """CREATE TABLE deployment_journal_guard (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), journal_id TEXT NOT NULL UNIQUE,
        revision INTEGER NOT NULL DEFAULT 0 CHECK(typeof(revision)='integer'
            AND revision BETWEEN 0 AND 9007199254740991),
        trust_revision INTEGER NOT NULL DEFAULT 0 CHECK(trust_revision=revision),
        head_digest TEXT, current_key_id TEXT, last_key_id TEXT,
        CHECK((revision=0 AND head_digest IS NULL AND current_key_id IS NULL
            AND last_key_id IS NULL) OR (revision>0 AND head_digest IS NOT NULL
            AND last_key_id IS NOT NULL)))""",
    """CREATE TABLE deployment_journal_events (
        event_id TEXT PRIMARY KEY NOT NULL, journal_id TEXT NOT NULL,
        revision INTEGER NOT NULL UNIQUE CHECK(typeof(revision)='integer'
            AND revision BETWEEN 1 AND 9007199254740991),
        previous_digest TEXT, event_digest TEXT NOT NULL UNIQUE,
        kind TEXT NOT NULL CHECK(kind IN
            ('GENESIS','NORMAL_ROTATION','REVOKE','EXTERNAL_REDESIGNATION')),
        old_key_id TEXT, old_fingerprint TEXT,
        new_key_id TEXT UNIQUE, new_fingerprint TEXT UNIQUE,
        envelope BLOB NOT NULL CHECK(typeof(envelope)='blob' AND length(envelope)<=16384),
        CHECK((kind='GENESIS' AND old_key_id IS NULL AND old_fingerprint IS NULL
            AND previous_digest IS NULL AND revision=1) OR
            (kind!='GENESIS' AND old_key_id IS NOT NULL AND old_fingerprint IS NOT NULL
            AND previous_digest IS NOT NULL AND revision>1)),
        CHECK((kind='REVOKE' AND new_key_id IS NULL AND new_fingerprint IS NULL) OR
            (kind!='REVOKE' AND new_key_id IS NOT NULL AND new_fingerprint IS NOT NULL)),
        CHECK(old_key_id IS NULL OR new_key_id IS NULL OR
            (old_key_id!=new_key_id AND old_fingerprint!=new_fingerprint)))""",
    """CREATE TRIGGER deployment_journal_guard_insert BEFORE INSERT ON deployment_journal_guard
        WHEN EXISTS(SELECT 1 FROM deployment_journal_guard)
        OR NEW.revision!=0 OR NEW.trust_revision!=0
        BEGIN SELECT RAISE(ABORT,'JOURNAL_CONFLICT'); END""",
    """CREATE TRIGGER deployment_journal_guard_update BEFORE UPDATE ON deployment_journal_guard
        WHEN NEW.singleton!=OLD.singleton OR NEW.journal_id!=OLD.journal_id
        OR NEW.revision!=OLD.revision+1 OR NEW.trust_revision!=OLD.trust_revision+1
        OR NOT EXISTS(SELECT 1 FROM deployment_journal_events e
            WHERE e.revision=NEW.revision AND e.journal_id=OLD.journal_id
            AND e.previous_digest IS OLD.head_digest AND e.event_digest=NEW.head_digest
            AND NEW.current_key_id IS e.new_key_id
            AND NEW.last_key_id IS coalesce(e.new_key_id,OLD.last_key_id))
        BEGIN SELECT RAISE(ABORT,'JOURNAL_CONFLICT'); END""",
    """CREATE TRIGGER deployment_journal_event_insert BEFORE INSERT ON deployment_journal_events
        WHEN EXISTS(SELECT 1 FROM deployment_journal_events e WHERE e.event_id=NEW.event_id
            OR e.revision=NEW.revision OR e.event_digest=NEW.event_digest
            OR (NEW.new_key_id IS NOT NULL AND (e.new_key_id=NEW.new_key_id
                OR e.new_fingerprint=NEW.new_fingerprint)))
        OR NOT EXISTS(SELECT 1 FROM deployment_journal_guard g
            WHERE g.journal_id=NEW.journal_id AND NEW.revision=g.revision+1
            AND NEW.previous_digest IS g.head_digest
            AND ((NEW.kind='GENESIS' AND g.revision=0) OR
                (NEW.kind!='GENESIS' AND NEW.old_key_id=g.last_key_id
                AND EXISTS(SELECT 1 FROM deployment_journal_events k
                    WHERE k.new_key_id=NEW.old_key_id AND k.new_fingerprint=NEW.old_fingerprint)
                AND (NEW.kind='EXTERNAL_REDESIGNATION' OR g.current_key_id=NEW.old_key_id))))
        BEGIN SELECT RAISE(ABORT,'JOURNAL_CONFLICT'); END""",
    """CREATE TRIGGER deployment_journal_event_advance AFTER INSERT ON deployment_journal_events
        BEGIN UPDATE deployment_journal_guard SET revision=NEW.revision,
            trust_revision=NEW.revision, head_digest=NEW.event_digest,
            current_key_id=NEW.new_key_id, last_key_id=coalesce(NEW.new_key_id,last_key_id)
            WHERE journal_id=NEW.journal_id AND revision=NEW.revision-1
            AND trust_revision=NEW.revision-1 AND head_digest IS NEW.previous_digest;
            SELECT CASE WHEN changes()!=1 THEN RAISE(ABORT,'JOURNAL_CONFLICT') END;
        END""",
)


def migrate_empty_journal(connection: Connection) -> None:
    """Schema installation is NOT journal identity initialization/admission.

    A caller must explicitly commit its independent-store transaction. Reject any
    nonempty database, including application DBs; no authority backfill/auto-upgrade.
    """
    if connection.dialect.name != "sqlite":
        raise RuntimeError("UNVERIFIED_JOURNAL_BACKEND")
    if connection.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).first():
        raise RuntimeError("JOURNAL_DATABASE_NOT_EMPTY")
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
    for statement in DDL:
        connection.exec_driver_sql(statement)
    for table in ("deployment_journal_schema", "deployment_journal_events"):
        for operation in ("UPDATE", "DELETE"):
            connection.exec_driver_sql(
                f"CREATE TRIGGER {table}_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_JOURNAL'); END"
            )
    connection.exec_driver_sql(
        "CREATE TRIGGER deployment_journal_schema_insert "
        "BEFORE INSERT ON deployment_journal_schema "
        "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_JOURNAL'); END"
    )
    connection.exec_driver_sql(
        "CREATE TRIGGER deployment_journal_guard_delete BEFORE DELETE ON deployment_journal_guard "
        "BEGIN SELECT RAISE(ABORT,'IMMUTABLE_JOURNAL'); END"
    )
