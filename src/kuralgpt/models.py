"""SQLAlchemy database models."""

from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""


class Document(Base):
    """Document containing a Kural or another source record."""

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    licence: Mapped[str | None] = mapped_column(String(100), nullable=True)
    doc_type: Mapped[str] = mapped_column(String(50), nullable=False, default="kural")
    published_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    document_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)


class Page(Base):
    """Searchable text belonging to a document."""

    __tablename__ = "pages"

    doc_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    page_no: Mapped[int] = mapped_column(Integer, primary_key=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
