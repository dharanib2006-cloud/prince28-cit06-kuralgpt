"""Document listing, searching, and retrieval endpoints."""

from fastapi import APIRouter, Depends, Query

from kuralgpt.api.deps import get_document_store
from kuralgpt.api.errors import ApiError
from kuralgpt.schemas import DocumentListResponse, KuralRecord
from kuralgpt.store import DocumentStore

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    kural_no: int | None = Query(default=None, ge=1, le=1330),
    store: DocumentStore = Depends(get_document_store),
) -> dict:
    """List documents with optional search, Kural number filter, and pagination."""

    records = store.records

    if kural_no is not None:
        records = [record for record in records if record.get("kural_no") == kural_no]

    if q:
        query = q.casefold().strip()
        searchable_fields = (
            "title",
            "couplet_tamil",
            "meaning_tamil",
            "meaning_english",
            "adhikaram",
            "paal",
            "theme",
        )

        records = [
            record
            for record in records
            if any(query in str(record.get(field, "")).casefold() for field in searchable_fields)
        ]

    total = len(records)
    records = records[offset : offset + limit]

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": records,
    }


@router.get("/{document_id}", response_model=KuralRecord)
def get_document(
    document_id: str,
    store: DocumentStore = Depends(get_document_store),
) -> dict:
    """Retrieve one document using its ID."""
    record = store.get_record(document_id)

    if record is None:
        raise ApiError(
            status_code=404,
            title="Not Found",
            detail=f"No document found with ID '{document_id}'.",
        )

    return record
