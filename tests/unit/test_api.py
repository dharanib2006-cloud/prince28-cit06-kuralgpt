"""Tests for KuralGPT API endpoints and configuration."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import kuralgpt.api.main as main_module
from kuralgpt.api.deps import get_db_session
from kuralgpt.api.main import create_app
from kuralgpt.config import Settings

ARATHUPPAAL = "\u0b85\u0bb1\u0ba4\u0bcd\u0ba4\u0bc1\u0baa\u0bcd\u0baa\u0bbe\u0bb2\u0bcd"
PORUTPAAL = "\u0baa\u0bca\u0bb0\u0bc1\u0b9f\u0bcd\u0baa\u0bbe\u0bb2\u0bcd"


def test_health_is_ok(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_when_at_least_20_records_are_loaded(tmp_path):
    settings = Settings(app_env="ci", data_file=tmp_path / "unused.json")
    mock_session = AsyncMock()
    mock_session.scalar.return_value = 20

    async def override_session():
        yield mock_session

    app = create_app(settings)
    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["records_count"] == 20
    assert response.json()["checks"]["database"] is True


def test_ready_is_503_when_fewer_than_20_records_are_loaded(tmp_path):
    settings = Settings(app_env="ci", data_file=tmp_path / "unused.json")
    mock_session = AsyncMock()
    mock_session.scalar.return_value = 19

    async def override_session():
        yield mock_session

    app = create_app(settings)
    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503


def test_ready_is_503_when_database_is_unavailable(tmp_path):
    settings = Settings(app_env="ci", data_file=tmp_path / "unused.json")
    mock_session = AsyncMock()
    mock_session.execute.side_effect = Exception("Database unavailable")

    async def override_session():
        yield mock_session

    app = create_app(settings)
    app.dependency_overrides[get_db_session] = override_session

    with TestClient(app) as test_client:
        assert test_client.get("/health").status_code == 200
        response = test_client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"]["checks"]["database"] is False


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_search_filters_records(client):
    response = client.get("/v1/documents", params={"q": "beta"})

    assert response.status_code == 200
    assert [record["id"] for record in response.json()["items"]] == ["002"]


def test_filter_by_kural_number(client):
    response = client.get("/v1/documents", params={"kural_no": 2})
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 1
    assert len(body["items"]) == 1
    assert body["items"][0]["id"] == "002"
    assert body["items"][0]["kural_no"] == 2


def test_statistics_returns_total_and_counts_by_paal(client):
    response = client.get("/v1/stats")
    body = response.json()

    assert response.status_code == 200
    assert body["total_records"] == 3
    assert body["counts_by_paal"] == {
        ARATHUPPAAL: 2,
        PORUTPAAL: 1,
    }


def test_get_document_found(client):
    response = client.get("/v1/documents/001")

    assert response.status_code == 200
    assert response.json()["id"] == "001"
    assert response.json()["kural_no"] == 1
    assert response.json()["paal"] == ARATHUPPAAL


def test_missing_document_is_problem_details(client):
    response = client.get("/v1/documents/999")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"

    body = response.json()

    assert body["status"] == 404
    assert body["title"] == "Not Found"
    assert body["request_id"] == response.headers["X-Request-ID"]


def test_bad_limit_is_422_problem(client):
    response = client.get("/v1/documents", params={"limit": 0})

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "query.limit"


def test_request_id_is_echoed(client):
    response = client.get("/health", headers={"X-Request-ID": "abc123"})
    assert response.headers["X-Request-ID"] == "abc123"


def test_app_refuses_to_start_without_app_env(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_filter_by_paal(client):
    response = client.get(
        "/v1/documents",
        params={"paal": ARATHUPPAAL},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2


def test_filter_by_adhikaram(client):
    response = client.get(
        "/v1/documents",
        params={"adhikaram": "Example chapter"},
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3


def test_filter_by_paal_and_adhikaram(client):
    response = client.get(
        "/v1/documents",
        params={
            "paal": ARATHUPPAAL,
            "adhikaram": "Example chapter",
        },
    )
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 2


def test_sort_documents_by_title(client):
    response = client.get(
        "/v1/documents",
        params={"sort": "title"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        "001",
        "002",
        "003",
    ]


def test_sort_documents_by_published_on_descending(client):
    response = client.get(
        "/v1/documents",
        params={"sort": "-published_on"},
    )

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [
        "003",
        "002",
        "001",
    ]


def test_reject_unsupported_sort_field(client):
    response = client.get(
        "/v1/documents",
        params={"sort": "unknown_column"},
    )

    assert response.status_code == 422


def test_create_app_uses_default_settings(monkeypatch):
    settings = Settings(app_env="ci")
    monkeypatch.setattr(main_module, "get_settings", lambda: settings)

    app = create_app()

    assert app.title == "KuralGPT API"


def test_pool_status_is_logged_after_50_requests(monkeypatch):
    settings = Settings(app_env="ci")
    mock_engine = Mock()
    mock_engine.pool.status.return_value = "Pool size: 5"
    mock_engine.dispose = AsyncMock()
    mock_log = Mock()

    monkeypatch.setattr(main_module, "get_engine", lambda: mock_engine)
    monkeypatch.setattr(main_module.logger, "info", mock_log)

    app = create_app(settings)

    with TestClient(app) as test_client:
        for _ in range(50):
            response = test_client.get("/health")
            assert response.status_code == 200

    mock_log.assert_any_call(
        "Database connection pool after 50 requests: %s",
        "Pool size: 5",
    )
    mock_engine.dispose.assert_awaited_once()
