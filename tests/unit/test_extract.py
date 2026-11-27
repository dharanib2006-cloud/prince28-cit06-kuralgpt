"""Unit tests for KuralGPT metadata extraction."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from kuralgpt.llm.doc_meta import DocMeta
from kuralgpt.llm.extract import (
    build_messages,
    document_text,
    extract,
    parse_metadata,
)
from kuralgpt.llm.gateway import LLMResult

VALID_METADATA = {
    "doc_kind": "guideline",
    "year": 2023,
    "language": "en",
    "summary": "This document provides guidelines for teaching Thirukkural.",
    "topics": ["education", "thirukkural"],
    "kural_no": ["1", "2"],
    "adhikaram": ["Praise of God"],
    "paal": ["aram"],
    "theme": ["education", "values"],
}


def make_result(text: str) -> LLMResult:
    """Create a fake LLM result for testing."""
    return LLMResult(
        text=text,
        provider="fake",
        model="fake-model",
        tokens_in=100,
        tokens_out=50,
        latency_ms=20,
        attempts=1,
        fallback_used=False,
        cost_inr=0.01,
    )


def test_parse_valid_metadata():
    metadata = parse_metadata(json.dumps(VALID_METADATA))

    assert isinstance(metadata, DocMeta)
    assert metadata.doc_kind == "guideline"
    assert metadata.year == 2023
    assert metadata.language == "en"
    assert metadata.paal == ["aram"]


def test_parse_metadata_with_markdown_fence():
    reply = f"```json\n{json.dumps(VALID_METADATA)}\n```"

    metadata = parse_metadata(reply)

    assert metadata.doc_kind == "guideline"
    assert metadata.topics == ["education", "thirukkural"]


def test_parse_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        parse_metadata("{invalid json}")


def test_parse_metadata_missing_required_field():
    incomplete = VALID_METADATA.copy()
    del incomplete["summary"]

    with pytest.raises(ValueError, match="Metadata validation failed"):
        parse_metadata(json.dumps(incomplete))


def test_build_messages_wraps_document_text():
    messages = build_messages(
        "Extract metadata.",
        "Sample document content.",
    )

    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"
    assert "<document>" in messages[1]["content"]
    assert "Sample document content." in messages[1]["content"]


@pytest.mark.asyncio
async def test_extract_retries_and_succeeds():
    gateway = SimpleNamespace(
        generate=AsyncMock(
            side_effect=[
                make_result("{invalid json}"),
                make_result(json.dumps(VALID_METADATA)),
            ]
        )
    )

    result = await extract(
        gateway=gateway,
        prompt="Extract metadata.",
        version="v1",
        document_text="Sample document from 2023.",
        max_attempts=3,
    )

    assert result.metadata is not None
    assert result.metadata.doc_kind == "guideline"
    assert result.attempts == 2
    assert result.error is None
    assert gateway.generate.await_count == 2


@pytest.mark.asyncio
async def test_extract_fails_after_max_attempts():
    gateway = SimpleNamespace(generate=AsyncMock(return_value=make_result("{invalid json}")))

    result = await extract(
        gateway=gateway,
        prompt="Extract metadata.",
        version="v1",
        document_text="Sample document.",
        max_attempts=3,
    )

    assert result.metadata is None
    assert result.attempts == 3
    assert result.error is not None
    assert gateway.generate.await_count == 3


def test_document_text_combines_first_three_pages_and_limits_length():
    document = SimpleNamespace(
        pages=[
            SimpleNamespace(page_no=1, text="First page"),
            SimpleNamespace(page_no=2, text="Second page"),
            SimpleNamespace(page_no=3, text="Third page"),
            SimpleNamespace(page_no=4, text="Fourth page"),
        ]
    )

    text = document_text(document)

    assert "First page" in text
    assert "Second page" in text
    assert "Third page" in text
    assert "Fourth page" not in text

    limited = document_text(document, max_chars=10)

    assert len(limited) == 10


def test_parse_metadata_strips_whitespace_from_keys():
    data = VALID_METADATA.copy()
    data[" kural_no "] = data.pop("kural_no")

    metadata = parse_metadata(json.dumps(data))

    assert metadata.kural_no == ["1", "2"]


def test_parse_metadata_converts_strings_to_lists():
    data = VALID_METADATA.copy()
    data["paal"] = "aram"
    data["theme"] = "education"

    metadata = parse_metadata(json.dumps(data))

    assert metadata.paal == ["aram"]
    assert metadata.theme == ["education"]


def test_parse_metadata_rejects_duplicate_normalized_keys():
    data = VALID_METADATA.copy()
    data[" kural_no "] = ["3"]

    with pytest.raises(ValueError, match="Duplicate field"):
        parse_metadata(json.dumps(data))


@pytest.mark.asyncio
async def test_extract_sends_json_schema_when_enabled():
    gateway = SimpleNamespace(
        generate=AsyncMock(return_value=make_result(json.dumps(VALID_METADATA)))
    )

    result = await extract(
        gateway=gateway,
        prompt="Extract metadata.",
        version="v6",
        document_text="Sample document from 2023.",
        use_schema=True,
    )

    assert result.metadata is not None
    assert result.attempts == 1

    call_kwargs = gateway.generate.await_args.kwargs
    response_format = call_kwargs["response_format"]

    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["name"] == "doc_meta"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"] == DocMeta.model_json_schema()


@pytest.mark.asyncio
async def test_extract_rejects_year_not_in_document():
    invented_metadata = VALID_METADATA.copy()
    invented_metadata["year"] = 2025

    gateway = SimpleNamespace(
        generate=AsyncMock(return_value=make_result(json.dumps(invented_metadata)))
    )

    result = await extract(
        gateway=gateway,
        prompt="Extract metadata.",
        version="v1",
        document_text="Sample document from 2023.",
        max_attempts=1,
    )

    assert result.metadata is None
    assert result.error == "year 2025 is not in the document"
    assert result.attempts == 1
    assert gateway.generate.await_count == 1
