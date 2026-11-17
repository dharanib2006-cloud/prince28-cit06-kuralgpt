"""Tests for KuralGPT API endpoints and configuration."""

import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from kuralgpt.api.main import create_app
from kuralgpt.config import Settings


def test_health_is_ok(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_when_at_least_20_records_are_loaded(tmp_path):
    records = [{"id": str(number)} for number in range(1, 21)]
    data_file = tmp_path / "records.json"
    data_file.write_text(json.dumps(records), encoding="utf-8")

    settings = Settings(app_env="ci", data_file=data_file)

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["records_count"] == 20
    assert response.json()["checks"]["records_loaded"] is True


def test_ready_is_503_when_fewer_than_20_records_are_loaded(tmp_path):
    records = [{"id": str(number)} for number in range(1, 20)]
    data_file = tmp_path / "records.json"
    data_file.write_text(json.dumps(records), encoding="utf-8")

    settings = Settings(app_env="ci", data_file=data_file)

    with TestClient(create_app(settings)) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503


def test_ready_is_503_when_data_file_is_missing(tmp_path):
    settings = Settings(app_env="ci", data_file=tmp_path / "missing.json")

    with TestClient(create_app(settings)) as test_client:
        assert test_client.get("/health").status_code == 200
        assert test_client.get("/ready").status_code == 503


def test_list_documents_paginates(client):
    response = client.get("/v1/documents", params={"limit": 2})
    body = response.json()

    assert response.status_code == 200
    assert body["total"] == 3
    assert len(body["items"]) == 2


def test_search_filters_records(client):
    response = client.get("/v1/documents", params={"q": "beta"})

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
        "அறத்துப்பால்": 2,
        "பொருட்பால்": 1,
    }


def test_get_document_found(client):
    response = client.get("/v1/documents/001")

    assert response.status_code == 200
    assert response.json()["title"] == "Alpha guideline"


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
