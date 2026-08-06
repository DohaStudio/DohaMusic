from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.factory import create_app
from backend.core.config import Settings


@pytest.fixture
def app(tmp_path) -> FastAPI:
    return create_app(
        Settings(
            database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
            auto_migrate=True,
            storage_root=tmp_path / "storage",
            mock_generation_delay_seconds=0.01,
            worker_max_threads=1,
            log_level="WARNING",
        )
    )


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
