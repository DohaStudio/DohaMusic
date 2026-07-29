"""Synchronous lyrics generation, validation, retrieval, and deletion use cases."""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.exceptions import ResourceNotFoundError
from backend.core.logging import get_logger
from backend.lyrics.errors import (
    LyricsError,
    LyricsGenerationError,
    LyricsOutputInvalidError,
)
from backend.lyrics.interfaces import LyricsGenerationRequest, LyricsGenerator
from backend.lyrics.validator import LyricsValidationResult, validate_lyrics
from backend.models.lyrics_document import LyricsDocument
from backend.repositories.lyrics_repository import LyricsRepository
from backend.schemas.lyrics import LyricsCreate, LyricsValidationRequest

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
        service_started_at = time.perf_counter()
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
        storage_started_at = time.perf_counter()
        with self.session_factory() as session:
            repository = LyricsRepository(session)
            document = repository.create(values)
            storage_time = time.perf_counter() - storage_started_at
            final_metadata = {
                **metadata,
                "created_at": document.created_at.isoformat(),
                "storage_time_seconds": storage_time,
                "total_service_time_seconds": time.perf_counter() - service_started_at,
            }
            document = repository.update_metadata(document, final_metadata)
            session.expunge(document)
        logger.info(
            "lyrics_generation_finished lyrics_id=%s provider=%s duration_ms=%s",
            document.id,
            result.provider,
            round((time.perf_counter() - service_started_at) * 1_000, 2),
        )
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
            repository.delete(document)
        logger.info("lyrics_document_deleted lyrics_id=%s", lyrics_id)
