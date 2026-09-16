from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

from backend.models.workspace import Job, JobStatus, MusicProject, Workspace
from backend.models.workspace.provider_execution import MusicDirectorProviderExecution

ROOT = Path(__file__).resolve().parents[1]
REVISION = "20260911_0034"
PREVIOUS = "20260911_0033"


def _config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


def test_0034_upgrade_downgrade_reupgrade(tmp_path):
    url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    config = _config(url)
    command.upgrade(config, PREVIOUS)
    command.upgrade(config, REVISION)
    engine = create_engine(url)
    assert "music_director_provider_executions" in inspect(engine).get_table_names()
    command.downgrade(config, PREVIOUS)
    assert "music_director_provider_executions" not in inspect(engine).get_table_names()
    command.upgrade(config, REVISION)


def test_0034_downgrade_with_execution_data_is_blocked(tmp_path):
    from datetime import UTC, datetime
    from uuid import uuid4

    url = f"sqlite:///{tmp_path / 'blocked.db'}"
    config = _config(url)
    command.upgrade(config, REVISION)
    engine = create_engine(url)
    factory = sessionmaker(engine)
    with factory() as session, session.begin():
        owner_id = uuid4()
        workspace = Workspace(owner_id=owner_id, name="Workspace", lifecycle_status="active")
        session.add(workspace)
        session.flush()
        project = MusicProject(
            workspace_id=workspace.workspace_id,
            title="Project",
            lifecycle_status="active",
            created_by=owner_id,
        )
        session.add(project)
        session.flush()
        job = Job(
            project_id=project.project_id,
            workspace_id=workspace.workspace_id,
            job_type="music_director",
            status=JobStatus.RUNNING,
            api_contract_version="1",
            settings_snapshot={},
            requested_by=owner_id,
        )
        session.add(job)
        session.flush()
        session.add(
            MusicDirectorProviderExecution(
                job_id=job.job_id,
                provider_id="mock-director",
                client_execution_key=str(uuid4()),
                status="intended",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    with pytest.raises(RuntimeError, match="downgrade is blocked"):
        command.downgrade(config, PREVIOUS)
    assert "music_director_provider_executions" in inspect(engine).get_table_names()
