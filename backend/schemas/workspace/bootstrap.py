"""명시적 단일 사용자 Workspace Bootstrap 출력 Schema."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class CompositionTransitionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "selection_required"]
    authority: Literal["NO_PREEXISTING_SELECTION_AUTHORITY"]
    project_count: int
    empty_project_count: int
    selection_required_project_count: int
    already_selected_project_count: int
    authoritative_backfill_project_count: int
    ambiguous_authority_project_count: int
    invalid_cross_project_selection_count: int
    expected_mutation_row_count: int


class WorkspaceBootstrapResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["planned", "created", "existing"]
    applied: bool
    created: bool
    workspace_id: UUID | None
    name: str
    migration_revision: str | None
    transition: CompositionTransitionResult | None = None
