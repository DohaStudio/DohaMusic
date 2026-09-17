"""Add ADR-075 Vocal rights facts without any legacy backfill.

Versioned DDL is frozen separately from current ORM models; changing V1 is
forbidden after merge. This revision targets the tested SQLite engine only.
"""

import sqlalchemy as sa
from alembic import op

from backend.db.vocal_rights_schema_v1 import (
    TABLE_NAMES,
    begin_sqlite_ddl_transaction,
    define_tables,
    integrity_ddl,
)

revision = "20260918_0036"
down_revision = "20260911_0035"
branch_labels = None
depends_on = None


def _metadata() -> sa.MetaData:
    metadata = sa.MetaData()
    # Only FK target identities, never creation/alteration of existing tables.
    for name, key in (
        ("workspaces", "workspace_id"),
        ("asset_versions", "asset_version_id"),
        ("artifacts", "artifact_id"),
        ("jobs", "job_id"),
        ("job_outputs", "job_output_id"),
    ):
        sa.Table(name, metadata, sa.Column(key, sa.Uuid(), primary_key=True))
    define_tables(metadata)
    return metadata


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        raise RuntimeError("0036 requires a verified Vocal rights integrity backend")
    begin_sqlite_ddl_transaction(connection)
    metadata = _metadata()
    for name in TABLE_NAMES:
        metadata.tables[name].create(connection)
    for statement in integrity_ddl():
        connection.exec_driver_sql(statement)


def downgrade() -> None:
    connection = op.get_bind()
    begin_sqlite_ddl_transaction(connection)
    for name in TABLE_NAMES:
        if connection.scalar(sa.text(f"SELECT count(*) FROM {name}")):
            raise RuntimeError("0036 downgrade is blocked while Vocal rights audit facts exist")
    for name in reversed(TABLE_NAMES):
        op.drop_table(name)
