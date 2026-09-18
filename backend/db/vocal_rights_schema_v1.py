"""Frozen ADR-075 persistence DDL for revision 0036.

Do not change this version after merge: future changes need a new migration and
schema version. No current model imports, actor policy, or authority decisions.
SQLite is the executable integrity target; other engines fail closed.
"""

from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

MAX_TOKEN = 9223372036854775807
PREFIX = "vocal_rights_"
TABLE_NAMES = (
    "vocal_rights_scope_guards",
    "vocal_rights_subjects",
    "vocal_rights_current_authorities",
    "vocal_rights_evidence",
    "vocal_rights_evidence_scopes",
    "vocal_rights_evidence_guards",
    "vocal_rights_evidence_withdrawals",
    "vocal_rights_grants",
    "vocal_rights_events",
    "vocal_completion_rights_receipts",
    "vocal_completion_rights_receipt_items",
)
IMMUTABLE_TABLES = (
    "vocal_rights_subjects",
    "vocal_rights_evidence",
    "vocal_rights_evidence_scopes",
    "vocal_rights_evidence_withdrawals",
    "vocal_rights_grants",
    "vocal_rights_events",
    "vocal_completion_rights_receipts",
    "vocal_completion_rights_receipt_items",
)


def _uuid(name: str, *, pk: bool = False, nullable: bool = False) -> sa.Column:
    return sa.Column(
        name,
        sa.Uuid(as_uuid=True),
        primary_key=pk,
        nullable=nullable,
        default=uuid4 if pk else None,
    )


def _fk(columns: list[str], targets: list[str], *, deferred: bool = False):
    return sa.ForeignKeyConstraint(
        columns,
        targets,
        ondelete="RESTRICT",
        deferrable=True if deferred else None,
        initially="DEFERRED" if deferred else None,
    )


def _created() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


def _token(name: str, *, initial: int = 0) -> sa.Column:
    return sa.Column(name, sa.BigInteger(), nullable=False, default=initial)


def _bounded(name: str, minimum: int = 0) -> sa.CheckConstraint:
    return sa.CheckConstraint(f"{name} BETWEEN {minimum} AND {MAX_TOKEN}")


def _audit_columns() -> list:
    # Opaque audit code, not an operation/role/policy decision vocabulary.
    return [
        _uuid("actor_id"),
        sa.Column("reason_code", sa.String(64), nullable=False),
        sa.CheckConstraint(
            "length(reason_code) BETWEEN 1 AND 64 AND reason_code NOT GLOB '*[^A-Z0-9_]*'"
        ),
        _created(),
    ]


def define_tables(metadata: sa.MetaData) -> dict[str, sa.Table]:
    """Define only new tables, with real legacy target FKs, without reflection."""
    tables: dict[str, sa.Table] = {}

    def table(name: str, *parts) -> sa.Table:
        result = sa.Table(name, metadata, *parts)
        tables[name] = result
        return result

    table(
        "vocal_rights_scope_guards",
        _uuid("scope_guard_id", pk=True),
        _uuid("owner_id"),
        _uuid("workspace_id"),
        _token("guard_epoch"),
        _created(),
        _fk(["workspace_id"], ["workspaces.workspace_id"]),
        sa.UniqueConstraint("owner_id", "workspace_id"),
        _bounded("guard_epoch"),
    )
    table(
        "vocal_rights_subjects",
        sa.Column("subject_type", sa.String(16), primary_key=True),
        _uuid("subject_id", pk=True),
        _uuid("workspace_id", nullable=True),
        _uuid("asset_version_id", nullable=True),
        _uuid("artifact_id", nullable=True),
        _fk(["workspace_id"], ["workspaces.workspace_id"]),
        _fk(["asset_version_id"], ["asset_versions.asset_version_id"]),
        _fk(["artifact_id"], ["artifacts.artifact_id"]),
        sa.CheckConstraint(
            "(subject_type = 'WORKSPACE' AND workspace_id = subject_id "
            "AND workspace_id IS NOT NULL AND asset_version_id IS NULL AND artifact_id IS NULL) OR "
            "(subject_type = 'ASSET_VERSION' AND asset_version_id = subject_id "
            "AND asset_version_id IS NOT NULL AND workspace_id IS NULL AND artifact_id IS NULL) OR "
            "(subject_type = 'ARTIFACT' AND artifact_id = subject_id "
            "AND artifact_id IS NOT NULL AND workspace_id IS NULL AND asset_version_id IS NULL)"
        ),
    )
    table(
        "vocal_rights_current_authorities",
        _uuid("authority_id", pk=True),
        _uuid("scope_guard_id"),
        sa.Column("subject_type", sa.String(16), nullable=False),
        _uuid("subject_id"),
        sa.Column("operation", sa.String(24), nullable=False),
        sa.Column("usage_role", sa.String(24), nullable=False),
        _token("semantic_revision"),
        _uuid("current_grant_id", nullable=True),
        _uuid("last_event_id", nullable=True),
        _created(),
        sa.UniqueConstraint(
            "scope_guard_id", "subject_type", "subject_id", "operation", "usage_role"
        ),
        _fk(["scope_guard_id"], ["vocal_rights_scope_guards.scope_guard_id"]),
        _fk(
            ["subject_type", "subject_id"],
            ["vocal_rights_subjects.subject_type", "vocal_rights_subjects.subject_id"],
        ),
        _fk(
            ["current_grant_id", "authority_id"],
            ["vocal_rights_grants.grant_id", "vocal_rights_grants.authority_id"],
        ),
        _fk(
            ["last_event_id", "authority_id", "semantic_revision"],
            [
                "vocal_rights_events.event_id",
                "vocal_rights_events.authority_id",
                "vocal_rights_events.semantic_revision",
            ],
        ),
        _bounded("semantic_revision"),
        sa.CheckConstraint(
            "(semantic_revision = 0 AND current_grant_id IS NULL AND last_event_id IS NULL) OR "
            "(semantic_revision > 0 AND last_event_id IS NOT NULL)"
        ),
        sa.CheckConstraint(
            "(operation = 'VOCAL_GENERATE' AND ((subject_type = 'WORKSPACE' "
            "AND usage_role = 'CREATE_OUTPUT') "
            "OR (subject_type = 'ARTIFACT' AND usage_role IN "
            "('LYRICS_REFERENCE','MELODY_REFERENCE','TIMING_REFERENCE','VOICE_REFERENCE')))) OR "
            "(operation = 'VOCAL_TRANSFORM' AND ((subject_type = 'ASSET_VERSION' "
            "AND usage_role IN ('SOURCE_VOCAL','PARENT_VOCAL')) OR "
            "(subject_type = 'ARTIFACT' AND usage_role = 'VOICE_REFERENCE'))) OR "
            "(operation IN ('VOCAL_CORRECT','VOCAL_ANALYZE') AND subject_type = 'ASSET_VERSION' "
            "AND usage_role IN ('SOURCE_VOCAL','PARENT_VOCAL')) OR "
            "(operation = 'OUTPUT_READ' AND subject_type = 'ARTIFACT' AND usage_role = 'OUTPUT')"
        ),
    )
    evidence = table(
        "vocal_rights_evidence",
        _uuid("evidence_id", pk=True),
        sa.Column("opaque_reference", sa.String(128), nullable=False, unique=True),
        sa.Column("digest_sha256", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        _uuid("rights_holder_id"),
        _uuid("verifier_id"),
        sa.Column("scope_count", sa.Integer(), nullable=False),
        _uuid("last_scope_authority_id"),
        sa.Column("last_scope_ordinal", sa.Integer(), nullable=False),
        _created(),
        sa.CheckConstraint("scope_count > 0 AND last_scope_ordinal = scope_count - 1"),
        _fk(
            ["evidence_id", "last_scope_authority_id", "last_scope_ordinal"],
            [
                "vocal_rights_evidence_scopes.evidence_id",
                "vocal_rights_evidence_scopes.authority_id",
                "vocal_rights_evidence_scopes.ordinal",
            ],
            deferred=True,
        ),
        sa.CheckConstraint(
            "length(opaque_reference) BETWEEN 1 AND 128 "
            "AND opaque_reference NOT GLOB '*[^A-Za-z0-9_.-]*'"
        ),
        sa.CheckConstraint("length(digest_sha256) = 64 AND digest_sha256 NOT GLOB '*[^0-9a-f]*'"),
        sa.CheckConstraint(
            "length(policy_version) BETWEEN 1 AND 64 "
            "AND policy_version NOT GLOB '*[^A-Za-z0-9_.-]*'"
        ),
        sa.UniqueConstraint("evidence_id", "digest_sha256", "policy_version"),
    )
    sa.Index("ix_vocal_rights_evidence_holder", evidence.c.rights_holder_id)
    table(
        "vocal_rights_evidence_scopes",
        _uuid("evidence_id", pk=True),
        _uuid("authority_id", pk=True),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.CheckConstraint("ordinal >= 0"),
        sa.UniqueConstraint("evidence_id", "ordinal"),
        sa.UniqueConstraint("evidence_id", "authority_id", "ordinal"),
        _fk(["evidence_id"], ["vocal_rights_evidence.evidence_id"]),
        _fk(["authority_id"], ["vocal_rights_current_authorities.authority_id"]),
    )
    sa.Index(
        "ix_vocal_rights_evidence_scopes_authority",
        tables["vocal_rights_evidence_scopes"].c.authority_id,
    )
    table(
        "vocal_rights_evidence_guards",
        _uuid("evidence_id", pk=True),
        _token("guard_epoch"),
        _uuid("withdrawal_event_id", nullable=True),
        _fk(["evidence_id"], ["vocal_rights_evidence.evidence_id"]),
        _fk(
            ["withdrawal_event_id", "evidence_id"],
            [
                "vocal_rights_evidence_withdrawals.withdrawal_event_id",
                "vocal_rights_evidence_withdrawals.evidence_id",
            ],
        ),
        _bounded("guard_epoch"),
    )
    table(
        "vocal_rights_evidence_withdrawals",
        _uuid("withdrawal_event_id", pk=True),
        _uuid("evidence_id"),
        *_audit_columns(),
        sa.UniqueConstraint("evidence_id"),
        sa.UniqueConstraint("withdrawal_event_id", "evidence_id"),
        _fk(["evidence_id"], ["vocal_rights_evidence.evidence_id"]),
    )
    grants = table(
        "vocal_rights_grants",
        _uuid("grant_id", pk=True),
        _uuid("authority_id"),
        _uuid("evidence_id"),
        _uuid("issuer_id"),
        _token("issued_revision", initial=1),
        _uuid("issuance_event_id"),
        sa.Column("idempotency_digest", sa.String(64), nullable=False),
        *_audit_columns(),
        _bounded("issued_revision", 1),
        sa.CheckConstraint(
            "length(idempotency_digest) = 64 AND idempotency_digest NOT GLOB '*[^0-9a-f]*'"
        ),
        sa.UniqueConstraint("grant_id", "authority_id"),
        sa.UniqueConstraint("grant_id", "authority_id", "evidence_id"),
        sa.UniqueConstraint("authority_id", "issued_revision"),
        sa.UniqueConstraint("authority_id", "idempotency_digest"),
        _fk(["authority_id"], ["vocal_rights_current_authorities.authority_id"]),
        _fk(
            ["evidence_id", "authority_id"],
            [
                "vocal_rights_evidence_scopes.evidence_id",
                "vocal_rights_evidence_scopes.authority_id",
            ],
        ),
        _fk(
            ["issuance_event_id", "authority_id", "issued_revision", "grant_id"],
            [
                "vocal_rights_events.event_id",
                "vocal_rights_events.authority_id",
                "vocal_rights_events.semantic_revision",
                "vocal_rights_events.new_grant_id",
            ],
            deferred=True,
        ),
    )
    sa.Index("ix_vocal_rights_grants_evidence", grants.c.evidence_id, grants.c.authority_id)
    table(
        "vocal_rights_events",
        _uuid("event_id", pk=True),
        _uuid("authority_id"),
        _token("semantic_revision", initial=1),
        sa.Column("transition", sa.String(16), nullable=False),
        _uuid("old_grant_id", nullable=True),
        _uuid("new_grant_id", nullable=True),
        *_audit_columns(),
        _bounded("semantic_revision", 1),
        sa.UniqueConstraint("authority_id", "semantic_revision"),
        sa.UniqueConstraint("event_id", "authority_id", "semantic_revision"),
        sa.UniqueConstraint("event_id", "authority_id", "semantic_revision", "new_grant_id"),
        sa.UniqueConstraint("old_grant_id"),
        sa.UniqueConstraint("new_grant_id"),
        _fk(["authority_id"], ["vocal_rights_current_authorities.authority_id"]),
        _fk(
            ["old_grant_id", "authority_id"],
            ["vocal_rights_grants.grant_id", "vocal_rights_grants.authority_id"],
        ),
        _fk(
            ["new_grant_id", "authority_id"],
            ["vocal_rights_grants.grant_id", "vocal_rights_grants.authority_id"],
        ),
        sa.CheckConstraint(
            "(transition = 'GRANTED' AND old_grant_id IS NULL AND new_grant_id IS NOT NULL) OR "
            "(transition = 'REVOKED' AND old_grant_id IS NOT NULL AND new_grant_id IS NULL) OR "
            "(transition = 'SUPERSEDED' AND old_grant_id IS NOT NULL AND new_grant_id IS NOT NULL "
            "AND old_grant_id != new_grant_id)"
        ),
    )
    receipts = table(
        "vocal_completion_rights_receipts",
        _uuid("receipt_id", pk=True),
        _uuid("job_id"),
        _uuid("job_output_id"),
        _uuid("artifact_id"),
        sa.Column("operation", sa.String(24), nullable=False),
        _uuid("actor_id"),
        _created(),
        sa.Column("item_count", sa.Integer(), nullable=False),
        _uuid("last_item_id"),
        sa.Column("last_ordinal", sa.Integer(), nullable=False),
        sa.UniqueConstraint("job_id"),
        sa.UniqueConstraint("job_output_id"),
        _fk(["job_id"], ["jobs.job_id"]),
        _fk(["job_output_id"], ["job_outputs.job_output_id"]),
        _fk(["artifact_id"], ["artifacts.artifact_id"]),
        _fk(
            ["last_item_id", "receipt_id", "last_ordinal"],
            [
                "vocal_completion_rights_receipt_items.item_id",
                "vocal_completion_rights_receipt_items.receipt_id",
                "vocal_completion_rights_receipt_items.ordinal",
            ],
            deferred=True,
        ),
        sa.CheckConstraint("item_count > 0 AND last_ordinal = item_count - 1"),
        sa.CheckConstraint(
            "operation IN ('VOCAL_GENERATE','VOCAL_TRANSFORM','VOCAL_CORRECT','VOCAL_ANALYZE')"
        ),
    )
    sa.Index("ix_vocal_completion_rights_receipts_artifact", receipts.c.artifact_id)
    table(
        "vocal_completion_rights_receipt_items",
        _uuid("item_id", pk=True),
        _uuid("receipt_id"),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        _uuid("authority_id"),
        _uuid("grant_id"),
        _token("semantic_revision", initial=1),
        _uuid("evidence_id"),
        sa.Column("digest_sha256", sa.String(64), nullable=False),
        sa.Column("policy_version", sa.String(64), nullable=False),
        sa.UniqueConstraint("receipt_id", "ordinal"),
        sa.UniqueConstraint("receipt_id", "authority_id"),
        sa.UniqueConstraint("item_id", "receipt_id", "ordinal"),
        _bounded("semantic_revision", 1),
        sa.CheckConstraint("ordinal >= 0"),
        _fk(["receipt_id"], ["vocal_completion_rights_receipts.receipt_id"]),
        _fk(
            ["grant_id", "authority_id", "evidence_id"],
            [
                "vocal_rights_grants.grant_id",
                "vocal_rights_grants.authority_id",
                "vocal_rights_grants.evidence_id",
            ],
        ),
        _fk(
            ["evidence_id", "digest_sha256", "policy_version"],
            [
                "vocal_rights_evidence.evidence_id",
                "vocal_rights_evidence.digest_sha256",
                "vocal_rights_evidence.policy_version",
            ],
        ),
    )
    return tables


def integrity_ddl() -> tuple[str, ...]:
    """Frozen SQLite checks supplement FK/UNIQUE/CHECK, including raw SQL."""
    statements: list[str] = []
    for table in IMMUTABLE_TABLES:
        for verb in ("UPDATE", "DELETE"):
            statements.append(
                f"CREATE TRIGGER {table}_immutable_{verb.lower()} BEFORE {verb} ON {table} "
                "BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END"
            )
    for table in (
        "vocal_rights_scope_guards",
        "vocal_rights_evidence_guards",
        "vocal_rights_current_authorities",
    ):
        statements.append(
            f"CREATE TRIGGER {table}_no_delete BEFORE DELETE ON {table} "
            "BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END"
        )
    statements.extend(
        (
            """CREATE TRIGGER vocal_rights_scope_initial BEFORE INSERT ON vocal_rights_scope_guards
            WHEN NEW.guard_epoch != 0 OR NOT EXISTS
            (SELECT 1 FROM workspaces w WHERE w.workspace_id = NEW.workspace_id
            AND w.owner_id = NEW.owner_id)
            BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_evidence_scope_closed
            BEFORE INSERT ON vocal_rights_evidence_scopes
            WHEN NOT EXISTS (SELECT 1 FROM vocal_rights_evidence e
            WHERE e.evidence_id = NEW.evidence_id AND NEW.ordinal < e.scope_count
            AND NEW.ordinal = (SELECT count(*) FROM vocal_rights_evidence_scopes s
            WHERE s.evidence_id = NEW.evidence_id))
            BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_evidence_guard_initial
            BEFORE INSERT ON vocal_rights_evidence_guards
            WHEN NEW.guard_epoch != 0 OR NEW.withdrawal_event_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_scope_guard_update
        BEFORE UPDATE ON vocal_rights_scope_guards
        WHEN NEW.scope_guard_id IS NOT OLD.scope_guard_id OR NEW.owner_id IS NOT OLD.owner_id
        OR NEW.workspace_id IS NOT OLD.workspace_id OR NEW.created_at IS NOT OLD.created_at
        OR NEW.guard_epoch != OLD.guard_epoch + 1
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_evidence_guard_update
        BEFORE UPDATE ON vocal_rights_evidence_guards
        WHEN NEW.evidence_id IS NOT OLD.evidence_id OR NEW.guard_epoch != OLD.guard_epoch + 1
        OR (NEW.withdrawal_event_id IS NOT OLD.withdrawal_event_id AND
            (OLD.withdrawal_event_id IS NOT NULL OR NOT EXISTS
            (SELECT 1 FROM vocal_rights_evidence_withdrawals w WHERE w.evidence_id = NEW.evidence_id
            AND w.withdrawal_event_id = NEW.withdrawal_event_id)))
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_current_initial
        BEFORE INSERT ON vocal_rights_current_authorities
        WHEN NEW.semantic_revision != 0 OR NEW.current_grant_id IS NOT NULL
        OR NEW.last_event_id IS NOT NULL
            BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_current_subject_scope
            BEFORE INSERT ON vocal_rights_current_authorities
            WHEN NOT EXISTS (SELECT 1 FROM vocal_rights_scope_guards sg
            JOIN workspaces w ON w.workspace_id = sg.workspace_id AND w.owner_id = sg.owner_id
            WHERE sg.scope_guard_id = NEW.scope_guard_id AND
            ((NEW.subject_type = 'WORKSPACE' AND NEW.subject_id = sg.workspace_id) OR
            (NEW.subject_type = 'ASSET_VERSION' AND EXISTS
                (SELECT 1 FROM asset_versions v JOIN assets a ON a.asset_id = v.asset_id
                WHERE v.asset_version_id = NEW.subject_id AND a.workspace_id = sg.workspace_id
                AND a.owner_id = sg.owner_id)) OR
            (NEW.subject_type = 'ARTIFACT' AND EXISTS
                (SELECT 1 FROM artifacts f JOIN asset_versions v
                ON v.asset_version_id = f.asset_version_id
                JOIN assets a ON a.asset_id = v.asset_id WHERE f.artifact_id = NEW.subject_id
                AND a.workspace_id = sg.workspace_id AND a.owner_id = sg.owner_id))))
            BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_current_update
        BEFORE UPDATE ON vocal_rights_current_authorities
        WHEN NEW.authority_id IS NOT OLD.authority_id
        OR NEW.scope_guard_id IS NOT OLD.scope_guard_id
        OR NEW.subject_type IS NOT OLD.subject_type OR NEW.subject_id IS NOT OLD.subject_id
        OR NEW.operation IS NOT OLD.operation OR NEW.usage_role IS NOT OLD.usage_role
        OR NEW.created_at IS NOT OLD.created_at
        OR NEW.semantic_revision != OLD.semantic_revision + 1
        OR NOT EXISTS (SELECT 1 FROM vocal_rights_events e WHERE e.event_id = NEW.last_event_id
        AND e.authority_id = NEW.authority_id AND e.semantic_revision = NEW.semantic_revision
        AND e.old_grant_id IS OLD.current_grant_id AND e.new_grant_id IS NEW.current_grant_id)
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_event_expected BEFORE INSERT ON vocal_rights_events
        WHEN NOT EXISTS (SELECT 1 FROM vocal_rights_current_authorities c
        WHERE c.authority_id = NEW.authority_id
        AND c.semantic_revision = NEW.semantic_revision - 1
        AND c.current_grant_id IS NEW.old_grant_id)
        OR (NEW.new_grant_id IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM vocal_rights_grants g JOIN vocal_rights_evidence_guards eg
        ON eg.evidence_id = g.evidence_id
        WHERE g.grant_id = NEW.new_grant_id AND g.authority_id = NEW.authority_id
        AND g.issued_revision = NEW.semantic_revision AND g.issuance_event_id = NEW.event_id
        AND eg.withdrawal_event_id IS NULL))
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_event_projection AFTER INSERT ON vocal_rights_events
        BEGIN UPDATE vocal_rights_current_authorities SET current_grant_id = NEW.new_grant_id,
        semantic_revision = NEW.semantic_revision, last_event_id = NEW.event_id
        WHERE authority_id = NEW.authority_id; END""",
            """CREATE TRIGGER vocal_rights_withdrawal_expected
        BEFORE INSERT ON vocal_rights_evidence_withdrawals
        WHEN NOT EXISTS (SELECT 1 FROM vocal_rights_evidence_guards eg
        WHERE eg.evidence_id = NEW.evidence_id
        AND eg.withdrawal_event_id IS NULL) OR EXISTS
        (SELECT 1 FROM vocal_rights_grants g JOIN vocal_rights_current_authorities c
        ON c.current_grant_id = g.grant_id WHERE g.evidence_id = NEW.evidence_id)
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_rights_withdrawal_projection
        AFTER INSERT ON vocal_rights_evidence_withdrawals
        BEGIN UPDATE vocal_rights_evidence_guards SET withdrawal_event_id = NEW.withdrawal_event_id,
        guard_epoch = guard_epoch + 1 WHERE evidence_id = NEW.evidence_id; END""",
            """CREATE TRIGGER vocal_completion_receipt_binding
        BEFORE INSERT ON vocal_completion_rights_receipts
        WHEN NOT EXISTS (SELECT 1 FROM job_outputs o JOIN jobs j ON j.job_id = o.job_id
        WHERE o.job_output_id = NEW.job_output_id AND o.job_id = NEW.job_id
        AND o.artifact_id = NEW.artifact_id AND o.output_order = 0 AND j.status = 'succeeded'
        AND ((j.job_type = 'vocal_generation' AND NEW.operation = 'VOCAL_GENERATE')
        OR (j.job_type = 'voice_conversion' AND NEW.operation = 'VOCAL_TRANSFORM')
        OR (j.job_type = 'vocal_correction' AND NEW.operation = 'VOCAL_CORRECT')
        OR (j.job_type = 'vocal_analysis' AND NEW.operation = 'VOCAL_ANALYZE')))
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
            """CREATE TRIGGER vocal_completion_receipt_item_binding
        BEFORE INSERT ON vocal_completion_rights_receipt_items
        WHEN NOT EXISTS (SELECT 1 FROM vocal_completion_rights_receipts r
        JOIN vocal_rights_current_authorities c ON c.authority_id = NEW.authority_id
        JOIN vocal_rights_grants g ON g.grant_id = c.current_grant_id
        JOIN vocal_rights_evidence_guards eg ON eg.evidence_id = g.evidence_id
        JOIN vocal_rights_scope_guards sg ON sg.scope_guard_id = c.scope_guard_id
        JOIN jobs j ON j.job_id = r.job_id AND j.workspace_id = sg.workspace_id
        JOIN workspaces w ON w.workspace_id = sg.workspace_id AND w.owner_id = sg.owner_id
        WHERE r.receipt_id = NEW.receipt_id AND c.operation = r.operation
        AND c.current_grant_id = NEW.grant_id AND c.semantic_revision = NEW.semantic_revision
        AND eg.withdrawal_event_id IS NULL AND NEW.ordinal < r.item_count
        AND NEW.ordinal = (SELECT count(*) FROM vocal_completion_rights_receipt_items i
        WHERE i.receipt_id = r.receipt_id))
        BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END""",
        )
    )
    return tuple(statements)


def begin_sqlite_ddl_transaction(connection) -> None:
    """Legacy sqlite3 DDL needs a physical Tx; caller still owns its end."""
    active = getattr(connection.connection.driver_connection, "in_transaction", None)
    if active is None:
        raise RuntimeError("Vocal rights requires a verified SQLite DDL transaction driver")
    if not active:
        connection.exec_driver_sql("BEGIN IMMEDIATE")


def register_integrity(metadata: sa.MetaData) -> None:
    def before_create(target, connection, *, tables, **kwargs):
        if connection.dialect.name == "sqlite" and any(
            table.name in TABLE_NAMES for table in tables
        ):
            begin_sqlite_ddl_transaction(connection)

    sa.event.listen(metadata, "before_create", before_create)
    for statement in integrity_ddl():
        target = statement.split(" ON ", 1)[1].split()[0]
        sa.event.listen(
            metadata.tables[target],
            "after_create",
            sa.DDL(
                statement.replace("CREATE TRIGGER ", "CREATE TRIGGER IF NOT EXISTS ", 1)
            ).execute_if(dialect="sqlite"),
        )
