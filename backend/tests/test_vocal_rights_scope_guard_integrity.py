"""Default SQLite direct-SQL REPLACE/epoch regression, fixture-only."""

from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, OperationalError

from backend.core.vocal_rights import (
    VocalRightsOperation,
    VocalRightsPersistenceError,
    VocalRightsSubjectType,
    VocalRightsUsageRole,
)
from backend.db import vocal_rights_scope_guard_integrity_v2
from backend.db.base import Base
from backend.db.session import create_database_engine, create_session_factory
from backend.db.vocal_rights_scope_guard_integrity_v2 import TRIGGER_NAME
from backend.models.workspace import Workspace
from backend.repositories.workspace.vocal_rights_repository import VocalRightsRepository
from backend.tests.test_vocal_rights_migration import config, snapshot

PARENT = "20260918_0036"
REVISION = "20260918_0037"
GUARD_SNAPSHOT = "SELECT * FROM vocal_rights_scope_guards"
INSERT_COLUMNS = "(scope_guard_id,owner_id,workspace_id,guard_epoch,created_at)"
INSERT_FACTS = (
    "SELECT :replacement,owner_id,workspace_id,0,created_at FROM vocal_rights_scope_guards WHERE 1"
)


def seed_empty_guard(factory):
    with factory.begin() as session:
        workspace = Workspace(
            owner_id=uuid4(), name="Synthetic empty anchor", lifecycle_status="active"
        )
        session.add(workspace)
        session.flush()
        guard = VocalRightsRepository(session).ensure_scope_guard(
            workspace.owner_id, workspace.workspace_id
        )
        assert guard.guard_epoch == 0
        return dict(
            owner=workspace.owner_id, workspace=workspace.workspace_id, guard=guard.scope_guard_id
        )


@pytest.fixture(params=("metadata", "migration"))
def empty_guard(tmp_path, request):
    url = f"sqlite:///{(tmp_path / 'anchor.db').as_posix()}"
    engine = create_database_engine(url)
    if request.param == "metadata":
        Base.metadata.create_all(engine)
    else:
        command.upgrade(config(url), "head")
    factory = create_session_factory(url)
    graph = seed_empty_guard(factory)
    graph.update(engine=engine, factory=factory)
    yield graph
    factory.kw["bind"].dispose()
    engine.dispose()


def first_cas(graph):
    with graph["factory"].begin() as session:
        guard = VocalRightsRepository(session).conditional_guard_update("scope", graph["guard"], 0)
        assert guard.guard_epoch == 1


def assert_stale_then_normal_cas(graph):
    with (
        pytest.raises(VocalRightsPersistenceError, match="AUTHORITY_CONFLICT"),
        graph["factory"].begin() as session,
    ):
        VocalRightsRepository(session).conditional_guard_update("scope", graph["guard"], 0)
    with graph["factory"].begin() as session:
        repository = VocalRightsRepository(session)
        guard = repository.ensure_scope_guard(graph["owner"], graph["workspace"])
        assert guard.scope_guard_id == graph["guard"]
        assert guard.guard_epoch == 1
        assert repository.conditional_guard_update("scope", graph["guard"], 1).guard_epoch == 2


def test_default_pragmas_empty_anchor_and_normal_cas(empty_guard):
    graph = empty_guard
    with graph["engine"].connect() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert connection.scalar(text("PRAGMA recursive_triggers")) == 0
        assert connection.scalar(text("SELECT guard_epoch FROM vocal_rights_scope_guards")) == 0
    first_cas(graph)
    assert_stale_then_normal_cas(graph)


@pytest.mark.parametrize("insert_kind", ("INSERT OR REPLACE", "REPLACE"))
@pytest.mark.parametrize("same_id", (True, False))
def test_direct_replace_cannot_reset_or_replace_unreferenced_anchor(
    empty_guard, insert_kind, same_id
):
    graph = empty_guard
    first_cas(graph)
    with graph["engine"].begin() as connection:
        assert connection.scalar(text("PRAGMA foreign_keys")) == 1
        assert connection.scalar(text("PRAGMA recursive_triggers")) == 0
        assert connection.scalar(text("SELECT count(*) FROM vocal_rights_current_authorities")) == 0
        before = connection.execute(text(GUARD_SNAPSHOT)).all()
        replacement = graph["guard"] if same_id else uuid4()
        with pytest.raises(IntegrityError, match="AUTHORITY_CONFLICT"):
            connection.execute(
                text(
                    f"{insert_kind} INTO vocal_rights_scope_guards {INSERT_COLUMNS} {INSERT_FACTS}"
                ),
                {"replacement": replacement.hex},
            )
        assert connection.execute(text(GUARD_SNAPSHOT)).all() == before
        assert not connection.execute(text("PRAGMA foreign_key_check")).all()
    assert_stale_then_normal_cas(graph)


@pytest.mark.parametrize(
    "statement",
    (
        "UPDATE OR REPLACE vocal_rights_scope_guards SET guard_epoch=0",
        f"INSERT OR IGNORE INTO vocal_rights_scope_guards {INSERT_COLUMNS} {INSERT_FACTS}",
        f"INSERT INTO vocal_rights_scope_guards {INSERT_COLUMNS} {INSERT_FACTS} "
        "ON CONFLICT(scope_guard_id) DO UPDATE SET guard_epoch=0",
    ),
)
def test_other_conflict_syntax_cannot_bypass_anchor_integrity(empty_guard, statement):
    graph = empty_guard
    first_cas(graph)
    with graph["engine"].begin() as connection:
        before = connection.execute(text(GUARD_SNAPSHOT)).all()
        with pytest.raises(IntegrityError, match="AUTHORITY_CONFLICT"):
            connection.execute(text(statement), {"replacement": graph["guard"].hex})
        assert connection.execute(text(GUARD_SNAPSHOT)).all() == before
    assert_stale_then_normal_cas(graph)


def test_caller_rollback_preserves_anchor_and_removes_partial_authority(empty_guard):
    graph = empty_guard
    first_cas(graph)
    with (
        pytest.raises(IntegrityError, match="AUTHORITY_CONFLICT"),
        graph["factory"].begin() as session,
    ):
        repository = VocalRightsRepository(session)
        repository.conditional_guard_update("scope", graph["guard"], 1)
        repository.ensure_current_authority(
            graph["guard"],
            VocalRightsSubjectType.WORKSPACE,
            graph["workspace"],
            VocalRightsOperation.VOCAL_GENERATE,
            VocalRightsUsageRole.CREATE_OUTPUT,
        )
        session.execute(
            text(
                f"INSERT OR REPLACE INTO vocal_rights_scope_guards {INSERT_COLUMNS} {INSERT_FACTS}"
            ),
            {"replacement": graph["guard"].hex},
        )
    with graph["engine"].connect() as connection:
        for table in ("subjects", "current_authorities", "grants", "events"):
            assert connection.scalar(text(f"SELECT count(*) FROM vocal_rights_{table}")) == 0
        assert connection.scalar(text("SELECT guard_epoch FROM vocal_rights_scope_guards")) == 1
    assert_stale_then_normal_cas(graph)


def test_followup_upgrade_preserves_existing_guard_and_every_fact(tmp_path):
    url = f"sqlite:///{(tmp_path / 'existing-anchor.db').as_posix()}"
    command.upgrade(config(url), PARENT)
    engine = create_database_engine(url)
    factory = create_session_factory(url)
    graph = seed_empty_guard(factory)
    graph.update(engine=engine, factory=factory)
    first_cas(graph)
    tables = set(Base.metadata.tables)
    before = snapshot(engine, tables)
    command.upgrade(config(url), "head")
    assert snapshot(engine, tables) == before
    with engine.begin() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
        assert connection.scalar(text("PRAGMA recursive_triggers")) == 0
        with pytest.raises(IntegrityError, match="AUTHORITY_CONFLICT"):
            connection.execute(
                text(
                    "INSERT OR REPLACE INTO vocal_rights_scope_guards "
                    f"{INSERT_COLUMNS} {INSERT_FACTS}"
                ),
                {"replacement": uuid4().hex},
            )
    assert snapshot(engine, tables) == before
    with pytest.raises(RuntimeError, match="audit facts exist"):
        command.downgrade(config(url), PARENT)
    assert snapshot(engine, tables) == before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == REVISION
    assert_stale_then_normal_cas(graph)
    factory.kw["bind"].dispose()
    engine.dispose()


def test_followup_ddl_failure_preserves_parent_head_and_existing_anchor(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'ddl-failure.db').as_posix()}"
    command.upgrade(config(url), PARENT)
    engine = create_database_engine(url)
    factory = create_session_factory(url)
    graph = seed_empty_guard(factory)
    graph.update(engine=engine, factory=factory)
    first_cas(graph)
    before = snapshot(engine, set(Base.metadata.tables))
    monkeypatch.setattr(
        vocal_rights_scope_guard_integrity_v2, "INSERT_INTEGRITY_DDL", "INVALID DDL"
    )
    with pytest.raises(OperationalError):
        command.upgrade(config(url), "head")
    assert snapshot(engine, set(Base.metadata.tables)) == before
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == PARENT
        assert (
            connection.scalar(
                text("SELECT count(*) FROM sqlite_master WHERE type='trigger' AND name=:name"),
                {"name": TRIGGER_NAME},
            )
            == 0
        )
    factory.kw["bind"].dispose()
    engine.dispose()
