"""Shared fixtures for KuralGPT API tests."""

import json
from unittest.mock import MagicMock

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
    },
]


@pytest.fixture
def data_file(tmp_path):
    """Create a temporary JSON file containing fake records."""
    path = tmp_path / "records.json"
    path.write_text(json.dumps(SAMPLE, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def client(data_file, monkeypatch):
    """Create a test client with isolated sample data and a mocked database."""

    def fake_list_documents(
        session,
        limit=20,
        offset=0,
        q=None,
        kural_no=None,
        paal=None,
        adhikaram=None,
        language=None,
        commentator=None,
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

        total = len(records)
        return records[offset : offset + limit], total

    def fake_get_document(session, document_id):
        return next(
            (record for record in SAMPLE if record["id"] == document_id),
            None,
        )

    monkeypatch.setattr(
        "kuralgpt.api.routes.documents.list_documents",
        fake_list_documents,
    )
    monkeypatch.setattr(
        "kuralgpt.api.routes.documents.get_document",
        fake_get_document,
    )

    mock_session = MagicMock()
    mock_session.scalar.return_value = len(SAMPLE)
    mock_session.scalars.return_value.all.return_value = [record["paal"] for record in SAMPLE]

    def override_get_db_session():
        yield mock_session

    settings = Settings(app_env="ci", data_file=data_file)
    app = create_app(settings)
    app.dependency_overrides[get_db_session] = override_get_db_session

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
