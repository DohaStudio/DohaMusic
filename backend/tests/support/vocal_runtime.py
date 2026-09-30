"""Pinned real DohaVocal ASGI fixture; no production imports or network calls."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROVIDER_SHA = "e28320ef26a2dc49eaefdfa62bceea0c8c69e6ed"


@pytest.fixture
def vocal_runtime(monkeypatch):
    configured = os.environ.get("DOHAVOCAL_E2E_SOURCE")
    if not configured:
        pytest.skip("DOHAVOCAL_E2E_SOURCE must identify the pinned clean Provider checkout")
    source = Path(configured).resolve()
    actual = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    assert actual == PROVIDER_SHA, "Provider fixture SHA mismatch"
    assert not subprocess.check_output(
        ["git", "-C", str(source), "status", "--porcelain", "--untracked-files=no"], text=True
    ).strip(), "Provider fixture has tracked changes"
    monkeypatch.syspath_prepend(str(source / "src"))
    from dohavocal.api.app import create_app

    # Only HTTP wire calls cross into the actual app. No store/provider shortcuts.
    with TestClient(create_app(), base_url="http://vocal.fixture") as client:
        yield client
