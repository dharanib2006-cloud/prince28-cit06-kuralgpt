"""Shared fixtures for KuralGPT API tests."""

import json

import pytest
from fastapi.testclient import TestClient

from kuralgpt.api.main import create_app
from kuralgpt.config import Settings

# Small fake records: tests do not depend on the real Kural data file.
SAMPLE = [
    {"id": "001", "title": "Alpha guideline", "year": 2023},
    {"id": "002", "title": "Beta circular", "year": 2024},
    {"id": "003", "title": "Gamma notice", "year": 2025},
]


@pytest.fixture
def data_file(tmp_path):
    """Create a temporary JSON file containing fake records."""
    path = tmp_path / "records.json"
    path.write_text(json.dumps(SAMPLE), encoding="utf-8")
    return path


@pytest.fixture
def client(data_file):
    """Create a test client with its own temporary records."""
    settings = Settings(app_env="ci", data_file=data_file)

    with TestClient(create_app(settings)) as test_client:
        yield test_client
