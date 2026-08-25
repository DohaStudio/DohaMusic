"""Hashed idempotency keys for multi-resource mutation replay safety."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("scope", "key_hash", name="uq_idempotency_scope_key_hash"),
        Index("ix_idempotency_records_expires_at", "expires_at"),
        CheckConstraint(
            "completed_revision IS NULL OR completed_revision >= 0",
            name="ck_idempotency_records_non_negative_completed_revision",
        ),
        CheckConstraint(
            "result_version IS NULL OR result_version > 0",
            name="ck_idempotency_records_positive_result_version",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    scope: Mapped[str] = mapped_column(String(150), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="IN_PROGRESS"
    )
    resource_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completed_revision: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
