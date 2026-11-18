from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.models import Document


def document_to_record(document: Document) -> dict[str, Any]:
    record = dict(document.metadata_)
    record["id"] = document.external_id
    return record


async def list_documents(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
    kural_no: int | None = None,
    paal: str | None = None,
    adhikaram: str | None = None,
    language: str | None = None,
    commentator: str | None = None,
) -> tuple[list[dict[str, Any]], int]:

    filters = []
    metadata = Document.metadata_

    if kural_no is not None:
        filters.append(cast(metadata["kural_no"].as_string(), String) == str(kural_no))

    if paal:
        filters.append(metadata["paal"].as_string() == paal)

    if adhikaram:
        filters.append(metadata["adhikaram"].as_string() == adhikaram)

    if language:
        filters.append(metadata["languages"].contains([language]))

    if commentator:
        filters.append(metadata["commentator"].as_string() == commentator)

    if q:
        term = f"%{q.strip()}%"
        fields = [
            Document.title,
            metadata["couplet_tamil"].as_string(),
            metadata["meaning_tamil"].as_string(),
            metadata["meaning_english"].as_string(),
            metadata["commentary_tamil"].as_string(),
            metadata["adhikaram"].as_string(),
            metadata["paal"].as_string(),
            metadata["theme"].as_string(),
        ]
        filters.append(or_(*[cast(field, String).ilike(term) for field in fields]))

    count_stmt = select(func.count()).select_from(Document)

    if filters:
        count_stmt = count_stmt.where(*filters)

    total = await session.scalar(count_stmt) or 0

    stmt = select(Document).where(*filters).order_by(Document.id).offset(offset).limit(limit)

    result = await session.scalars(stmt)

    return [document_to_record(doc) for doc in result.all()], total


async def get_document(
    session: AsyncSession,
    document_id: str,
) -> dict[str, Any] | None:

    stmt = select(Document).where(Document.external_id == document_id)

    document = await session.scalar(stmt)

    return document_to_record(document) if document is not None else None
