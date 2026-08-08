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
    AssetCreateRequest,
    AssetDetail,
    AssetSummary,
    AssetUpdateRequest,
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
    "AssetCreateRequest",
    "AssetDetail",
    "AssetSummary",
    "AssetUpdateRequest",
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
