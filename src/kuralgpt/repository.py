from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.models import Document, Page


def document_to_record(document: Document) -> dict[str, Any]:
    record = dict(document.metadata_ or {})
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
    sort: str = "id",
    doc_kind: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    filters = []
    metadata = Document.metadata_

    # Filter extracted documents by their document kind.
    if doc_kind:
        filters.append(metadata["doc_kind"].as_string() == doc_kind)

    # Support both legacy Kural records and extracted metadata.
    if kural_no is not None:
        filters.append(
            or_(
                Document.kural_no == kural_no,
                metadata["kural_no"].contains([str(kural_no)]),
                metadata["kural_no"].as_string() == str(kural_no),
            )
        )

    if paal:
        filters.append(
            or_(
                metadata["paal"].as_string() == paal,
                metadata["paal"].contains([paal]),
            )
        )

    if adhikaram:
        filters.append(
            or_(
                metadata["adhikaram"].as_string() == adhikaram,
                metadata["adhikaram"].contains([adhikaram]),
            )
        )

    if language:
        filters.append(
            or_(
                metadata["languages"].contains([language]),
                metadata["language"].as_string() == language,
            )
        )

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
            metadata["summary"].as_string(),
            metadata["topics"].as_string(),
        ]
        filters.append(or_(*[cast(field, String).ilike(term) for field in fields]))

    count_stmt = select(func.count()).select_from(Document)

    if filters:
        count_stmt = count_stmt.where(*filters)

    total = await session.scalar(count_stmt) or 0

    sort_options = {
        "id": Document.id.asc(),
        "title": Document.title.asc(),
        "-published_on": Document.published_on.desc().nulls_last(),
    }
    ordering = sort_options.get(sort, Document.id.asc())

    stmt = select(Document).where(*filters).order_by(ordering).offset(offset).limit(limit)

    result = await session.scalars(stmt)

    return [document_to_record(doc) for doc in result.all()], total


async def get_document(
    session: AsyncSession,
    document_id: str,
) -> dict[str, Any] | None:
    stmt = select(Document).where(Document.external_id == document_id)
    document = await session.scalar(stmt)

    return document_to_record(document) if document is not None else None


async def get_document_page(
    session: AsyncSession,
    document_id: str,
    page_no: int,
) -> dict[str, Any] | None:
    stmt = (
        select(Page)
        .join(Document)
        .where(
            Document.external_id == document_id,
            Page.page_no == page_no,
        )
    )

    page = await session.scalar(stmt)

    if page is None:
        return None

    return {
        "document_id": document_id,
        "page_no": page.page_no,
        "text": page.text,
        "headings": page.headings,
    }
