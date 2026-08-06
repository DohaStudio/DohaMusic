"""Database engine and session factory helpers."""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def create_database_engine(database_url: str) -> Engine:
    connect_args = (
        {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    )
    return create_engine(database_url, connect_args=connect_args, pool_pre_ping=True)


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_database_engine(database_url),
        autoflush=False,
        expire_on_commit=False,
    )
