"""Persistent generated lyrics document."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LyricsDocument(Base):
    __tablename__ = "lyrics_documents"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("lyrics_documents.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    revision_instruction: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str | None] = mapped_column(String(64))
    result_hash: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str | None] = mapped_column(String(300))
    language: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    genre: Mapped[str | None] = mapped_column(String(100))
    mood: Mapped[str | None] = mapped_column(String(100))
    keywords: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    structure: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    sections_data: Mapped[list[dict[str, Any]]] = mapped_column(
        "sections", JSON, nullable=False, default=list
    )
    full_text: Mapped[str] = mapped_column(Text, nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_payload: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
