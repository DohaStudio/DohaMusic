from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, Response, status

from backend.api.v1.dependencies import get_effective_owner_id, get_request_id
from backend.core.exceptions import AppError
from backend.schemas.workspace import SuccessResponse
from backend.schemas.workspace.music_director import (
    MusicDirectorCandidateDetail,
    MusicDirectorJobCreated,
    MusicDirectorRunCreateRequest,
    MusicDirectorRunDetail,
    MusicDirectorSelectionRequest,
    MusicDirectorSelectionResult,
)
from backend.services.workspace.music_director_candidate_persistence_service import (
    MusicDirectorPersistenceError,
    MusicDirectorPersistenceErrorCode,
)
from backend.services.workspace.music_director_public_service import (
    MusicDirectorPublicError,
    MusicDirectorPublicErrorCode,
    MusicDirectorPublicService,
    PublicMusicDirectorRun,
)

router = APIRouter(prefix="/projects/{project_id}/music-director", tags=["MusicDirector"])
Owner = Annotated[UUID, Depends(get_effective_owner_id)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]


def get_service(request: Request) -> MusicDirectorPublicService:
    service = getattr(request.app.state, "music_director_public_service", None)
    if not isinstance(service, MusicDirectorPublicService):
        raise TypeError("MusicDirectorPublicService is not configured")
    return service


Service = Annotated[MusicDirectorPublicService, Depends(get_service)]


@router.post(
    "/runs",
    response_model=SuccessResponse[MusicDirectorJobCreated],
    status_code=201,
    operation_id="create_music_director_run",
)
def create_run(
    project_id: UUID,
    payload: MusicDirectorRunCreateRequest,
    request: Request,
    response: Response,
    service: Service,
    owner: Owner,
    idempotency_key: IdempotencyKey,
):
    try:
        creation = service.create_run_job(
            effective_owner_id=owner,
            project_id=project_id,
            composition_snapshot_id=payload.composition_snapshot_id,
            instruction=payload.music_intent.instruction,
            candidate_count=payload.music_intent.candidate_count,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _map_error(exc) from exc
    job = creation.aggregate.job
    response.status_code = creation.response_status
    return SuccessResponse(
        data=MusicDirectorJobCreated(
            job_id=job.job_id,
            project_id=job.project_id,
            composition_snapshot_id=job.composition_snapshot_id,
            status=job.status.value,
            candidate_count=payload.music_intent.candidate_count,
            created_at=job.created_at,
        ),
        request_id=get_request_id(request),
    )


@router.get(
    "/runs/{run_id}",
    response_model=SuccessResponse[MusicDirectorRunDetail],
    operation_id="get_music_director_run",
)
def get_run(project_id: UUID, run_id: UUID, request: Request, service: Service, owner: Owner):
    try:
        aggregate = service.get_run(effective_owner_id=owner, project_id=project_id, run_id=run_id)
    except Exception as exc:
        raise _map_error(exc) from exc
    return SuccessResponse(data=_run_detail(aggregate), request_id=get_request_id(request))


@router.get(
    "/runs/{run_id}/candidates/{candidate_id}",
    response_model=SuccessResponse[MusicDirectorCandidateDetail],
    operation_id="get_music_director_candidate",
)
def get_candidate(
    project_id: UUID,
    run_id: UUID,
    candidate_id: UUID,
    request: Request,
    service: Service,
    owner: Owner,
):
    try:
        aggregate, candidate = service.get_candidate(
            effective_owner_id=owner,
            project_id=project_id,
            run_id=run_id,
            candidate_id=candidate_id,
        )
    except Exception as exc:
        raise _map_error(exc) from exc
    return SuccessResponse(
        data=_candidate_detail(aggregate, candidate), request_id=get_request_id(request)
    )


@router.post(
    "/runs/{run_id}/candidates/{candidate_id}/select",
    response_model=SuccessResponse[MusicDirectorSelectionResult],
    operation_id="select_music_director_candidate",
)
def select_candidate(
    project_id: UUID,
    run_id: UUID,
    candidate_id: UUID,
    payload: MusicDirectorSelectionRequest,
    request: Request,
    service: Service,
    owner: Owner,
):
    try:
        run = service.select_candidate(
            effective_owner_id=owner,
            project_id=project_id,
            run_id=run_id,
            candidate_id=candidate_id,
            expected_version=payload.expected_run_version,
        )
    except Exception as exc:
        raise _map_error(exc) from exc
    return SuccessResponse(
        data=MusicDirectorSelectionResult(
            run_id=run.run_id, selected_candidate_id=candidate_id, version=run.version
        ),
        request_id=get_request_id(request),
    )


@router.post(
    "/jobs/{job_id}/cancel",
    status_code=status.HTTP_200_OK,
    operation_id="cancel_music_director_job",
)
def cancel_job(project_id: UUID, job_id: UUID, response: Response, service: Service, owner: Owner):
    try:
        result = service.cancel_job(effective_owner_id=owner, project_id=project_id, job_id=job_id)
    except Exception as exc:
        raise _map_error(exc) from exc
    response.status_code = result.response_status
    return {"job_id": str(result.job.job_id), "status": result.job.status.value}


def _candidate_detail(aggregate: PublicMusicDirectorRun, candidate) -> MusicDirectorCandidateDetail:
    run = aggregate.run
    return MusicDirectorCandidateDetail(
        candidate_id=candidate.candidate_id,
        ordinal=candidate.ordinal,
        status=candidate.status,
        proposal_digest=candidate.proposal_digest,
        proposal_artifact_id=candidate.proposal_artifact_id,
        preview_artifact_id=candidate.preview_artifact_id,
        candidate_asset_version_id=candidate.candidate_asset_version_id,
        selected=run.selected_candidate_id == candidate.candidate_id,
        applied=run.applied_candidate_id == candidate.candidate_id,
    )


def _run_detail(aggregate: PublicMusicDirectorRun) -> MusicDirectorRunDetail:
    run = aggregate.run
    return MusicDirectorRunDetail(
        run_id=run.run_id,
        job_id=run.job_id,
        project_id=run.project_id,
        composition_snapshot_id=run.composition_snapshot_id,
        selected_candidate_id=run.selected_candidate_id,
        applied_candidate_id=run.applied_candidate_id,
        applied_working_revision=run.applied_working_revision,
        version=run.version,
        status=aggregate.job.status.value,
        candidates=[_candidate_detail(aggregate, item) for item in aggregate.candidates],
        created_at=run.created_at,
        updated_at=run.updated_at,
    )


def _map_error(exc: Exception) -> AppError:
    if isinstance(exc, MusicDirectorPublicError):
        status_code = 409 if exc.code is MusicDirectorPublicErrorCode.NOT_READY else 404
        return AppError(
            code=f"MUSIC_DIRECTOR_{exc.code.value}",
            message="Music Director resource is unavailable.",
            status_code=status_code,
        )
    if isinstance(exc, MusicDirectorPersistenceError):
        status_code = (
            409
            if exc.code
            in {
                MusicDirectorPersistenceErrorCode.STALE_SELECTION,
                MusicDirectorPersistenceErrorCode.INVALID_TRANSITION,
            }
            else 404
        )
        return AppError(
            code=f"MUSIC_DIRECTOR_{exc.code.value}",
            message="Music Director request conflicts with current authority.",
            status_code=status_code,
        )
    from backend.api.v1.routes.common import map_job_error

    return map_job_error(exc)
