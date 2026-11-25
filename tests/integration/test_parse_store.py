import pymupdf
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from kuralgpt.ingest.parse import ParseError, parse_file
from kuralgpt.ingest.store import (
    record_parse_failure,
    store_parsed_document,
)
from kuralgpt.models import Document, Page


def test_store_parsed_document(clean_database, tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text(
        "First paragraph.\n\nSecond paragraph.",
        encoding="utf-8",
    )
    parsed = parse_file(path)

    engine = create_engine(clean_database)
    try:
        with Session(engine) as session:
            document = store_parsed_document(session, path, parsed)
            session.commit()

            assert document.id is not None

            saved_pages = session.scalars(select(Page).where(Page.document_id == document.id)).all()

            assert len(saved_pages) == len(parsed.pages)
            assert saved_pages[0].text
    finally:
        engine.dispose()


def test_store_same_document_twice_without_duplicates(clean_database, tmp_path):
    path = tmp_path / "repeat.txt"
    path.write_text("Original content.", encoding="utf-8")

    engine = create_engine(clean_database)
    try:
        with Session(engine) as session:
            first_parsed = parse_file(path)
            first = store_parsed_document(session, path, first_parsed)
            session.commit()

            document_id = first.id

            path.write_text("Updated content.", encoding="utf-8")
            second_parsed = parse_file(path)
            second = store_parsed_document(session, path, second_parsed)
            session.commit()

            assert second.id == document_id

            document_count = session.scalar(select(func.count()).select_from(Document))
            page_count = session.scalar(
                select(func.count()).select_from(Page).where(Page.document_id == document_id)
            )

            saved_page = session.scalar(select(Page).where(Page.document_id == document_id))

            assert document_count == 1
            assert page_count == len(second_parsed.pages)
            assert "Updated content." in saved_page.text
    finally:
        engine.dispose()


def test_record_parse_failure_and_increment_attempts(clean_database, tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{invalid json}", encoding="utf-8")

    try:
        parse_file(path)
    except ParseError as error:
        parse_error = error
    else:
        raise AssertionError("Expected parsing to fail")

    engine = create_engine(clean_database)
    try:
        with Session(engine) as session:
            first = record_parse_failure(session, path, parse_error)
            session.commit()

            assert first.attempts == 1

            second = record_parse_failure(session, path, parse_error)
            session.commit()

            assert second.id == first.id
            assert second.attempts == 2
    finally:
        engine.dispose()


def test_store_scanned_pages_in_document_metadata(clean_database, tmp_path):
    path = tmp_path / "scanned_pages.pdf"

    pdf = pymupdf.open()

    page1 = pdf.new_page()
    page1.insert_text(
        (72, 72),
        "This is the first normal text page with sufficient content.",
    )

    page2 = pdf.new_page()
    page2.insert_text(
        (72, 72),
        "This is the second normal text page with sufficient content.",
    )

    # Third page has no extractable text.
    pdf.new_page()

    pdf.save(path)
    pdf.close()

    parsed = parse_file(path)

    engine = create_engine(clean_database)
    try:
        with Session(engine) as session:
            document = store_parsed_document(session, path, parsed)
            session.commit()

            saved_document = session.get(Document, document.id)

            assert saved_document is not None
            assert saved_document.metadata_["scanned_pages"] == [3]
    finally:
        engine.dispose()
