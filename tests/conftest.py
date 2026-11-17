"""Shared fixtures for KuralGPT API tests."""

import json

import pytest
from fastapi.testclient import TestClient

from kuralgpt.api.main import create_app
from kuralgpt.config import Settings

SAMPLE = [
    {
        "id": "001",
        "kural_no": 1,
        "paal": "அறத்துப்பால்",
        "adhikaram": "கடவுள் வாழ்த்து",
        "couplet_tamil": "அகர முதல எழுத்தெல்லாம் ஆதி பகவன் முதற்றே உலகு",
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
        "paal": "அறத்துப்பால்",
        "adhikaram": "கடவுள் வாழ்த்து",
        "couplet_tamil": "கற்றதனால் ஆய பயனென்கொல் வாலறிவன்",
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
        "paal": "பொருட்பால்",
        "adhikaram": "Example chapter",
        "couplet_tamil": "Test couplet",
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
def client(data_file):
    """Create a test client with its own temporary records."""
    settings = Settings(app_env="ci", data_file=data_file)

    with TestClient(create_app(settings)) as test_client:
        yield test_client
