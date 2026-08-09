"""Artifact Metadata와 검증된 Payload delivery REST API."""

from __future__ import annotations

import sys
from collections.abc import Iterator
from contextlib import AbstractContextManager
from typing import Annotated, BinaryIO
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import StreamingResponse

from backend.api.v1.dependencies import (
    get_artifact_application_service,
    get_effective_owner_id,
    get_request_id,
)
from backend.api.v1.range_requests import (
    ByteRange,
    RangeNotSatisfiable,
    parse_single_byte_range,
)
from backend.api.v1.routes.common import reject_owner_input
from backend.core.exceptions import AppError
from backend.schemas.workspace import ArtifactDetail, ErrorResponse, SuccessResponse
from backend.services.workspace import (
    ArtifactAccessError,
    ArtifactAccessErrorCode,
    ArtifactApplicationService,
    ArtifactContentHandle,
    ArtifactMetadata,
)

_STREAM_CHUNK_SIZE = 1024 * 1024
_MEDIA_EXTENSIONS = {
    "application/json": "json",
    "audio/flac": "flac",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "text/plain": "txt",
}
_BINARY_RESPONSES = {
    200: {
        "description": "전체 Artifact Payload",
        "content": {
            "application/octet-stream": {
                "schema": {"type": "string", "format": "binary"}
            }
        },
    },
    206: {
        "description": "단일 byte Range Payload",
        "content": {
            "application/octet-stream": {
                "schema": {"type": "string", "format": "binary"}
            }
        },
    },
    416: {"model": ErrorResponse, "description": "만족할 수 없는 byte Range"},
}

router = APIRouter(
    prefix="/artifacts",
    tags=["Artifact"],
    dependencies=[Depends(reject_owner_input)],
)
ArtifactServiceDependency = Annotated[
    ArtifactApplicationService, Depends(get_artifact_application_service)
]
EffectiveOwnerDependency = Annotated[UUID, Depends(get_effective_owner_id)]
RangeHeader = Annotated[
    str | None,
    Header(
        alias="Range",
        max_length=256,
        description="단일 byte Range: bytes=start-end, bytes=start-, bytes=-suffix",
    ),
]


@router.get(
    "/{artifact_id}",
    response_model=SuccessResponse[ArtifactDetail],
    response_model_exclude_none=True,
    operation_id="get_artifact",
    summary="Artifact Metadata 조회",
)
def get_artifact(
    artifact_id: UUID,
    request: Request,
    service: ArtifactServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
) -> SuccessResponse[ArtifactDetail]:
    try:
        metadata = service.get_artifact_for_owner(
            artifact_id,
            effective_owner_id=effective_owner_id,
        )
    except ArtifactAccessError as exc:
        raise _map_artifact_error(exc) from exc
    return SuccessResponse[ArtifactDetail](
        data=_metadata_detail(metadata),
        request_id=get_request_id(request),
    )


@router.get(
    "/{artifact_id}/content",
    response_class=StreamingResponse,
    responses=_BINARY_RESPONSES,
    operation_id="get_artifact_content",
    summary="Artifact inline content 조회",
)
def get_artifact_content(
    artifact_id: UUID,
    service: ArtifactServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
    range_header: RangeHeader = None,
) -> StreamingResponse:
    return _delivery_response(
        artifact_id=artifact_id,
        service=service,
        effective_owner_id=effective_owner_id,
        range_header=range_header,
        download=False,
    )


@router.get(
    "/{artifact_id}/download",
    response_class=StreamingResponse,
    responses=_BINARY_RESPONSES,
    operation_id="download_artifact",
    summary="Artifact attachment 다운로드",
)
def download_artifact(
    artifact_id: UUID,
    service: ArtifactServiceDependency,
    effective_owner_id: EffectiveOwnerDependency,
    range_header: RangeHeader = None,
) -> StreamingResponse:
    return _delivery_response(
        artifact_id=artifact_id,
        service=service,
        effective_owner_id=effective_owner_id,
        range_header=range_header,
        download=True,
    )


def _delivery_response(
    *,
    artifact_id: UUID,
    service: ArtifactApplicationService,
    effective_owner_id: UUID,
    range_header: str | None,
    download: bool,
) -> StreamingResponse:
    content_context = service.open_content_for_owner(
        artifact_id,
        effective_owner_id=effective_owner_id,
    )
    entered = False
    try:
        handle, stream = content_context.__enter__()
        entered = True
        try:
            byte_range = parse_single_byte_range(
                range_header,
                size_bytes=handle.size_bytes,
            )
        except RangeNotSatisfiable:
            raise _invalid_range(handle.size_bytes) from None

        status_code = (
            status.HTTP_206_PARTIAL_CONTENT if byte_range else status.HTTP_200_OK
        )
        start = byte_range.start if byte_range else 0
        length = byte_range.length if byte_range else handle.size_bytes
        stream.seek(start)
        headers = _delivery_headers(
            handle,
            byte_range=byte_range,
            download=download,
        )
        body = _stream_content(content_context, stream, length)
        response = StreamingResponse(
            body,
            status_code=status_code,
            media_type=handle.media_type,
            headers=headers,
        )
        entered = False
        return response
    except ArtifactAccessError as exc:
        raise _map_artifact_error(exc) from exc
    finally:
        if entered:
            content_context.__exit__(*sys.exc_info())


def _stream_content(
    context: AbstractContextManager[tuple[ArtifactContentHandle, BinaryIO]],
    stream: BinaryIO,
    length: int,
) -> Iterator[bytes]:
    remaining = length
    try:
        while remaining:
            chunk = stream.read(min(_STREAM_CHUNK_SIZE, remaining))
            if not chunk:
                raise OSError("Artifact stream ended before the verified length.")
            remaining -= len(chunk)
            yield chunk
    finally:
        context.__exit__(None, None, None)


def _delivery_headers(
    handle: ArtifactContentHandle,
    *,
    byte_range: ByteRange | None,
    download: bool,
) -> dict[str, str]:
    length = byte_range.length if byte_range else handle.size_bytes
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, no-store",
        "Content-Disposition": (
            f'attachment; filename="{_download_filename(handle)}"'
            if download
            else "inline"
        ),
        "Content-Length": str(length),
        "Content-Type": handle.media_type,
        "X-Content-Type-Options": "nosniff",
    }
    if byte_range is not None:
        headers["Content-Range"] = (
            f"bytes {byte_range.start}-{byte_range.end}/{handle.size_bytes}"
        )
    return headers


def _download_filename(handle: ArtifactContentHandle) -> str:
    safe_kind = "".join(
        character
        for character in handle.artifact_kind[:64]
        if character.isascii() and (character.isalnum() or character in {"-", "_"})
    ).strip("-_")
    if not safe_kind:
        safe_kind = "artifact"
    extension = _MEDIA_EXTENSIONS.get(handle.media_type, "bin")
    return f"{safe_kind}-{handle.artifact_id}.{extension}"


def _metadata_detail(metadata: ArtifactMetadata) -> ArtifactDetail:
    base_url = f"/api/v1/artifacts/{metadata.artifact_id}"
    content_allowed = metadata.retention_status == "active"
    return ArtifactDetail(
        artifact_id=metadata.artifact_id,
        asset_version_id=metadata.asset_version_id,
        artifact_kind=metadata.artifact_kind,
        media_type=metadata.media_type,
        size_bytes=metadata.size_bytes,
        checksum_algorithm=metadata.checksum_algorithm,
        artifact_checksum=metadata.artifact_checksum,
        producer_type=metadata.producer_type,
        producer_id=metadata.producer_id,
        run_id=metadata.run_id,
        retention_status=metadata.retention_status,
        created_at=metadata.created_at,
        content_url=f"{base_url}/content" if content_allowed else None,
        download_url=f"{base_url}/download" if content_allowed else None,
    )


def _invalid_range(size_bytes: int) -> AppError:
    return AppError(
        code="INVALID_RANGE",
        message="요청한 byte Range를 제공할 수 없습니다.",
        status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes */{size_bytes}",
        },
    )


def _map_artifact_error(exc: ArtifactAccessError) -> AppError:
    mapping = {
        ArtifactAccessErrorCode.NOT_FOUND: (
            status.HTTP_404_NOT_FOUND,
            "Artifact를 찾을 수 없습니다.",
        ),
        ArtifactAccessErrorCode.CONTENT_UNAVAILABLE: (
            status.HTTP_409_CONFLICT,
            "Artifact content를 안전하게 제공할 수 없습니다.",
        ),
        ArtifactAccessErrorCode.QUARANTINED: (
            status.HTTP_409_CONFLICT,
            "Artifact가 격리되어 content를 제공할 수 없습니다.",
        ),
        ArtifactAccessErrorCode.GONE: (
            status.HTTP_410_GONE,
            "Artifact content를 더 이상 제공할 수 없습니다.",
        ),
        ArtifactAccessErrorCode.INTEGRITY_ERROR: (
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Artifact 무결성 검증에 실패했습니다.",
        ),
    }
    status_code, message = mapping[exc.code]
    return AppError(code=exc.code.value, message=message, status_code=status_code)
