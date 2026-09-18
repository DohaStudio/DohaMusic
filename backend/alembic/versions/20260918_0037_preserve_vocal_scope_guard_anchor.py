"""Add ScopeGuard INSERT protection without changing revision 0036 or facts."""

import sqlalchemy as sa
from alembic import op

from backend.db.vocal_rights_schema_v1 import begin_sqlite_ddl_transaction
from backend.db.vocal_rights_scope_guard_integrity_v2 import INSERT_INTEGRITY_DDL, TRIGGER_NAME

revision = "20260918_0037"
down_revision = "20260918_0036"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name != "sqlite":
        raise RuntimeError("0037 requires a verified Vocal rights integrity backend")
    begin_sqlite_ddl_transaction(connection)
    connection.exec_driver_sql(INSERT_INTEGRITY_DDL)


def downgrade() -> None:
    connection = op.get_bind()
    begin_sqlite_ddl_transaction(connection)
    if connection.scalar(sa.text("SELECT count(*) FROM vocal_rights_scope_guards")):
        raise RuntimeError("0037 downgrade is blocked while Vocal rights audit facts exist")
    connection.exec_driver_sql(f"DROP TRIGGER {TRIGGER_NAME}")
