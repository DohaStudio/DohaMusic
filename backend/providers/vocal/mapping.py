"""DohaMusic 권한 context를 DohaVocal 요청 DTO로 변환한다."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from .contracts import VocalCapability, VocalCreateJobRequest, VocalJobInput


@dataclass(frozen=True, slots=True)
class AuthorizedVocalJobContext:
    """DohaMusic service가 owner·workspace·project 권한을 해소한 뒤의 입력."""

    effective_owner_id: UUID
    workspace_id: UUID
    project_id: UUID
    capability: VocalCapability
    idempotency_key: str
    input_asset_version_ids: tuple[UUID, ...]
    input_artifact_ids: tuple[UUID, ...]
    model_manifest_id: str
    settings_snapshot: dict[str, Any]
    job_input: VocalJobInput
    composition_snapshot_id: UUID | None = None


def map_authorized_create_job(
    context: AuthorizedVocalJobContext,
) -> VocalCreateJobRequest:
    """임의 owner 입력 없이 effective owner만 requested_by로 전달한다."""

    return VocalCreateJobRequest(
        capability=context.capability,
        idempotency_key=context.idempotency_key,
        project_id=str(context.project_id),
        input_asset_version_ids=tuple(map(str, context.input_asset_version_ids)),
        input_artifact_ids=tuple(map(str, context.input_artifact_ids)),
        model_manifest_id=context.model_manifest_id,
        settings_snapshot=deepcopy(context.settings_snapshot),
        requested_by=str(context.effective_owner_id),
        composition_snapshot_id=(
            str(context.composition_snapshot_id)
            if context.composition_snapshot_id is not None
            else None
        ),
        job_input=context.job_input,
    )
