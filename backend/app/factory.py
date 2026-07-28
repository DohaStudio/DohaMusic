"""FastAPI application composition root."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request, Response

from backend.ai.factory import create_music_generator
from backend.api.exception_handlers import register_exception_handlers
from backend.api.router import api_router
from backend.core.config import Settings, get_settings
from backend.core.logging import configure_logging, get_logger
from backend.db.migrations import upgrade_database
from backend.db.session import create_session_factory
from backend.services.generation_service import GenerationService
from backend.services.voice_profile_service import VoiceProfileService
from backend.storage.service import StorageService
from backend.workers.dispatcher import ThreadPoolJobDispatcher
from backend.workers.generation_worker import GenerationWorker

logger = get_logger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build an application with replaceable infrastructure dependencies."""

    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        storage = StorageService(resolved_settings.storage_root)
        storage.ensure_layout()
        upgrade_database(resolved_settings.database_url)

        session_factory = create_session_factory(resolved_settings.database_url)
        music_generator = create_music_generator(resolved_settings, storage)
        logger.info(
            "provider_configured provider=%s model=%s",
            resolved_settings.music_generator,
            music_generator.model_name,
        )
        worker = GenerationWorker(
            session_factory=session_factory,
            music_generator=music_generator,
            storage=storage,
        )
        dispatcher = ThreadPoolJobDispatcher(
            worker=worker,
            max_workers=resolved_settings.worker_max_threads,
        )

        app.state.settings = resolved_settings
        app.state.session_factory = session_factory
        app.state.storage = storage
        app.state.worker = worker
        app.state.dispatcher = dispatcher
        app.state.generation_service = GenerationService(
            session_factory=session_factory,
            dispatcher=dispatcher,
        )
        app.state.voice_profile_service = VoiceProfileService(
            session_factory=session_factory,
        )
        logger.info("application_started")
        try:
            yield
        finally:
            dispatcher.shutdown()
            logger.info("application_stopped")

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    register_exception_handlers(app)
    app.include_router(api_router)

    @app.middleware("http")
    async def log_request(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started_at = time.perf_counter()
        logger.info(
            "request_started method=%s path=%s", request.method, request.url.path
        )
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "request_failed method=%s path=%s",
                request.method,
                request.url.path,
            )
            raise
        elapsed_ms = round((time.perf_counter() - started_at) * 1_000, 2)
        logger.info(
            "request_finished method=%s path=%s status=%s duration_ms=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    return app
