"""Tests for the document ingestion API."""

from fastapi.testclient import TestClient

from kuralgpt.workers.queue import IngestQueue

ADMIN_HEADERS = {"Authorization": "Bearer test-admin-token"}


def test_ingest_requires_admin(client: TestClient):
    response = client.post("/v1/ingest", json={"limit": 2})

    assert response.status_code == 401


def test_ingest_queues_records(client: TestClient, monkeypatch):
    records = [
        {"url": "https://example.com/one.pdf", "path": "one.pdf"},
        {"url": "https://example.com/two.pdf", "path": "two.pdf"},
    ]

    monkeypatch.setattr(
        "kuralgpt.api.routes.ingest.plan",
        lambda *args, **kwargs: records,
    )

    response = client.post(
        "/v1/ingest",
        json={"limit": 2},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 202
    assert response.json()["queued"] == 2
    assert response.json()["job_id"] == "test-job-1"
    assert client.app.state.fake_ingest_queue.queued_item_ids == [1, 2]
    assert client.app.state.fake_ingest_repository.created_records == records


def test_ingest_returns_empty_when_nothing_to_do(client: TestClient, monkeypatch):
    monkeypatch.setattr(
        "kuralgpt.api.routes.ingest.plan",
        lambda *args, **kwargs: [],
    )

    response = client.post(
        "/v1/ingest",
        json={},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["queued"] == 0
    assert response.json()["job_id"] is None


def test_ingest_retries_failed_records(client: TestClient):
    repository = client.app.state.fake_ingest_repository
    repository.records = [{"url": "https://example.com/failed.pdf", "path": "failed.pdf"}]

    response = client.post(
        "/v1/ingest",
        json={"retry_failed": True, "limit": 1},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 202
    assert response.json()["queued"] == 1
    assert repository.created_records == repository.records


def test_ingest_progress_returns_job(client: TestClient):
    expected = {
        "job_id": "test-job-1",
        "requested": 1,
        "counts": {
            "queued": 1,
            "running": 0,
            "completed": 0,
            "skipped": 0,
            "failed": 0,
        },
        "items": [],
    }
    client.app.state.fake_ingest_repository.progress_result = expected

    response = client.get("/v1/ingest/test-job-1")

    assert response.status_code == 200
    assert response.json() == expected


def test_ingest_progress_returns_404_for_unknown_job(client: TestClient):
    response = client.get("/v1/ingest/unknown-job")

    assert response.status_code == 404


def test_ingest_dead_letter_returns_failed_items(client: TestClient):
    expected = [
        {
            "id": 10,
            "job_id": "test-job-1",
            "error": "Parsing failed",
        }
    ]
    client.app.state.fake_ingest_repository.dead_letter_items = expected

    response = client.get("/v1/ingest/dead-letter?limit=10")

    assert response.status_code == 200
    assert response.json() == {"count": 1, "items": expected}


def test_ingest_passes_source_and_limit_to_planner(
    client: TestClient,
    monkeypatch,
):
    received = {}

    def fake_plan(manifest, known_ids, *, source="", limit=20):
        received["source"] = source
        received["limit"] = limit
        return []

    monkeypatch.setattr("kuralgpt.api.routes.ingest.plan", fake_plan)

    response = client.post(
        "/v1/ingest",
        json={"source": "github", "limit": 5},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 200
    assert received == {"source": "github", "limit": 5}


def test_ingest_returns_503_when_redis_is_unavailable(
    client: TestClient,
    monkeypatch,
):
    async def unavailable(cls, redis_url):
        raise ConnectionError("Redis is unavailable")

    monkeypatch.setattr(IngestQueue, "connect", classmethod(unavailable))
    client.app.dependency_overrides.pop(
        "get_ingest_queue",
        None,
    )

    from kuralgpt.api.deps import get_ingest_queue

    client.app.dependency_overrides.pop(get_ingest_queue, None)

    response = client.post(
        "/v1/ingest",
        json={"limit": 1},
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 503
    assert "Redis" in response.json()["detail"]
