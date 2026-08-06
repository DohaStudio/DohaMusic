"""명시적 단일 사용자 Workspace Bootstrap 출력 Schema."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class WorkspaceBootstrapResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["planned", "created", "existing"]
    applied: bool
    created: bool
    workspace_id: UUID | None
    name: str
    migration_revision: str | None
