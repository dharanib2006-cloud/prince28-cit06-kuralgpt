from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.api.deps import get_db_session
from kuralgpt.api.errors import ApiError
from kuralgpt.repository import get_document, list_documents
from kuralgpt.schemas import DocumentListResponse, KuralRecord

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.get("", response_model=DocumentListResponse)
async def list_documents_endpoint(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None),
    kural_no: int | None = Query(default=None, ge=1, le=1330),
    paal: str | None = Query(default=None),
    adhikaram: str | None = Query(default=None),
    language: str | None = Query(default=None),
    commentator: str | None = Query(default=None),
    sort: Literal["id", "title", "-published_on"] = Query(default="id"),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    records, total = await list_documents(
        session,
        limit,
        offset,
        q,
        kural_no,
        paal,
        adhikaram,
        language,
        commentator,
        sort,
    )

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": records,
    }


@router.get("/{document_id}", response_model=KuralRecord)
async def get_document_endpoint(
    document_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    record = await get_document(session, document_id)

    if record is None:
        raise ApiError(
            status_code=404,
            title="Not Found",
            detail=f"No document found with ID '{document_id}'.",
        )

    return record
