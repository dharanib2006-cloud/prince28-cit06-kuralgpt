from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kuralgpt.ingest.parse import ParseError
from kuralgpt.workers import ingest


class FakeSession:
    def __init__(self, item):
        self.item = item

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def get(self, model, item_id):
        return self.item


@pytest.fixture
def worker_context(tmp_path):
    local_file = tmp_path / "sample.pdf"
    local_file.write_bytes(b"sample document")

    item = SimpleNamespace(
        id=1,
        record={
            "url": "https://example.com/sample.pdf",
            "path": str(local_file),
        },
    )

    def session_factory():
        return FakeSession(item)

    return (
        {
            "settings": SimpleNamespace(
                manifest_file=tmp_path / "manifest.jsonl",
                ingest_rpm=12.0,
            ),
            "async_session_factory": session_factory,
            "gateway": object(),
            "ingest_semaphore": __import__("asyncio").Semaphore(2),
            "pace_lock": __import__("asyncio").Lock(),
            "last_llm_call": 0.0,
            "job_try": 1,
        },
        item,
        local_file,
    )


def test_find_local_file(worker_context):
    ctx, item, local_file = worker_context

    result = ingest._find_local_file(
        item.record,
        ctx["settings"].manifest_file,
    )

    assert result == local_file


@pytest.mark.asyncio
async def test_ingest_document_completes_successfully(
    worker_context,
    monkeypatch,
):
    ctx, item, local_file = worker_context

    monkeypatch.setattr(
        ingest,
        "_update_item",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ingest,
        "_wait_for_llm_slot",
        AsyncMock(),
    )
    monkeypatch.setattr(
        ingest,
        "parse_file",
        lambda path: SimpleNamespace(
            pages=[SimpleNamespace(text="Sample page")],
            title="Sample document",
        ),
    )
    monkeypatch.setattr(ingest, "_store_document", lambda *args: 42)
    monkeypatch.setattr(
        ingest,
        "get_document",
        lambda document_id: SimpleNamespace(id=document_id),
    )
    monkeypatch.setattr(ingest, "document_text", lambda document: "Sample text")
    monkeypatch.setattr(ingest, "load_prompt", lambda *args: "Test prompt")
    monkeypatch.setattr(
        ingest,
        "extract",
        AsyncMock(
            return_value=SimpleNamespace(
                metadata=object(),
                error=None,
            )
        ),
    )

    def save_mock(*args):
        return None

    monkeypatch.setattr(ingest, "save", save_mock)

    result = await ingest.ingest_document(ctx, 1)

    assert result["status"] == "completed"
    assert result["item_id"] == 1
    assert result["document_id"] == 42
    assert result["pages"] == 1


@pytest.mark.asyncio
async def test_ingest_document_missing_item_raises(monkeypatch):
    class MissingSession(FakeSession):
        async def get(self, model, item_id):
            return None

    ctx = {
        "settings": SimpleNamespace(ingest_rpm=12.0),
        "async_session_factory": lambda: MissingSession(None),
        "ingest_semaphore": __import__("asyncio").Semaphore(2),
    }

    with pytest.raises(ValueError, match="not found"):
        await ingest.ingest_document(ctx, 99)


@pytest.mark.asyncio
async def test_ingest_document_records_parse_failure(
    worker_context,
    monkeypatch,
):
    ctx, item, local_file = worker_context

    monkeypatch.setattr(ingest, "_update_item", AsyncMock())
    monkeypatch.setattr(
        ingest,
        "parse_file",
        lambda path: (_ for _ in ()).throw(ParseError("invalid", "Cannot parse test document")),
    )

    def record_failure(*args):
        return None

    monkeypatch.setattr(ingest, "_record_failure", record_failure)

    with pytest.raises(ParseError):
        await ingest.ingest_document(ctx, 1)


@pytest.mark.asyncio
async def test_ingest_document_rejects_missing_metadata(
    worker_context,
    monkeypatch,
):
    ctx, item, local_file = worker_context

    monkeypatch.setattr(ingest, "_update_item", AsyncMock())
    monkeypatch.setattr(ingest, "_wait_for_llm_slot", AsyncMock())
    monkeypatch.setattr(
        ingest,
        "parse_file",
        lambda path: SimpleNamespace(
            pages=[SimpleNamespace(text="Sample page")],
            title="Sample document",
        ),
    )
    monkeypatch.setattr(ingest, "_store_document", lambda *args: 42)
    monkeypatch.setattr(
        ingest,
        "get_document",
        lambda document_id: SimpleNamespace(id=document_id),
    )
    monkeypatch.setattr(ingest, "document_text", lambda document: "Sample text")
    monkeypatch.setattr(ingest, "load_prompt", lambda *args: "Test prompt")
    monkeypatch.setattr(
        ingest,
        "extract",
        AsyncMock(
            return_value=SimpleNamespace(
                metadata=None,
                error="Invalid metadata",
            )
        ),
    )

    with pytest.raises(ValueError, match="Invalid metadata"):
        await ingest.ingest_document(ctx, 1)
