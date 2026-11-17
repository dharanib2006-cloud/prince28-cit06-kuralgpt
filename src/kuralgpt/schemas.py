"""Pydantic response models for KuralGPT."""

from pydantic import BaseModel, ConfigDict


class KuralRecord(BaseModel):
    """Represent one verified Thirukkural record."""

    model_config = ConfigDict(extra="ignore")

    id: str
    kural_no: int
    paal: str
    adhikaram: str
    couplet_tamil: str
    meaning_tamil: str | None = None
    commentary_tamil: str
    meaning_english: str
    theme: str | None = None


class DocumentListResponse(BaseModel):
    """Represent a paginated list of Kural records."""

    total: int
    limit: int
    offset: int
    items: list[KuralRecord]
