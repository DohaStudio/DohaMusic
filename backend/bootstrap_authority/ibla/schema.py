"""Separate SQLite schemas; not application metadata/Alembic or journal schema."""

import re

from sqlalchemy import text

from backend.bootstrap_authority.ibla.codec import binding_wire
from backend.bootstrap_authority.ibla.contracts import IblaInconsistent

VERSION = 1


def objects(role):
    if role not in {"L", "H"}:
        raise ValueError("ROLE")
    kinds = (
        "'COMMISSION','HISTORY_BLOCK','RETIRE'"
        if role == "L"
        else ("'COMMISSIONING_PENDING','PREPARED','CONFIRMED','UNCERTAIN'")
    )
    uniqueness = "UNIQUE(operation_id)" if role == "L" else "UNIQUE(operation_id,kind)"
    operation_duplicate = "operation_id=NEW.operation_id" + (
        " AND kind=NEW.kind" if role == "H" else ""
    )
    ddl = [
        f"""CREATE TABLE ibla_identity (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            version INTEGER NOT NULL CHECK(version=1),
            role TEXT NOT NULL CHECK(role='{role}'),
            binding BLOB NOT NULL CHECK(typeof(binding)='blob' AND length(binding)<=16384))""",
        """CREATE TABLE ibla_head (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1),
            revision INTEGER NOT NULL CHECK(typeof(revision)='integer'
                AND revision BETWEEN 0 AND 9007199254740991),
            digest TEXT, CHECK((revision=0 AND digest IS NULL)
                OR (revision>0 AND digest IS NOT NULL)))""",
        f"""CREATE TABLE ibla_events (
            revision INTEGER PRIMARY KEY CHECK(typeof(revision)='integer'
                AND revision BETWEEN 1 AND 9007199254740991),
            record_id TEXT NOT NULL UNIQUE, operation_id TEXT NOT NULL,
            fingerprint TEXT NOT NULL, previous_digest TEXT, digest TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL CHECK(kind IN ({kinds})),
            envelope BLOB NOT NULL CHECK(typeof(envelope)='blob' AND length(envelope)<=16384),
            {uniqueness})""",
        f"""CREATE TRIGGER ibla_events_insert BEFORE INSERT ON ibla_events
            WHEN EXISTS(SELECT 1 FROM ibla_events WHERE revision=NEW.revision
                OR record_id=NEW.record_id OR digest=NEW.digest OR ({operation_duplicate}))
            OR NOT EXISTS(SELECT 1 FROM ibla_head WHERE revision=NEW.revision-1
                AND digest IS NEW.previous_digest)
            BEGIN SELECT RAISE(ABORT,'IBLA_CONFLICT'); END""",
        """CREATE TRIGGER ibla_head_update BEFORE UPDATE ON ibla_head
            WHEN NEW.singleton!=OLD.singleton OR NEW.revision!=OLD.revision+1
            OR NOT EXISTS(SELECT 1 FROM ibla_events WHERE revision=NEW.revision
                AND previous_digest IS OLD.digest AND digest=NEW.digest)
            BEGIN SELECT RAISE(ABORT,'IBLA_CONFLICT'); END""",
        """CREATE TRIGGER ibla_events_advance AFTER INSERT ON ibla_events
            BEGIN UPDATE ibla_head SET revision=NEW.revision,digest=NEW.digest
                WHERE revision=NEW.revision-1 AND digest IS NEW.previous_digest;
                SELECT CASE WHEN changes()!=1 THEN RAISE(ABORT,'IBLA_CONFLICT') END;
            END""",
    ]
    for table in ("ibla_identity", "ibla_events", "ibla_head"):
        operations = ("UPDATE", "DELETE") if table != "ibla_head" else ("DELETE",)
        for operation in operations:
            ddl.append(
                f"CREATE TRIGGER {table}_{operation.lower()} BEFORE {operation} ON {table} "
                "BEGIN SELECT RAISE(ABORT,'IBLA_IMMUTABLE'); END"
            )
    for table in ("ibla_identity", "ibla_head"):
        ddl.append(
            f"CREATE TRIGGER {table}_insert BEFORE INSERT ON {table} "
            "BEGIN SELECT RAISE(ABORT,'IBLA_IMMUTABLE'); END"
        )
    # Explicit H index supports operation replay across multiple control states.
    if role == "H":
        ddl.append("CREATE INDEX ibla_operation ON ibla_events(operation_id,revision)")
    return tuple(ddl)


def install_empty_store(connection, *, role, binding):
    """Explicit PUBLIC fixture/setup mechanics, NOT commissioned authority.

    Caller must own/commit an isolated connection transaction. Runtime never calls
    this helper. No implicit file creation, backfill, upgrade, reset or downgrade.
    """
    wire = binding_wire(binding)
    ddl = objects(role)
    if (
        connection.dialect.name != "sqlite"
        or connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"
        ).first()
    ):
        raise IblaInconsistent()
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN")
    for sql in ddl[:3]:
        connection.exec_driver_sql(sql)
    connection.execute(
        text("INSERT INTO ibla_identity VALUES(1,1,:role,:binding)"),
        {"role": role, "binding": wire},
    )
    connection.exec_driver_sql("INSERT INTO ibla_head VALUES(1,0,NULL)")
    for sql in ddl[3:]:
        connection.exec_driver_sql(sql)


def require_schema(session, role, binding):
    def normalize(value):
        return " ".join(value.split())

    expected = {}
    for sql in objects(role):
        kind, name = re.match(r"CREATE (TABLE|TRIGGER|INDEX) (\w+)", sql).groups()
        expected[(kind.lower(), name)] = normalize(sql)
    actual = {
        (r[0], r[1]): normalize(r[2])
        for r in session.execute(
            text("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
        )
    }
    identity = session.execute(text("SELECT * FROM ibla_identity")).all()
    if actual != expected or identity != [(1, VERSION, role, binding_wire(binding))]:
        raise IblaInconsistent()
    if session.execute(text("PRAGMA integrity_check")).all() != [("ok",)]:
        raise IblaInconsistent()
