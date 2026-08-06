from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import backend.models  # noqa: F401
from backend.db.base import Base
from backend.db.sqlite import (
    assert_sqlite_foreign_key_integrity,
    configure_sqlite_foreign_keys,
    set_sqlite_foreign_keys,
    verify_sqlite_foreign_keys,
)

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    configure_sqlite_foreign_keys(connectable)
    with connectable.connect() as connection:
        verify_sqlite_foreign_keys(connection)
        legacy_batch_compatibility = bool(
            config.attributes.get("allow_legacy_sqlite_batch_fk_bypass", False)
        )
        if legacy_batch_compatibility:
            set_sqlite_foreign_keys(connection, enabled=False)
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if legacy_batch_compatibility:
                set_sqlite_foreign_keys(connection, enabled=True)
                verify_sqlite_foreign_keys(connection)
                assert_sqlite_foreign_key_integrity(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
