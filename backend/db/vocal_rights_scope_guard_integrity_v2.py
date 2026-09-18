"""Frozen revision 0037 ScopeGuard insertion integrity, independent of PRAGMA.

REPLACE's implicit DELETE can bypass delete triggers. Reject conflicting INSERT
before SQLite resolves PK/UNIQUE conflicts, preserving even unreferenced anchors.
Do not change this version after merge; subsequent DDL needs another revision.
"""

import sqlalchemy as sa

TRIGGER_NAME = "vocal_rights_scope_guard_insert_unique_v2"
INSERT_INTEGRITY_DDL = f"""CREATE TRIGGER {TRIGGER_NAME}
BEFORE INSERT ON vocal_rights_scope_guards
WHEN EXISTS (SELECT 1 FROM vocal_rights_scope_guards g
WHERE g.scope_guard_id = NEW.scope_guard_id
OR (g.owner_id = NEW.owner_id AND g.workspace_id = NEW.workspace_id))
BEGIN SELECT RAISE(ABORT, 'AUTHORITY_CONFLICT'); END"""


def register_scope_guard_integrity(metadata: sa.MetaData) -> None:
    sa.event.listen(
        metadata.tables["vocal_rights_scope_guards"],
        "after_create",
        sa.DDL(INSERT_INTEGRITY_DDL).execute_if(dialect="sqlite"),
    )
