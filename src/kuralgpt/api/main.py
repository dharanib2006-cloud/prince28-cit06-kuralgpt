from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from kuralgpt.api.errors import (
    ApiError,
    api_error_handler,
    validation_error_handler,
)
from kuralgpt.api.middleware import RequestContextMiddleware
from kuralgpt.api.routes import documents, health, stats
from kuralgpt.config import Settings, get_settings
from kuralgpt.db.session import get_engine
from kuralgpt.logging_setup import configure_logging


def create_app(settings: Settings | None = None) -> FastAPI:

    if settings is None:
        settings = get_settings()

    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:

        engine = get_engine()
        app.state.database_engine = engine

        yield

        await engine.dispose()

    app = FastAPI(
        title="KuralGPT API",
        description="A Thirukkural companion for teachers.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(
        RequestValidationError,
        validation_error_handler,
    )

    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(documents.router)
    app.include_router(stats.router)

    return app
