"""Workspace Job HMAC cursor와 Owner scope keyset page 계약 검증."""

from __future__ import annotations

import base64
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker

import backend.models  # noqa: F401
from backend.core.cursor_pagination import CURSOR_SORT, CursorCodec, filter_fingerprint
from backend.core.exceptions import (
    ApplicationValidationError,
    CursorConfigurationError,
    InvalidCursorError,
    InvalidLimitError,
    ResourceNotFoundError,
)
from backend.db.base import Base
from backend.db.session import create_database_engine
from backend.models.workspace import Job, JobStatus, MusicProject, Workspace
from backend.repositories.workspace import JobRepository
from backend.repositories.workspace.job_repository import (
    _build_list_jobs_after_statement,
)
from backend.services.workspace import JobService

TEST_KEY = "job-cursor-signing-key-with-at-least-32-bytes"
CREATED_AT = datetime(2026, 8, 10, 12, 0, tzinfo=UTC)


def _id(namespace: int, value: int) -> UUID:
    return UUID(f"{namespace:02x}{value:030x}")


def _workspace(owner_id: UUID, identifier: int) -> Workspace:
    return Workspace(
        workspace_id=_id(2, identifier),
        owner_id=owner_id,
        name=f"Workspace {identifier}",
        lifecycle_status="active",
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _project(workspace_id: UUID, identifier: int) -> MusicProject:
    return MusicProject(
        project_id=_id(3, identifier),
        workspace_id=workspace_id,
        title=f"Project {identifier}",
        lifecycle_status="active",
        created_by=_id(4, identifier),
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


def _job(
    workspace_id: UUID | None,
    project_id: UUID,
    identifier: int,
    *,
    status: JobStatus,
    job_type: str,
    created_at: datetime,
) -> Job:
    return Job(
        job_id=_id(5, identifier),
        workspace_id=workspace_id,
        project_id=project_id,
        job_type=job_type,
        status=status,
        api_contract_version="1.0",
        settings_snapshot={},
        requested_by=_id(6, identifier),
        created_at=created_at,
    )


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'job-cursor.db').as_posix()}"
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    assert engine.pool.checkedout() == 0
    engine.dispose()


def _seed_pages(session_factory):
    owner_id = _id(1, 1)
    other_owner_id = _id(1, 2)
    first_workspace = _workspace(owner_id, 1)
    second_workspace = _workspace(owner_id, 2)
    other_workspace = _workspace(other_owner_id, 3)
    first_project = _project(first_workspace.workspace_id, 1)
    second_project = _project(first_workspace.workspace_id, 2)
    outside_project = _project(second_workspace.workspace_id, 3)
    other_project = _project(other_workspace.workspace_id, 4)
    jobs = [
        _job(
            first_workspace.workspace_id,
            first_project.project_id,
            1,
            status=JobStatus.QUEUED,
            job_type="mix",
            created_at=CREATED_AT,
        ),
        _job(
            first_workspace.workspace_id,
            first_project.project_id,
            2,
            status=JobStatus.QUEUED,
            job_type="mix",
            created_at=CREATED_AT,
        ),
        _job(
            first_workspace.workspace_id,
            first_project.project_id,
            3,
            status=JobStatus.QUEUED,
            job_type="mix",
            created_at=CREATED_AT - timedelta(minutes=1),
        ),
        _job(
            first_workspace.workspace_id,
            first_project.project_id,
            4,
            status=JobStatus.RUNNING,
            job_type="export",
            created_at=CREATED_AT - timedelta(minutes=2),
        ),
        _job(
            first_workspace.workspace_id,
            second_project.project_id,
            5,
            status=JobStatus.FAILED,
            job_type="audio_analysis",
            created_at=CREATED_AT - timedelta(minutes=3),
        ),
        _job(
            second_workspace.workspace_id,
            outside_project.project_id,
            6,
            status=JobStatus.QUEUED,
            job_type="mix",
            created_at=CREATED_AT + timedelta(minutes=1),
        ),
        _job(
            other_workspace.workspace_id,
            other_project.project_id,
            7,
            status=JobStatus.QUEUED,
            job_type="mix",
            created_at=CREATED_AT + timedelta(minutes=2),
        ),
        _job(
            None,
            first_project.project_id,
            8,
            status=JobStatus.QUEUED,
            job_type="mix",
            created_at=CREATED_AT + timedelta(minutes=3),
        ),
    ]
    with session_factory.begin() as session:
        session.add_all(
            [
                first_workspace,
                second_workspace,
                other_workspace,
                first_project,
                second_project,
                outside_project,
                other_project,
                *jobs,
            ]
        )
    return {
        "owner_id": owner_id,
        "other_owner_id": other_owner_id,
        "first_workspace": first_workspace,
        "second_workspace": second_workspace,
        "other_workspace": other_workspace,
        "first_project": first_project,
        "second_project": second_project,
        "other_project": other_project,
        "jobs": jobs,
    }


def _job_filter(
    *,
    owner_id: UUID,
    workspace_id: UUID,
    project_id: UUID | None = None,
    status: JobStatus | None = None,
    job_type: str | None = None,
) -> str:
    return filter_fingerprint(
        {
            "effective_owner_id": str(owner_id),
            "job_type": job_type,
            "project_id": str(project_id) if project_id is not None else None,
            "sort": CURSOR_SORT,
            "status": status.value if status is not None else None,
            "workspace_id": str(workspace_id),
        }
    )


def _decode_payload(token: str) -> dict[str, object]:
    payload_part = token.split(".", maxsplit=1)[0]
    padding = "=" * (-len(payload_part) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_part + padding))


def test_job_cursor_uses_created_at_v1_payload() -> None:
    codec = CursorCodec(TEST_KEY)
    owner_id = _id(1, 1)
    workspace_id = _id(2, 1)
    fingerprint = _job_filter(owner_id=owner_id, workspace_id=workspace_id)

    token = codec.encode(
        resource="job",
        last_created_at=CREATED_AT,
        last_id=_id(5, 1),
        filter_hash=fingerprint,
        limit=25,
    )
    position = codec.decode(
        token,
        expected_resource="job",
        expected_filter_hash=fingerprint,
        expected_limit=25,
    )

    assert _decode_payload(token) == {
        "direction": "next",
        "filter_hash": fingerprint,
        "last_created_at": "2026-08-10T12:00:00Z",
        "last_id": str(_id(5, 1)),
        "limit": 25,
        "resource": "job",
        "sort": "created_at_desc",
        "v": 1,
    }
    assert position.last_created_at == CREATED_AT
    assert position.last_id == _id(5, 1)


def test_job_pages_are_stable_owner_and_workspace_scoped(session_factory) -> None:
    values = _seed_pages(session_factory)
    service = JobService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    cursor = None
    collected: list[Job] = []

    for _ in range(4):
        page = service.list_job_page(
            effective_owner_id=values["owner_id"],
            workspace_id=values["first_workspace"].workspace_id,
            cursor=cursor,
            limit=2,
        )
        collected.extend(page.items)
        if not page.has_more:
            assert page.next_cursor is None
            break
        assert page.next_cursor is not None
        cursor = page.next_cursor
    else:
        pytest.fail("Job cursor가 종료되지 않았습니다.")

    expected = sorted(
        [
            item
            for item in values["jobs"]
            if item.workspace_id == values["first_workspace"].workspace_id
        ],
        key=lambda item: (item.created_at, item.job_id),
        reverse=True,
    )
    assert [item.job_id for item in collected] == [item.job_id for item in expected]
    assert len({item.job_id for item in collected}) == len(collected)


def test_job_page_filters_and_binds_cursor_context(session_factory) -> None:
    values = _seed_pages(session_factory)
    service = JobService(session_factory, cursor_codec=CursorCodec(TEST_KEY))
    first = service.list_job_page(
        effective_owner_id=values["owner_id"],
        workspace_id=values["first_workspace"].workspace_id,
        project_id=values["first_project"].project_id,
        status=JobStatus.QUEUED,
        job_type="mix",
        limit=1,
    )
    assert first.next_cursor is not None
    assert len(first.items) == 1

    variants = [
        {"effective_owner_id": values["other_owner_id"]},
        {"workspace_id": values["second_workspace"].workspace_id},
        {"project_id": values["second_project"].project_id},
        {"status": JobStatus.RUNNING},
        {"job_type": "export"},
    ]
    base = {
        "effective_owner_id": values["owner_id"],
        "workspace_id": values["first_workspace"].workspace_id,
        "project_id": values["first_project"].project_id,
        "status": JobStatus.QUEUED,
        "job_type": "mix",
        "cursor": first.next_cursor,
        "limit": 1,
    }
    for changes in variants:
        with pytest.raises(InvalidCursorError):
            service.list_job_page(**(base | changes))


def test_job_repository_enforces_owner_scope(session_factory) -> None:
    values = _seed_pages(session_factory)
    with session_factory() as session:
        repository = JobRepository(session)
        assert (
            repository.list_jobs_after(
                owner_id=values["owner_id"],
                workspace_id=values["other_workspace"].workspace_id,
            )
            == []
        )
        owned = repository.list_jobs_after(
            owner_id=values["owner_id"],
            workspace_id=values["first_workspace"].workspace_id,
            project_id=values["first_project"].project_id,
            status=JobStatus.QUEUED,
            job_type="mix",
        )
    assert [item.job_id for item in owned] == [_id(5, 2), _id(5, 1), _id(5, 3)]


def test_job_page_rejects_scope_filters_limit_and_missing_codec(
    session_factory,
) -> None:
    values = _seed_pages(session_factory)
    service = JobService(session_factory, cursor_codec=CursorCodec(TEST_KEY))

    with pytest.raises(ResourceNotFoundError, match="Workspace"):
        service.list_job_page(
            effective_owner_id=values["owner_id"],
            workspace_id=values["other_workspace"].workspace_id,
        )
    with pytest.raises(ResourceNotFoundError, match="MusicProject"):
        service.list_job_page(
            effective_owner_id=values["owner_id"],
            workspace_id=values["first_workspace"].workspace_id,
            project_id=values["other_project"].project_id,
        )
    for invalid_limit in (True, False, 0, 101, 1.0, "10"):
        with pytest.raises(InvalidLimitError):
            service.list_job_page(
                effective_owner_id=values["owner_id"],
                workspace_id=values["first_workspace"].workspace_id,
                limit=invalid_limit,  # type: ignore[arg-type]
            )
    for invalid_type in ("", "   ", True):
        with pytest.raises(ApplicationValidationError):
            service.list_job_page(
                effective_owner_id=values["owner_id"],
                workspace_id=values["first_workspace"].workspace_id,
                job_type=invalid_type,  # type: ignore[arg-type]
            )
    with pytest.raises(CursorConfigurationError):
        JobService(session_factory).list_job_page(
            effective_owner_id=values["owner_id"],
            workspace_id=values["first_workspace"].workspace_id,
        )


def test_job_page_returns_empty_terminal_page(session_factory) -> None:
    owner_id = _id(1, 1)
    workspace = _workspace(owner_id, 1)
    with session_factory.begin() as session:
        session.add(workspace)
    page = JobService(
        session_factory,
        cursor_codec=CursorCodec(TEST_KEY),
    ).list_job_page(
        effective_owner_id=owner_id,
        workspace_id=workspace.workspace_id,
        limit=20,
    )
    assert page.items == ()
    assert page.has_more is False
    assert page.next_cursor is None
    assert page.limit == 20


def _seed_query_plan(engine) -> dict[str, object]:
    owner_id = _id(11, 1)
    other_owner_id = _id(11, 2)
    workspaces = [
        {
            "workspace_id": _id(12, index),
            "owner_id": owner_id if index <= 2 else other_owner_id,
            "name": f"Plan Workspace {index}",
            "lifecycle_status": "active",
            "created_at": CREATED_AT,
            "updated_at": CREATED_AT,
            "deleted_at": None,
        }
        for index in range(1, 5)
    ]
    projects = [
        {
            "project_id": _id(13, index),
            "workspace_id": workspaces[(index - 1) // 2]["workspace_id"],
            "title": f"Plan Project {index}",
            "description": None,
            "lifecycle_status": "active",
            "created_by": _id(14, index),
            "created_at": CREATED_AT,
            "updated_at": CREATED_AT,
            "deleted_at": None,
        }
        for index in range(1, 9)
    ]
    statuses = tuple(JobStatus)
    job_types = ("mix", "export", "audio_analysis", "music_generation")
    rows = []
    for index in range(1, 10_001):
        workspace_offset = (index - 1) % len(workspaces)
        project_offset = workspace_offset * 2 + ((index // len(workspaces)) % 2)
        rows.append(
            {
                "job_id": _id(15, index),
                "project_id": projects[project_offset]["project_id"],
                "workspace_id": workspaces[workspace_offset]["workspace_id"],
                "job_type": job_types[index % len(job_types)],
                "status": statuses[index % len(statuses)],
                "api_contract_version": "1.0",
                "settings_snapshot": {},
                "requested_by": _id(16, index),
                "created_at": CREATED_AT - timedelta(seconds=index // 3),
                "attempt": 0,
            }
        )
    with engine.begin() as connection:
        connection.execute(insert(Workspace), workspaces)
        connection.execute(insert(MusicProject), projects)
        for start in range(0, len(rows), 1_000):
            connection.execute(insert(Job), rows[start : start + 1_000])
    return {
        "owner_id": owner_id,
        "workspace_id": workspaces[0]["workspace_id"],
        "project_id": projects[0]["project_id"],
        "status": statuses[1],
        "job_type": job_types[1],
        "anchor_time": CREATED_AT - timedelta(seconds=500),
        "anchor_id": _id(15, 5_000),
    }


def test_job_repository_query_plans_use_0017_indexes(tmp_path: Path) -> None:
    engine = create_database_engine(
        f"sqlite:///{(tmp_path / 'job-query-plan.db').as_posix()}"
    )
    Base.metadata.create_all(engine)
    values = _seed_query_plan(engine)
    filters = {
        "workspace": {},
        "project": {"project_id": values["project_id"]},
        "status": {"status": values["status"]},
        "type": {"job_type": values["job_type"]},
    }
    expected_indexes = {
        "workspace": "ix_jobs_workspace_keyset",
        "project": "ix_jobs_workspace_project_keyset",
        "status": "ix_jobs_workspace_status_keyset",
        "type": "ix_jobs_workspace_type_keyset",
    }

    with engine.connect() as connection:
        for name, query_filters in filters.items():
            for page, position in {
                "first": {},
                "next": {
                    "last_created_at": values["anchor_time"],
                    "last_id": values["anchor_id"],
                },
            }.items():
                statement = _build_list_jobs_after_statement(
                    owner_id=values["owner_id"],
                    workspace_id=values["workspace_id"],
                    limit=51,
                    **query_filters,
                    **position,
                )
                compiled = statement.compile(
                    dialect=engine.dialect,
                    compile_kwargs={"literal_binds": True},
                )
                plan = " | ".join(
                    row[3]
                    for row in connection.exec_driver_sql(
                        f"EXPLAIN QUERY PLAN {compiled}"
                    )
                )
                assert expected_indexes[name] in plan, (name, page, plan)
                assert "TEMP B-TREE" not in plan, (name, page, plan)
                assert "SCAN jobs" not in plan, (name, page, plan)
                with Session(engine) as session:
                    rows = list(session.scalars(statement))
                ordering = [(row.created_at, row.job_id) for row in rows]
                assert ordering == sorted(ordering, reverse=True)
    engine.dispose()
