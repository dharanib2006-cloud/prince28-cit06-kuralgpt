import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError

from kuralgpt.api.deps import create_gateway
from kuralgpt.api.errors import (
    ApiError,
    api_error_handler,
    validation_error_handler,
)
from kuralgpt.api.middleware import RequestContextMiddleware
from kuralgpt.api.routes import chat, documents, health, llm, stats
from kuralgpt.api.routes.chat import load_prompt
from kuralgpt.config import Settings, get_settings
from kuralgpt.db.session import get_engine
from kuralgpt.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = get_settings()

    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = get_engine()
        app.state.database_engine = engine

        app.state.system_prompt = load_prompt(
            settings.prompts_dir,
            "chat_system_v1",
        )

        app.state.classify_prompt = load_prompt(
            settings.prompts_dir,
            "classify_v4",
        )

        app.state.llm_gateway = create_gateway(settings)

        logger.info(
            "Database connection pool at startup: %s",
            engine.pool.status(),
        )

        yield

        await engine.dispose()

    app = FastAPI(
        title="KuralGPT API",
        description="A Thirukkural companion for teachers.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.state.request_count = 0

    @app.middleware("http")
    async def log_pool_after_50_requests(
        request: Request,
        call_next,
    ):
        response = await call_next(request)

        app.state.request_count += 1

        if app.state.request_count == 50:
            engine = getattr(app.state, "database_engine", None)

            if engine is not None:
                logger.info(
                    "Database connection pool after 50 requests: %s",
                    engine.pool.status(),
                )

        return response

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )

    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(stats.router)
    app.include_router(chat.router, prefix="/v1")
    app.include_router(llm.router)

    return app
