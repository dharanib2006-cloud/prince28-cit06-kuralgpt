"""Extract and validate document metadata using an LLM."""

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlalchemy import or_, select

from kuralgpt.database import get_session_factory
from kuralgpt.llm.doc_meta import DocMeta
from kuralgpt.llm.gateway import LLMGateway, LLMResult
from kuralgpt.models import Document, Page


@dataclass
class Extraction:
    """Result of one metadata extraction attempt."""

    metadata: DocMeta | None
    result: LLMResult | None
    attempts: int
    error: str | None = None


@dataclass
class SimplePage:
    """Page data detached from the database session."""

    page_no: int
    text: str | None


@dataclass
class SimpleDocument:
    """Document data detached from the database session."""

    id: int
    title: str | None
    pages: list[SimplePage]


def parse_metadata(reply: str) -> DocMeta:
    """Parse, normalize, and validate an LLM JSON response."""
    text = reply.strip()

    if text.startswith("```"):
        lines = text.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"Invalid JSON response: {error}") from error

    if not isinstance(data, dict):
        raise ValueError("The response must be one JSON object.")

    # Remove accidental whitespace from field names.
    normalized = {}

    for key, value in data.items():
        clean_key = key.strip() if isinstance(key, str) else key

        if clean_key in normalized:
            raise ValueError(f"Duplicate field after removing whitespace: {clean_key}")

        normalized[clean_key] = value

    # Convert single string values into lists where lists are expected.
    list_fields = {
        "topics",
        "kural_no",
        "adhikaram",
        "paal",
        "theme",
    }

    for field in list_fields:
        value = normalized.get(field)

        if isinstance(value, str):
            normalized[field] = [value]

    try:
        return DocMeta.model_validate(normalized)
    except ValidationError as error:
        raise ValueError(f"Metadata validation failed: {error}") from error


def build_messages(
    prompt: str,
    document_text: str,
    previous_error: str | None = None,
    document_title: str | None = None,
) -> list[dict[str, str]]:
    """Build extraction messages while treating document text as untrusted data."""
    user_content = (
        f"<document_title>\n{document_title or 'Unknown'}\n</document_title>\n"
        f"<document>\n{document_text}\n</document>"
    )

    if previous_error:
        user_content += (
            "\n\nYour previous response was invalid. "
            "Correct the response using this validation feedback:\n"
            f"{previous_error}\n"
            "Return one corrected JSON object only."
        )

    return [
        {"role": "system", "content": prompt},
        {"role": "user", "content": user_content},
    ]


async def extract(
    gateway: LLMGateway,
    prompt: str,
    version: str,
    document_text: str,
    document_title: str | None = None,
    max_attempts: int = 3,
) -> Extraction:
    """Extract document metadata, retrying invalid JSON or metadata."""
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    last_error = None
    last_result = None

    for attempt in range(1, max_attempts + 1):
        result = await gateway.generate(
            build_messages(
                prompt,
                document_text,
                last_error,
                document_title,
            ),
            purpose="extract",
            prompt_version=version,
            temperature=0,
            response_format={"type": "json_object"},
        )

        last_result = result

        try:
            metadata = parse_metadata(result.text)

            return Extraction(
                metadata=metadata,
                result=result,
                attempts=attempt,
            )

        except ValueError as error:
            last_error = str(error)

    return Extraction(
        metadata=None,
        result=last_result,
        attempts=max_attempts,
        error=last_error,
    )


def document_text(document: Any, max_chars: int = 6000) -> str:
    """Combine the first three pages within a character limit."""
    if max_chars < 1:
        raise ValueError("max_chars must be at least 1.")

    pages = sorted(
        document.pages,
        key=lambda page: page.page_no,
    )[:3]

    combined = "\n\n".join(page.text.strip() for page in pages if page.text and page.text.strip())

    return combined[:max_chars]


def pending(
    prompt_version: str,
    limit: int | None = None,
) -> list[int]:
    """Return parsed document IDs that need extraction or retry."""
    session_factory = get_session_factory()

    with session_factory() as session:
        note = Document.metadata_["extract"]

        statement = (
            select(Document.id)
            .where(Document.doc_type != "record")
            .where(
                or_(
                    note["prompt"].astext.is_distinct_from(prompt_version),
                    note["error"].astext.is_not(None),
                )
            )
            .order_by(Document.id)
        )

        if limit is not None:
            statement = statement.limit(limit)

        return list(session.scalars(statement).all())


def failed_documents(limit: int | None = None) -> list[int]:
    """Return document IDs whose latest metadata extraction failed."""
    session_factory = get_session_factory()

    with session_factory() as session:
        note = Document.metadata_["extract"]

        statement = (
            select(Document.id)
            .where(Document.doc_type != "record")
            .where(note["error"].astext.is_not(None))
            .order_by(Document.id)
        )

        if limit is not None:
            statement = statement.limit(limit)

        return list(session.scalars(statement).all())


def save(
    document_id: int,
    extraction: Extraction,
    prompt_version: str,
) -> None:
    """Save extracted metadata without removing existing document metadata."""
    session_factory = get_session_factory()

    with session_factory() as session:
        document = session.get(Document, document_id)

        if document is None:
            raise ValueError(f"Document {document_id} was not found.")

        existing = dict(document.metadata_ or {})

        note: dict[str, Any] = {
            "prompt": prompt_version,
            "attempts": extraction.attempts,
        }

        if extraction.metadata is not None:
            extracted = extraction.metadata.model_dump(mode="json")
            existing.update(extracted)
            note["status"] = "ok"
        else:
            note["status"] = "failed"
            note["error"] = extraction.error or "Unknown extraction error"

        existing["extract"] = note
        document.metadata_ = existing

        session.commit()


def get_document(document_id: int) -> SimpleDocument | None:
    """Load a document and its pages for metadata extraction."""
    session_factory = get_session_factory()

    with session_factory() as session:
        document = session.get(Document, document_id)

        if document is None:
            return None

        pages = session.scalars(
            select(Page).where(Page.document_id == document_id).order_by(Page.page_no)
        ).all()

        return SimpleDocument(
            id=document.id,
            title=document.title,
            pages=[
                SimplePage(
                    page_no=page.page_no,
                    text=page.text,
                )
                for page in pages
            ],
        )
