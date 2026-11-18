"""Database queries for KuralGPT documents."""

from typing import Any

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.orm import Session

from kuralgpt.models import Document


def list_documents(
    session: Session,
    limit: int = 20,
    offset: int = 0,
    q: str | None = None,
    kural_no: int | None = None,
    paal: str | None = None,
    adhikaram: str | None = None,
    language: str | None = None,
    commentator: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """List documents with optional filters and pagination."""

    filters = []

    if kural_no is not None:
        filters.append(
            cast(Document.document_metadata["kural_no"].as_string(), String) == str(kural_no)
        )

    if paal:
        filters.append(Document.document_metadata["paal"].as_string() == paal)

    if adhikaram:
        filters.append(Document.document_metadata["adhikaram"].as_string() == adhikaram)

    if language:
        filters.append(Document.document_metadata["languages"].contains([language]))

    if commentator:
        filters.append(Document.document_metadata["commentator"].as_string() == commentator)

    if q:
        search_term = f"%{q.strip()}%"
        searchable_fields = [
            Document.title,
            Document.document_metadata["couplet_tamil"].as_string(),
            Document.document_metadata["meaning_tamil"].as_string(),
            Document.document_metadata["meaning_english"].as_string(),
            Document.document_metadata["commentary_tamil"].as_string(),
            Document.document_metadata["adhikaram"].as_string(),
            Document.document_metadata["paal"].as_string(),
            Document.document_metadata["theme"].as_string(),
        ]

        filters.append(
            or_(*[cast(field, String).ilike(search_term) for field in searchable_fields])
        )

    count_statement = select(func.count()).select_from(Document)

    if filters:
        count_statement = count_statement.where(*filters)

    total = session.scalar(count_statement) or 0

    statement = select(Document).where(*filters).order_by(Document.id).offset(offset).limit(limit)

    documents = session.scalars(statement).all()

    records = []

    for document in documents:
        record = dict(document.document_metadata)
        record["id"] = document.id
        records.append(record)

    return records, total


def get_document(
    session: Session,
    document_id: str,
) -> dict[str, Any] | None:
    """Retrieve one document by its ID."""

    document = session.get(Document, document_id)

    if document is None:
        return None

    record = dict(document.document_metadata)
    record["id"] = document.id

    return record
