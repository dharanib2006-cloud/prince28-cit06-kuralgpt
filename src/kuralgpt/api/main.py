"""KuralGPT FastAPI application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from kuralgpt.api.errors import ApiError, api_error_handler
from kuralgpt.api.middleware import RequestContextMiddleware
from kuralgpt.api.routes import documents, health
from kuralgpt.config import get_settings
from kuralgpt.logging_setup import configure_logging
from kuralgpt.store import DocumentStore


def create_app() -> FastAPI:
    """Create and configure the KuralGPT application."""
    settings = get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = DocumentStore(settings.data_file)
        store.load()
        app.state.document_store = store
        yield

    app = FastAPI(
        title="KuralGPT API",
        description="A Thirukkural companion for teachers.",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_middleware(RequestContextMiddleware)

    app.include_router(health.router)
    app.include_router(documents.router)

    return app
