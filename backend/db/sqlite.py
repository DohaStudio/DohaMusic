"""SQLite connection safety helpers shared by Runtime and Alembic."""

from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine


def _enable_foreign_keys(dbapi_connection: Any, _connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def configure_sqlite_foreign_keys(engine: Engine) -> Engine:
    """Enable FK enforcement on every connection of a SQLite engine."""

    if engine.dialect.name == "sqlite" and not event.contains(
        engine, "connect", _enable_foreign_keys
    ):
        event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def verify_sqlite_foreign_keys(connection: Connection) -> None:
    """Fail an online SQLite operation if FK enforcement is not active."""

    if connection.dialect.name != "sqlite":
        return
    cursor = connection.connection.dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys")
        row = cursor.fetchone()
    finally:
        cursor.close()
    enabled = row[0] if row is not None else 0
    if enabled != 1:
        raise RuntimeError("SQLite foreign key enforcement is not enabled")


def set_sqlite_foreign_keys(connection: Connection, *, enabled: bool) -> None:
    """Set FK enforcement for an explicit Alembic compatibility window."""

    if connection.dialect.name != "sqlite":
        return
    cursor = connection.connection.dbapi_connection.cursor()
    try:
        value = "ON" if enabled else "OFF"
        cursor.execute(f"PRAGMA foreign_keys={value}")
    finally:
        cursor.close()


def assert_sqlite_foreign_key_integrity(connection: Connection) -> None:
    """Fail if an explicit compatibility migration leaves FK violations."""

    if connection.dialect.name != "sqlite":
        return
    cursor = connection.connection.dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_key_check")
        violation = cursor.fetchone()
    finally:
        cursor.close()
    if violation is not None:
        raise RuntimeError("SQLite foreign key integrity check failed")
