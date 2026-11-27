"""Pydantic response models for KuralGPT."""

from pydantic import BaseModel, ConfigDict


class KuralRecord(BaseModel):
    """Represent a legacy Kural record or an extracted document."""

    model_config = ConfigDict(extra="allow")

    id: str

    # Legacy records use single values; extracted documents use lists.
    kural_no: int | list[str] | None = None
    paal: str | list[str] | None = None
    adhikaram: str | list[str] | None = None
    theme: str | list[str] | None = None

    # Legacy Thirukkural fields
    couplet_tamil: str | None = None
    meaning_tamil: str | None = None
    commentary_tamil: str | None = None
    meaning_english: str | None = None

    # Extracted document metadata
    doc_kind: str | None = None
    year: int | None = None
    language: str | None = None
    summary: str | None = None
    topics: list[str] | None = None


class DocumentListResponse(BaseModel):
    """Represent a paginated list of documents."""

    total: int
    limit: int
    offset: int
    items: list[KuralRecord]


class PageResponse(BaseModel):
    """Represent one parsed document page."""

    document_id: str
    page_no: int
    text: str
    headings: list[str]
