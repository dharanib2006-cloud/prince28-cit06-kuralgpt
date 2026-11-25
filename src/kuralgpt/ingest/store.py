"""Database storage helpers for parsed documents."""

import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from kuralgpt.ingest.parse import ParsedDoc, ParseError
from kuralgpt.models import Document, Page, ParseFailure


def _file_sha256(path: Path) -> str:
    """Calculate the SHA-256 hash of a file."""
    if not path.is_file():
        return hashlib.sha256(b"").hexdigest()

    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    return sha256.hexdigest()


def store_parsed_document(
    session: Session,
    path: Path,
    parsed: ParsedDoc,
    source_url: str | None = None,
) -> Document:
    """Save a parsed document and its pages to the database."""
    path = Path(path)
    file_hash = _file_sha256(path)
    external_id = f"raw:{hashlib.sha256(path.resolve().as_posix().encode('utf-8')).hexdigest()}"

    document = session.scalar(select(Document).where(Document.external_id == external_id))

    metadata = {
        "path": str(path),
        "parser": parsed.parser,
        "pages": len(parsed.pages),
        "tables": sum(len(page.tables) for page in parsed.pages),
        "scanned_pages": parsed.scanned_pages,
    }

    if document is None:
        document = Document(
            external_id=external_id,
            title=parsed.title,
            source_url=source_url,
            doc_type=parsed.kind,
            sha256=file_hash,
            metadata_=metadata,
        )
        session.add(document)
        session.flush()
    else:
        document.title = parsed.title
        document.source_url = source_url
        document.doc_type = parsed.kind
        document.sha256 = file_hash
        document.metadata_ = metadata

        session.query(Page).filter(Page.document_id == document.id).delete(
            synchronize_session=False
        )

        session.flush()

    for parsed_page in parsed.pages:
        session.add(
            Page(
                document_id=document.id,
                page_no=parsed_page.page_no,
                text=parsed_page.text,
                headings=parsed_page.headings,
            )
        )

    # A successful retry clears the previous failure.
    failure = session.scalar(select(ParseFailure).where(ParseFailure.path == str(path)))

    if failure is not None:
        session.delete(failure)

    session.flush()
    return document


def record_parse_failure(
    session: Session,
    path: Path,
    error: ParseError,
    source_url: str | None = None,
) -> ParseFailure:
    """Record a parsing failure or increment its retry count."""
    path = Path(path)
    path_string = str(path)
    file_hash = _file_sha256(path)

    failure = session.scalar(select(ParseFailure).where(ParseFailure.path == path_string))

    if failure is None:
        failure = ParseFailure(
            path=path_string,
            sha256=file_hash,
            source_url=source_url,
            reason=error.reason,
            detail=error.detail,
            attempts=1,
        )
        session.add(failure)
    else:
        failure.sha256 = file_hash
        failure.source_url = source_url
        failure.reason = error.reason
        failure.detail = error.detail
        failure.attempts += 1

    session.flush()
    return failure
