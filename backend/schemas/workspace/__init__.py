"""Workspace REST API v1 transport Schema."""

from backend.schemas.workspace.bootstrap import WorkspaceBootstrapResult
from backend.schemas.workspace.common import (
    CollectionLinks,
    CollectionResponse,
    ErrorDetail,
    ErrorEnvelope,
    ErrorResponse,
    Pagination,
    SuccessResponse,
)
from backend.schemas.workspace.resources import (
    ProjectAssetCreateRequest,
    ProjectAssetSummary,
    ProjectCreateRequest,
    ProjectDetail,
    ProjectSummary,
    ProjectUpdateRequest,
    WorkspaceDetail,
    WorkspaceSummary,
    WorkspaceUpdateRequest,
)

__all__ = [
    "CollectionLinks",
    "CollectionResponse",
    "ErrorDetail",
    "ErrorEnvelope",
    "ErrorResponse",
    "Pagination",
    "ProjectAssetCreateRequest",
    "ProjectAssetSummary",
    "ProjectCreateRequest",
    "ProjectDetail",
    "ProjectSummary",
    "ProjectUpdateRequest",
    "SuccessResponse",
    "WorkspaceBootstrapResult",
    "WorkspaceDetail",
    "WorkspaceSummary",
    "WorkspaceUpdateRequest",
]
