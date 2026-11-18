"""Dependencies shared by KuralGPT API routes."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy.orm import Session

from kuralgpt.config import Settings, get_settings
from kuralgpt.database import get_session_factory
from kuralgpt.store import DocumentStore


def get_app_settings() -> Settings:
    """Provide application settings to API routes."""
    return get_settings()


def get_document_store(request: Request) -> DocumentStore:
    """Provide the document store created during application startup."""
    return request.app.state.document_store


def get_db_session() -> Generator[Session, None, None]:
    """Provide a PostgreSQL session to API routes."""
    session_factory = get_session_factory()

    with session_factory() as session:
        yield session
