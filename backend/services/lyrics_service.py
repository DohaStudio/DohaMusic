"""Synchronous lyrics generation, revision, validation, and persistence use cases."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.core.logging import get_logger
from backend.lyrics.errors import (
    LyricsError,
    LyricsGenerationError,
    LyricsOutputInvalidError,
    LyricsRevisionError,
)
from backend.lyrics.interfaces import (
    LyricsGenerationRequest,
    LyricsGenerator,
    LyricsRevisionRequest,
    LyricsSection,
)
from backend.lyrics.validator import LyricsValidationResult, validate_lyrics
from backend.models.lyrics_document import LyricsDocument
from backend.repositories.lyrics_repository import LyricsRepository
from backend.schemas.lyrics import (
    LyricsCreate,
    LyricsRevisionCreate,
    LyricsValidationRequest,
)

logger = get_logger(__name__)


class LyricsService:
    def __init__(
        self,
        session_factory: Callable[[], Session],
        generator: LyricsGenerator,
    ) -> None:
        self.session_factory = session_factory
        self.generator = generator

    def create(self, request: LyricsCreate) -> LyricsDocument:
        started_at = time.perf_counter()
        logger.info(
            "lyrics_generation_started provider=%s language=%s",
            self.generator.provider,
            request.language,
        )
        generation_request = LyricsGenerationRequest(
            topic=request.topic,
            genre=request.genre,
            mood=request.mood,
            language=request.language,
            keywords=tuple(request.keywords),
            structure=tuple(request.structure),
            target_duration_seconds=request.target_duration_seconds,
            additional_instructions=request.additional_instructions,
            allow_template_fallback=request.allow_template_fallback,
        )
        try:
            result = self.generator.generate(generation_request)
        except LyricsError:
            raise
        except Exception as exc:
            logger.exception(
                "lyrics_generation_provider_failed provider=%s error_type=%s",
                self.generator.provider,
                type(exc).__name__,
            )
            raise LyricsGenerationError() from exc

        validation_started_at = time.perf_counter()
        validation = validate_lyrics(result.full_text, request.language)
        validation_time = time.perf_counter() - validation_started_at
        if not validation.valid or not result.sections:
            raise LyricsOutputInvalidError()

        metadata = {
            **result.metadata,
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
            "language": request.language,
            "topic": request.topic,
            "genre": request.genre,
            "mood": request.mood,
            "keywords": request.keywords,
            "requested_structure": request.structure,
            "generated_structure": [
                section.section_type for section in validation.sections
            ],
            "target_duration_seconds": request.target_duration_seconds,
            "additional_instructions_provided": bool(request.additional_instructions),
            "generation_time_seconds": result.generation_time_seconds,
            "validation_time_seconds": validation_time,
            "character_count": validation.character_count,
            "line_count": validation.line_count,
            "section_count": validation.section_count,
            "warnings": list(validation.warnings),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        values: dict[str, object] = {
            "result_hash": _content_hash(validation.normalized_lyrics),
            "title": result.title,
            "language": request.language,
            "topic": request.topic,
            "genre": request.genre,
            "mood": request.mood,
            "keywords": request.keywords,
            "structure": [section.section_type for section in validation.sections],
            "sections_data": [
                {
                    "section_type": section.section_type,
                    "lines": list(section.lines),
                }
                for section in validation.sections
            ],
            "full_text": validation.normalized_lyrics,
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
            "status": "GENERATED",
            "metadata_payload": metadata,
        }
        document = self._persist(values, metadata, started_at)
        logger.info(
            "lyrics_generation_finished lyrics_id=%s provider=%s duration_ms=%s",
            document.id,
            result.provider,
            round((time.perf_counter() - started_at) * 1_000, 2),
        )
        return document

    def revise(self, lyrics_id: str, request: LyricsRevisionCreate) -> LyricsDocument:
        started_at = time.perf_counter()
        source = self.get(lyrics_id)
        revise = getattr(self.generator, "revise", None)
        if not callable(revise):
            raise LyricsRevisionError(
                "현재 Lyrics Provider는 의미 기반 수정을 지원하지 않습니다."
            )
        source_sections = tuple(
            LyricsSection(item["section_type"], tuple(item["lines"]))
            for item in source.sections_data
        )
        logger.info(
            "lyrics_revision_started provider=%s source_version=%s",
            self.generator.provider,
            source.version,
        )
        try:
            result = revise(
                LyricsRevisionRequest(
                    source_title=source.title,
                    source_language=source.language,
                    source_sections=source_sections,
                    source_full_text=source.full_text,
                    instruction=request.instruction,
                    preserve_structure=request.preserve_structure,
                )
            )
        except LyricsError:
            raise
        except Exception as exc:
            logger.exception(
                "lyrics_revision_provider_failed provider=%s error_type=%s",
                self.generator.provider,
                type(exc).__name__,
            )
            raise LyricsRevisionError() from exc

        validation_started_at = time.perf_counter()
        validation = validate_lyrics(result.full_text, source.language)
        validation_time = time.perf_counter() - validation_started_at
        generated_structure = tuple(
            section.section_type for section in validation.sections
        )
        if (
            not validation.valid
            or not result.sections
            or (
                request.preserve_structure
                and generated_structure != tuple(source.structure)
            )
        ):
            raise LyricsOutputInvalidError()

        source_hash = _content_hash(source.full_text)
        result_hash = _content_hash(validation.normalized_lyrics)
        metadata = {
            **result.metadata,
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
            "language": source.language,
            "revision": True,
            "source_version": source.version,
            "version": source.version + 1,
            "preserve_structure": request.preserve_structure,
            "revision_instruction_hash": _content_hash(request.instruction),
            "source_hash": source_hash,
            "result_hash": result_hash,
            "generation_time_seconds": result.generation_time_seconds,
            "validation_time_seconds": validation_time,
            "warnings": list(validation.warnings),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        values: dict[str, object] = {
            "parent_id": source.id,
            "version": source.version + 1,
            "revision_instruction": request.instruction,
            "source_hash": source_hash,
            "result_hash": result_hash,
            "title": result.title,
            "language": source.language,
            "topic": source.topic,
            "genre": source.genre,
            "mood": source.mood,
            "keywords": source.keywords,
            "structure": list(generated_structure),
            "sections_data": [
                {
                    "section_type": section.section_type,
                    "lines": list(section.lines),
                }
                for section in validation.sections
            ],
            "full_text": validation.normalized_lyrics,
            "provider": result.provider,
            "model_name": result.model_name,
            "model_version": result.model_version,
            "status": "REVISED",
            "metadata_payload": metadata,
        }
        document = self._persist(values, metadata, started_at)
        logger.info(
            "lyrics_revision_finished provider=%s version=%s duration_ms=%s",
            result.provider,
            document.version,
            round((time.perf_counter() - started_at) * 1_000, 2),
        )
        return document

    def _persist(
        self,
        values: dict[str, object],
        metadata: dict[str, object],
        started_at: float,
    ) -> LyricsDocument:
        storage_started_at = time.perf_counter()
        with self.session_factory() as session:
            repository = LyricsRepository(session)
            document = repository.create(values)
            final_metadata = {
                **metadata,
                "created_at": document.created_at.isoformat(),
                "storage_time_seconds": time.perf_counter() - storage_started_at,
                "total_service_time_seconds": time.perf_counter() - started_at,
            }
            document = repository.update_metadata(document, final_metadata)
            session.expunge(document)
        return document

    def get(self, lyrics_id: str) -> LyricsDocument:
        with self.session_factory() as session:
            document = LyricsRepository(session).get(lyrics_id)
            if document is None:
                raise ResourceNotFoundError("가사 문서")
            session.expunge(document)
            return document

    def validate(self, request: LyricsValidationRequest) -> LyricsValidationResult:
        started_at = time.perf_counter()
        result = validate_lyrics(request.raw_lyrics, request.language)
        logger.info(
            "lyrics_validation_finished language=%s valid=%s duration_ms=%s",
            request.language,
            result.valid,
            round((time.perf_counter() - started_at) * 1_000, 2),
        )
        return result

    def delete(self, lyrics_id: str) -> None:
        with self.session_factory() as session:
            repository = LyricsRepository(session)
            document = repository.get(lyrics_id)
            if document is None:
                raise ResourceNotFoundError("가사 문서")
            if repository.has_children(lyrics_id):
                raise LyricsRevisionError(
                    "수정 이력이 있는 원본 문서는 삭제할 수 없습니다."
                )
            repository.delete(document)
        logger.info("lyrics_document_deleted lyrics_id=%s", lyrics_id)


def _content_hash(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()
