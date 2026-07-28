"""FastAPI application composition root."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
import time

from fastapi import FastAPI, Request, Response

from backend.ai.factory import create_music_generator
from backend.ai.stem_factory import create_stem_separator
from backend.api.exception_handlers import register_exception_handlers
from backend.api.router import api_router
from backend.core.config import Settings, get_settings
from backend.core.logging import configure_logging, get_logger
from backend.db.migrations import upgrade_database
from backend.db.session import create_session_factory
from backend.services.generation_service import GenerationService
from backend.services.stem_service import StemService
from backend.services.voice_profile_service import VoiceProfileService
from backend.storage.service import StorageService
from backend.workers.dispatcher import ThreadPoolJobDispatcher
from backend.workers.generation_worker import GenerationWorker
from backend.workers.stem_worker import StemWorker

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
        stem_separator = create_stem_separator(resolved_settings, storage)
        logger.info(
            "provider_configured provider=%s model=%s",
            resolved_settings.music_generator,
            music_generator.model_name,
        )
        logger.info(
            "stem_provider_configured provider=%s model=%s",
            resolved_settings.stem_provider,
            stem_separator.model_name,
        )
        worker = GenerationWorker(
            session_factory=session_factory,
            music_generator=music_generator,
            storage=storage,
        )
        shared_executor = ThreadPoolExecutor(
            max_workers=resolved_settings.worker_max_threads,
            thread_name_prefix="dohamusic-ai-worker",
        )
        dispatcher = ThreadPoolJobDispatcher(
            worker=worker,
            executor=shared_executor,
        )
        stem_worker = StemWorker(
            session_factory=session_factory,
            stem_separator=stem_separator,
            storage=storage,
        )
        stem_dispatcher = ThreadPoolJobDispatcher(
            worker=stem_worker,
            executor=shared_executor,
        )

        app.state.settings = resolved_settings
        app.state.session_factory = session_factory
        app.state.storage = storage
        app.state.worker = worker
        app.state.dispatcher = dispatcher
        app.state.stem_worker = stem_worker
        app.state.stem_dispatcher = stem_dispatcher
        app.state.generation_service = GenerationService(
            session_factory=session_factory,
            dispatcher=dispatcher,
        )
        app.state.voice_profile_service = VoiceProfileService(
            session_factory=session_factory,
        )
        app.state.stem_service = StemService(
            session_factory=session_factory,
            dispatcher=stem_dispatcher,
        )
        logger.info("application_started")
        try:
            yield
        finally:
            shared_executor.shutdown(wait=True, cancel_futures=False)
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
