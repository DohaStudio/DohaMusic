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

__all__ = [
    "CollectionLinks",
    "CollectionResponse",
    "ErrorDetail",
    "ErrorEnvelope",
    "ErrorResponse",
    "Pagination",
    "SuccessResponse",
    "WorkspaceBootstrapResult",
]
