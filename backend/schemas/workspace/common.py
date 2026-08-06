"""Workspace REST API v1 공통 성공·오류·Collection Schema."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")


class SuccessResponse(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    data: DataT
    request_id: str = Field(min_length=8, max_length=128)


class Pagination(BaseModel):
    model_config = ConfigDict(extra="forbid")

    limit: int = Field(ge=1, le=100)
    next_cursor: str | None = None
    has_more: bool


class CollectionLinks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    self: str
    next: str | None = None


class CollectionResponse(BaseModel, Generic[DataT]):
    model_config = ConfigDict(extra="forbid")

    data: list[DataT]
    pagination: Pagination
    links: CollectionLinks
    request_id: str = Field(min_length=8, max_length=128)


class ErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: list[str | int] = Field(default_factory=list)
    error_code: str
    message: str


class ErrorEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)
    request_id: str = Field(min_length=8, max_length=128)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error: ErrorEnvelope
