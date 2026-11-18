"""Document listing, searching, and retrieval endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from kuralgpt.api.deps import get_db_session
from kuralgpt.api.errors import ApiError
from kuralgpt.repository import get_document, list_documents
from kuralgpt.schemas import DocumentListResponse, KuralRecord

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
def list_documents_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    kural_no: int | None = Query(default=None, ge=1, le=1330),
    paal: str | None = Query(default=None),
    adhikaram: str | None = Query(default=None),
    language: str | None = Query(default=None),
    commentator: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> dict:
    """List PostgreSQL documents with filters and pagination."""

    records, total = list_documents(
        session=session,
        limit=limit,
        offset=offset,
        q=q,
        kural_no=kural_no,
        paal=paal,
        adhikaram=adhikaram,
        language=language,
        commentator=commentator,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": records,
    }


@router.get("/{document_id}", response_model=KuralRecord)
def get_document_endpoint(
    document_id: str,
    session: Session = Depends(get_db_session),
) -> dict:
    """Retrieve one PostgreSQL document using its ID."""

    record = get_document(session, document_id)

    if record is None:
        raise ApiError(
            status_code=404,
            title="Not Found",
            detail=f"No document found with ID '{document_id}'.",
        )

    return record
