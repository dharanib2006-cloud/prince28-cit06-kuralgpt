"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from kuralgpt.api.deps import get_document_store
from kuralgpt.store import DocumentStore

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Return basic application health."""
    return {"status": "ok"}


@router.get("/ready")
def ready(
    store: DocumentStore = Depends(get_document_store),
) -> dict[str, str | int]:
    """Check whether the application data is ready."""
    if not store.loaded:
        raise HTTPException(
            status_code=503,
            detail="Document data is not available.",
        )

    return {
        "status": "ready",
        "records_count": len(store.records),
    }
