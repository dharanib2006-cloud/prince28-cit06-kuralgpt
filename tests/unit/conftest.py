import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from kuralgpt.api.deps import get_db_session
from kuralgpt.api.main import create_app
from kuralgpt.config import Settings

SAMPLE = [
    {
        "id": "001",
        "kural_no": 1,
        "paal": "\u0b85\u0bb1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd",
        "adhikaram": "Example chapter",
        "couplet_tamil": "Sample couplet",
        "meaning_tamil": None,
        "commentary_tamil": "Test commentary",
        "meaning_english": "Test English meaning",
        "theme": None,
        "title": "Alpha guideline",
        "year": 2023,
        "published_on": "2023-01-01",
    },
    {
        "id": "002",
        "kural_no": 2,
        "paal": "\u0b85\u0bb1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd",
        "adhikaram": "Example chapter",
        "couplet_tamil": "Sample couplet",
        "meaning_tamil": None,
        "commentary_tamil": "Test commentary",
        "meaning_english": "Test English meaning",
        "theme": None,
        "title": "Beta circular",
        "year": 2024,
        "published_on": "2024-01-01",
    },
    {
        "id": "003",
        "kural_no": 3,
        "paal": "\u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0baa\u0bbe\u0bb2\u0bcd",
        "adhikaram": "Example chapter",
        "couplet_tamil": "Sample couplet",
        "meaning_tamil": None,
        "commentary_tamil": "Test commentary",
        "meaning_english": "Test English meaning",
        "theme": None,
        "title": "Gamma notice",
        "year": 2025,
        "published_on": "2025-01-01",
    },
]


@pytest.fixture
def data_file(tmp_path):
    path = tmp_path / "records.json"
    path.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def client(data_file, monkeypatch):
    """API client with mocked asynchronous repository and database."""

    async def fake_list_documents(
        session,
        limit=20,
        offset=0,
        q=None,
        kural_no=None,
        paal=None,
        adhikaram=None,
        language=None,
        commentator=None,
        sort="id",
    ):
        records = SAMPLE.copy()

        if kural_no is not None:
            records = [r for r in records if r["kural_no"] == kural_no]
        if paal:
            records = [r for r in records if r["paal"] == paal]
        if adhikaram:
            records = [r for r in records if r["adhikaram"] == adhikaram]
        if q:
            term = q.lower()
            records = [r for r in records if term in json.dumps(r, ensure_ascii=False).lower()]

        if sort == "title":
            records.sort(key=lambda r: r["title"].lower())
        elif sort == "-published_on":
            records.sort(
                key=lambda r: r["published_on"],
                reverse=True,
            )

        return records[offset : offset + limit], len(records)

    async def fake_get_document(session, document_id):
        return next(
            (record for record in SAMPLE if record["id"] == document_id),
            None,
        )

    async def fake_get_document_page(session, document_id, page_no):
        if document_id == "001" and page_no == 2:
            return {
                "document_id": document_id,
                "page_no": page_no,
                "text": "Sample page text for testing.",
                "headings": ["Chapter 1", "Section 2"],
            }
        return None

    monkeypatch.setattr(
        "kuralgpt.api.routes.documents.list_documents",
        fake_list_documents,
    )
    monkeypatch.setattr(
        "kuralgpt.api.routes.documents.get_document",
        fake_get_document,
    )
    monkeypatch.setattr(
        "kuralgpt.api.routes.documents.get_document_page",
        fake_get_document_page,
    )

    mock_session = AsyncMock()
    mock_session.scalar.return_value = len(SAMPLE)
    mock_session.scalars.return_value = SimpleNamespace(
        all=lambda: [record["paal"] for record in SAMPLE]
    )

    async def override_get_db_session():
        yield mock_session

    settings = Settings(app_env="ci", data_file=data_file)
    app = create_app(settings)
    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
