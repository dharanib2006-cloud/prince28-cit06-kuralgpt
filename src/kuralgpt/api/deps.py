"""Dependencies shared by KuralGPT API routes."""

from fastapi import Request

from kuralgpt.config import Settings, get_settings
from kuralgpt.store import DocumentStore


def get_app_settings() -> Settings:
    """Provide application settings to API routes."""
    return get_settings()


def get_document_store(request: Request) -> DocumentStore:
    """Provide the document store created during application startup."""
    return request.app.state.document_store
