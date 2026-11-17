"""Health and readiness endpoints."""

from fastapi import APIRouter, Depends, HTTPException

from kuralgpt.api.deps import get_document_store
from kuralgpt.store import DocumentStore

router = APIRouter(tags=["health"])

MINIMUM_RECORDS = 20


@router.get("/health")
def health() -> dict[str, str]:
    """Return basic application health."""
    return {"status": "ok"}


@router.get("/ready")
def ready(
    store: DocumentStore = Depends(get_document_store),
) -> dict:
    """Check whether enough application data is available."""
    records_count = len(store.records)

    if not store.loaded or records_count < MINIMUM_RECORDS:
        raise HTTPException(
            status_code=503,
            detail=(
                f"At least {MINIMUM_RECORDS} records are required. "
                f"Currently available: {records_count}."
            ),
        )

    return {
        "status": "ready",
        "records_count": records_count,
        "checks": {
            "records_loaded": True,
        },
    }
