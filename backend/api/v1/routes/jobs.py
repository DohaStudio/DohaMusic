"""Workspace Job 공식 Resource REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status

from backend.api.v1.dependencies import (
    get_effective_workspace,
    get_job_service,
    get_request_id,
)
from backend.api.v1.routes.common import (
    invalid_input,
    map_job_error,
    relative_next_url,
    relative_request_url,
)
from backend.models.workspace import Job, JobStatus, Workspace
from backend.schemas.workspace import (
    CollectionLinks,
    CollectionResponse,
    JobCreateRequest,
    JobDetail,
    JobInputDetail,
    JobModelUsageDetail,
    JobOutputDetail,
    JobSummary,
    Pagination,
    SuccessResponse,
)
from backend.services.workspace import JobAggregate, JobReferenceInput, JobService

JobServiceDependency = Annotated[JobService, Depends(get_job_service)]
EffectiveWorkspaceDependency = Annotated[Workspace, Depends(get_effective_workspace)]
IdempotencyKeyHeader = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        description="Job 생성·재시도 요청을 구분하는 opaque idempotency key",
    ),
]

_ALLOWED_JOB_QUERY_FIELDS = frozenset(
    {"project_id", "status", "job_type", "cursor", "limit"}
)


def reject_job_query_input(request: Request) -> None:
    unexpected = set(request.query_params).difference(_ALLOWED_JOB_QUERY_FIELDS)
    if unexpected:
        raise invalid_input("Job API에서 허용하지 않는 query parameter입니다.")


router = APIRouter(
    prefix="/jobs",
    tags=["WorkspaceJob"],
    dependencies=[Depends(reject_job_query_input)],
)


@router.get(
    "",
    response_model=CollectionResponse[JobSummary],
    operation_id="list_workspace_jobs",
    summary="effective Workspace의 Job 목록 조회",
)
def list_jobs(
    request: Request,
    service: JobServiceDependency,
    workspace: EffectiveWorkspaceDependency,
    project_id: UUID | None = None,
    status_filter: Annotated[JobStatus | None, Query(alias="status")] = None,
    job_type: Annotated[str | None, Query(max_length=64)] = None,
    cursor: Annotated[str | None, Query(max_length=2048)] = None,
    limit: Annotated[int, Query()] = 50,
) -> CollectionResponse[JobSummary]:
    try:
        page = service.list_job_page(
            effective_owner_id=workspace.owner_id,
            workspace_id=workspace.workspace_id,
            project_id=project_id,
            status=status_filter,
            job_type=job_type,
            cursor=cursor,
            limit=limit,
        )
    except Exception as exc:
        raise map_job_error(exc) from exc
    return CollectionResponse[JobSummary](
        data=[JobSummary.model_validate(item) for item in page.items],
        pagination=Pagination(
            limit=page.limit,
            next_cursor=page.next_cursor,
            has_more=page.has_more,
        ),
        links=CollectionLinks(
            self=relative_request_url(request),
            next=relative_next_url(request, page.next_cursor),
        ),
        request_id=get_request_id(request),
    )


@router.post(
    "",
    response_model=SuccessResponse[JobDetail],
    status_code=status.HTTP_201_CREATED,
    operation_id="create_workspace_job",
    summary="불변 Job 요청 snapshot 생성",
)
def create_job(
    payload: JobCreateRequest,
    request: Request,
    response: Response,
    service: JobServiceDependency,
    workspace: EffectiveWorkspaceDependency,
    idempotency_key: IdempotencyKeyHeader,
) -> SuccessResponse[JobDetail]:
    try:
        result = service.create_job_for_owner(
            effective_owner_id=workspace.owner_id,
            project_id=payload.project_id,
            job_type=payload.job_type,
            api_contract_version="1",
            settings_snapshot=payload.settings_snapshot,
            idempotency_key=idempotency_key,
            inputs=tuple(
                JobReferenceInput(
                    input_order=item.input_order,
                    input_role=item.input_role,
                    asset_version_id=item.asset_version_id,
                    artifact_id=item.artifact_id,
                )
                for item in payload.inputs
            ),
            composition_snapshot_id=payload.composition_snapshot_id,
            provider_id=payload.provider_id,
            model_manifest_id=payload.model_manifest_id,
            job_input=payload.job_input,
        )
    except Exception as exc:
        raise map_job_error(exc) from exc
    response.status_code = result.response_status
    return SuccessResponse[JobDetail](
        data=_aggregate_detail(result.aggregate),
        request_id=get_request_id(request),
    )


@router.get(
    "/{job_id}",
    response_model=SuccessResponse[JobDetail],
    operation_id="get_workspace_job",
    summary="Job aggregate 상세 조회",
)
def get_job(
    job_id: UUID,
    request: Request,
    service: JobServiceDependency,
    workspace: EffectiveWorkspaceDependency,
) -> SuccessResponse[JobDetail]:
    try:
        aggregate = service.get_job_aggregate_for_owner(
            job_id,
            effective_owner_id=workspace.owner_id,
        )
    except Exception as exc:
        raise map_job_error(exc) from exc
    return SuccessResponse[JobDetail](
        data=_aggregate_detail(aggregate),
        request_id=get_request_id(request),
    )


@router.post(
    "/{job_id}/cancel",
    response_model=SuccessResponse[JobDetail],
    operation_id="cancel_workspace_job",
    summary="Job 취소 또는 실행 중 취소 요청",
)
def cancel_job(
    job_id: UUID,
    request: Request,
    response: Response,
    service: JobServiceDependency,
    workspace: EffectiveWorkspaceDependency,
) -> SuccessResponse[JobDetail]:
    try:
        result = service.cancel_job_for_owner(
            job_id,
            effective_owner_id=workspace.owner_id,
        )
        aggregate = service.get_job_aggregate_for_owner(
            job_id,
            effective_owner_id=workspace.owner_id,
        )
    except Exception as exc:
        raise map_job_error(exc, action="cancel") from exc
    response.status_code = result.response_status
    return SuccessResponse[JobDetail](
        data=_aggregate_detail(aggregate),
        request_id=get_request_id(request),
    )


@router.post(
    "/{job_id}/retry",
    response_model=SuccessResponse[JobDetail],
    status_code=status.HTTP_202_ACCEPTED,
    operation_id="retry_workspace_job",
    summary="종료된 Job의 frozen request로 새 Job 생성",
)
def retry_job(
    job_id: UUID,
    request: Request,
    response: Response,
    service: JobServiceDependency,
    workspace: EffectiveWorkspaceDependency,
    idempotency_key: IdempotencyKeyHeader,
) -> SuccessResponse[JobDetail]:
    try:
        result = service.retry_job_for_owner(
            job_id,
            effective_owner_id=workspace.owner_id,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise map_job_error(exc, action="retry") from exc
    response.status_code = result.response_status
    return SuccessResponse[JobDetail](
        data=_aggregate_detail(result.aggregate),
        request_id=get_request_id(request),
    )


def _aggregate_detail(aggregate: JobAggregate) -> JobDetail:
    job = aggregate.job
    summary = _job_summary(job)
    return JobDetail(
        **summary.model_dump(),
        inputs=[JobInputDetail.model_validate(item) for item in aggregate.inputs],
        outputs=[JobOutputDetail.model_validate(item) for item in aggregate.outputs],
        model_usages=[
            JobModelUsageDetail.model_validate(item) for item in aggregate.model_usages
        ],
        error_code=job.error_code,
        error_message=job.error_message,
        error_retryable=job.error_retryable,
        error_details_id=job.error_details_id,
    )


def _job_summary(job: Job) -> JobSummary:
    return JobSummary.model_validate(job)
