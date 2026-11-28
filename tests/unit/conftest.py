import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from kuralgpt.api.deps import (
    get_db_session,
    get_gateway,
    get_ingest_queue,
    get_ingest_repository,
    get_manifest,
    get_usage_repository,
)
from kuralgpt.api.main import create_app
from kuralgpt.config import Settings
from kuralgpt.llm.gateway import CircuitBreaker, FakeLLM, LLMResult

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


class FakeChatGateway:
    """Fake gateway for chat and LLM status API tests."""

    def __init__(self):
        self.providers = [
            FakeLLM(name="gemini", model="gemini-test"),
            FakeLLM(name="groq", model="groq-test"),
        ]
        self.breakers = {provider.name: CircuitBreaker() for provider in self.providers}
        self.last_messages = None

    async def generate(self, messages, **kwargs):
        self.last_messages = messages
        return LLMResult(
            text="This is a test answer.",
            provider="fake",
            model="fake-1",
            tokens_in=12,
            tokens_out=8,
            latency_ms=25,
            attempts=1,
            fallback_used=False,
            cost_inr=0.01,
        )

    async def stream(self, messages, **kwargs):
        self.last_messages = messages
        yield "This is "
        yield "a test answer."
        yield LLMResult(
            text="This is a test answer.",
            provider="fake",
            model="fake-1",
            tokens_in=12,
            tokens_out=8,
            latency_ms=25,
            attempts=1,
            fallback_used=False,
            cost_inr=0.01,
        )


class FakeUsageRepository:
    """Fake daily usage records for API tests."""

    async def by_day(self, days=7):
        return [
            {
                "day": "2026-11-25",
                "calls": 4,
                "cost_inr": 0.05,
                "errors": 1,
                "fallbacks": 2,
                "tokens_in": 500,
                "tokens_out": 300,
            }
        ]


class FakeIngestRepository:
    """Fake ingestion database repository for API tests."""

    def __init__(self):
        self.records = []
        self.created_records = []
        self.job_id = "test-job-1"
        self.item_ids = [1, 2]
        self.progress_result = None
        self.dead_letter_items = []

    async def known_ids(self):
        return set()

    async def failed_records(self, limit=2000):
        return self.records[:limit]

    async def create(self, records):
        self.created_records = records
        return self.job_id, self.item_ids[: len(records)]

    async def progress(self, job_id):
        if job_id == self.job_id:
            return self.progress_result
        return None

    async def dead_letter(self, limit=50):
        return self.dead_letter_items[:limit]


class FakeIngestQueue:
    """Fake Redis queue for API tests."""

    def __init__(self):
        self.queued_item_ids = []

    async def put(self, item_ids):
        self.queued_item_ids.extend(item_ids)


class FakeManifest:
    """Fake manifest records for API tests."""

    def __init__(self):
        self.items = []

    def records(self):
        return self.items


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
        doc_kind=None,
    ):
        records = SAMPLE.copy()
        if doc_kind:
            records = [r for r in records if r.get("doc_kind") == doc_kind]

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

    settings = Settings(app_env="ci", data_file=data_file, admin_token="test-admin-token")
    app = create_app(settings)

    fake_gateway = FakeChatGateway()
    app.state.llm_gateway = fake_gateway

    app.dependency_overrides[get_db_session] = override_get_db_session
    app.dependency_overrides[get_gateway] = lambda: fake_gateway
    app.dependency_overrides[get_usage_repository] = lambda: FakeUsageRepository()

    fake_ingest_repository = FakeIngestRepository()
    fake_ingest_queue = FakeIngestQueue()
    fake_manifest = FakeManifest()

    app.dependency_overrides[get_ingest_repository] = lambda: fake_ingest_repository
    app.dependency_overrides[get_ingest_queue] = lambda: fake_ingest_queue
    app.dependency_overrides[get_manifest] = lambda: fake_manifest

    app.state.fake_ingest_repository = fake_ingest_repository
    app.state.fake_ingest_queue = fake_ingest_queue
    app.state.fake_manifest = fake_manifest

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
