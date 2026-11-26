"""Integration tests for metadata extraction and database storage."""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from kuralgpt.llm.doc_meta import DocMeta
from kuralgpt.llm.extract import (
    Extraction,
    get_document,
    pending,
    save,
)
from kuralgpt.llm.gateway import LLMResult
from kuralgpt.models import Document, Page


def test_extract_metadata_store(clean_database, monkeypatch):
    """Test pending documents, document loading, and metadata saving."""
    engine = create_engine(clean_database)

    session_factory = sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )

    monkeypatch.setattr(
        "kuralgpt.llm.extract.get_session_factory",
        lambda: session_factory,
    )

    try:
        with session_factory() as session:
            document = Document(
                external_id="extract-test-document",
                title="Thirukkural Teaching Guidelines",
                source_url="https://example.com/guidelines",
                licence="Test licence",
                doc_type="pdf",
                sha256="extract-test-sha256",
                metadata_={"source": "integration-test"},
            )

            document.pages.append(
                Page(
                    page_no=1,
                    text="Guidelines for teaching Thirukkural and its values.",
                )
            )

            session.add(document)
            session.commit()
            document_id = document.id

        # The new document should be pending extraction.
        pending_ids = pending("v1")

        assert document_id in pending_ids

        # The document and its page text should load correctly.
        loaded = get_document(document_id)

        assert loaded is not None
        assert loaded.title == "Thirukkural Teaching Guidelines"
        assert len(loaded.pages) == 1
        assert "Guidelines for teaching Thirukkural" in loaded.pages[0].text

        # Save valid extracted metadata.
        metadata = DocMeta.model_validate(
            {
                "doc_kind": "guideline",
                "year": 2023,
                "language": "en",
                "summary": ("This document provides guidelines for teaching Thirukkural."),
                "topics": ["education", "thirukkural"],
                "kural_no": ["1"],
                "adhikaram": ["Praise of God"],
                "paal": ["aram"],
                "theme": ["education"],
            }
        )

        result = LLMResult(
            text="{}",
            provider="fake",
            model="fake-model",
            tokens_in=100,
            tokens_out=50,
            latency_ms=20,
            attempts=1,
            fallback_used=False,
            cost_inr=0.01,
        )

        extraction = Extraction(
            metadata=metadata,
            result=result,
            attempts=1,
        )

        save(document_id, extraction, "v1")

        # Verify the saved metadata and preserved original metadata.
        with session_factory() as session:
            saved_document = session.get(Document, document_id)

            assert saved_document is not None
            assert saved_document.metadata_["source"] == "integration-test"
            assert saved_document.metadata_["doc_kind"] == "guideline"
            assert saved_document.metadata_["topics"] == [
                "education",
                "thirukkural",
            ]
            assert saved_document.metadata_["extract"]["prompt"] == "v1"
            assert saved_document.metadata_["extract"]["status"] == "ok"

        # Successfully extracted documents should no longer be pending.
        assert document_id not in pending("v1")

    finally:
        engine.dispose()
