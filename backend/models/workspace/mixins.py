"""Workspace 목표 Entity에 선택적으로 적용하는 공통 Mixin."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


def utc_now() -> datetime:
    """UTC 기준 현재 시각을 반환한다."""

    return datetime.now(timezone.utc)


class CreatedAtMixin:
    """생성 시각만 필요한 Entity용 Mixin."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )


class TimestampMixin(CreatedAtMixin):
    """변경 가능한 Metadata Entity용 생성·수정 시각 Mixin."""

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class SoftDeleteMixin:
    """문서에서 Soft Delete를 허용한 Entity용 Mixin."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
