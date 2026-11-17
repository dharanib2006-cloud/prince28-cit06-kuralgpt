"""Document listing, searching, and retrieval endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, Query

from kuralgpt.api.deps import get_document_store
from kuralgpt.api.errors import ApiError
from kuralgpt.store import DocumentStore

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.get("")
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    store: DocumentStore = Depends(get_document_store),
) -> dict[str, Any]:
    """List documents with optional text search and pagination."""
    if q:
        records = store.search_records(q)
        total = len(records)
        records = records[offset : offset + limit]
    else:
        total = len(store.records)
        records = store.list_records(limit=limit, offset=offset)

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": records,
    }


@router.get("/{document_id}")
def get_document(
    document_id: str,
    store: DocumentStore = Depends(get_document_store),
) -> dict[str, Any]:
    """Retrieve one document using its ID."""
    record = store.get_record(document_id)

    if record is None:
        raise ApiError(
            status_code=404,
            title="Document Not Found",
            detail=f"No document found with ID '{document_id}'.",
        )

    return record
