"""CompositionSnapshot keyset query의 SQLite 실행 계획 검증."""

from __future__ import annotations

import sqlite3
from uuid import uuid4


SNAPSHOT_COUNT = 6_000


def _details(
    connection: sqlite3.Connection,
    sql: str,
    parameters: tuple[object, ...],
) -> list[str]:
    return [
        str(row[3])
        for row in connection.execute(
            f"EXPLAIN QUERY PLAN {sql}",
            parameters,
        )
    ]


def _assert_indexed(details: list[str], table: str) -> None:
    combined = " ".join(details).upper()
    assert f"SEARCH {table.upper()} USING" in combined
    assert "TEMP B-TREE" not in combined
    assert f"SCAN {table.upper()}" not in combined


def test_snapshot_and_item_queries_use_existing_indexes_without_temp_sort() -> None:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE composition_snapshots (
            composition_snapshot_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            snapshot_version INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(project_id, snapshot_version)
        );
        CREATE INDEX ix_composition_snapshots_project_created
            ON composition_snapshots(project_id, created_at);
        CREATE TABLE snapshot_items (
            snapshot_item_id TEXT PRIMARY KEY,
            composition_snapshot_id TEXT NOT NULL,
            asset_version_id TEXT NOT NULL,
            item_role TEXT NOT NULL,
            sort_order INTEGER NOT NULL,
            UNIQUE(composition_snapshot_id, item_role, sort_order),
            UNIQUE(composition_snapshot_id, asset_version_id, item_role)
        );
        """
    )
    project_id = str(uuid4())
    snapshots = [
        (str(uuid4()), project_id, version, "2026-08-10T00:00:00Z")
        for version in range(1, SNAPSHOT_COUNT + 1)
    ]
    connection.executemany(
        "INSERT INTO composition_snapshots VALUES (?, ?, ?, ?)", snapshots
    )
    snapshot_id = snapshots[-1][0]
    connection.executemany(
        "INSERT INTO snapshot_items VALUES (?, ?, ?, ?, ?)",
        [
            (str(uuid4()), snapshot_id, str(uuid4()), "stem", order)
            for order in range(SNAPSHOT_COUNT)
        ],
    )

    first_sql = """
        SELECT * FROM composition_snapshots
        WHERE project_id = ?
        ORDER BY snapshot_version DESC, composition_snapshot_id DESC
        LIMIT ?
    """
    next_sql = """
        SELECT * FROM composition_snapshots
        WHERE project_id = ?
          AND (snapshot_version < ? OR
               (snapshot_version = ? AND composition_snapshot_id < ?))
        ORDER BY snapshot_version DESC, composition_snapshot_id DESC
        LIMIT ?
    """
    item_sql = """
        SELECT * FROM snapshot_items
        WHERE composition_snapshot_id = ?
        ORDER BY item_role ASC, sort_order ASC, snapshot_item_id ASC
        LIMIT ?
    """
    _assert_indexed(
        _details(connection, first_sql, (project_id, 101)),
        "composition_snapshots",
    )
    _assert_indexed(
        _details(
            connection,
            next_sql,
            (project_id, 5_000, 5_000, str(uuid4()), 101),
        ),
        "composition_snapshots",
    )
    _assert_indexed(
        _details(connection, item_sql, (snapshot_id, 101)),
        "snapshot_items",
    )

    seen: list[int] = []
    last_version: int | None = None
    last_id: str | None = None
    while True:
        if last_version is None:
            rows = connection.execute(first_sql, (project_id, 127)).fetchall()
        else:
            rows = connection.execute(
                next_sql,
                (project_id, last_version, last_version, last_id, 127),
            ).fetchall()
        if not rows:
            break
        seen.extend(int(row[2]) for row in rows)
        last_id, last_version = str(rows[-1][0]), int(rows[-1][2])

    assert seen == list(range(SNAPSHOT_COUNT, 0, -1))
    assert len(seen) == len(set(seen))
    connection.close()
