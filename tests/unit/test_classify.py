"""Unit tests for question classification."""

import asyncio
import json
from pathlib import Path

from kuralgpt.llm.classify import (
    accuracy,
    build_messages,
    classify,
    find_leaks,
    parse_label,
)
from kuralgpt.llm.gateway import FakeLLM, LLMGateway


def test_parse_label_docs():
    assert parse_label("docs") == "docs"


def test_parse_label_personal_case_and_punctuation():
    assert parse_label("PERSONAL.") == "personal"


def test_parse_label_invalid_reply():
    assert parse_label("docs or personal") == "invalid"


def test_build_messages_wraps_question():
    messages = build_messages("Classify the question.", "  What is Kural 1?  ")

    assert messages[0] == {
        "role": "system",
        "content": "Classify the question.",
    }
    assert messages[1] == {
        "role": "user",
        "content": "<question>\nWhat is Kural 1?\n</question>",
    }


def test_accuracy():
    rows = [
        {"label": "docs", "got": "docs"},
        {"label": "personal", "got": "docs"},
        {"label": "off_topic", "got": "off_topic"},
    ]

    assert accuracy(rows) == 2 / 3
    assert accuracy([]) == 0.0


def test_find_leaks():
    prompt = "Use the documents to answer questions about friendship."
    questions = [
        "What is the first kural?",
        "What is the first Kural? ",
        "Who directed Baahubali?",
    ]

    assert find_leaks(prompt, questions) == []


def test_classify_with_fake_gateway():
    provider = FakeLLM(script=["docs"])
    gateway = LLMGateway([provider])

    label, result = asyncio.run(
        classify(
            gateway,
            "Classify the question.",
            "v1",
            "What is the first kural?",
        )
    )

    assert label == "docs"
    assert result.text == "docs"
    assert provider.calls == 1


def test_prompt_files_and_testset_exist():
    root = Path(__file__).resolve().parents[2]

    prompt_files = list((root / "prompts").glob("classify_v*.md"))
    assert len(prompt_files) >= 3

    testset_path = root / "eval" / "prompt_testset.jsonl"
    assert testset_path.is_file()

    rows = [
        json.loads(line)
        for line in testset_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(rows) >= 20

    valid_labels = {"docs", "personal", "off_topic"}

    assert all(
        isinstance(row.get("question"), str)
        and row["question"].strip()
        and row.get("label") in valid_labels
        for row in rows
    )


def test_classify_v5_has_english_and_tamil_examples_for_each_label():
    root = Path(__file__).resolve().parents[2]
    prompt_path = root / "prompts" / "classify_v5.md"
    prompt = prompt_path.read_text(encoding="utf-8")

    for label in ("docs", "personal", "off_topic"):
        assert f"### {label} — English" in prompt
        assert f"### {label} — Tamil" in prompt

    rows = [
        json.loads(line)
        for line in (root / "eval" / "prompt_testset.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    assert find_leaks(prompt, [row["question"] for row in rows]) == []
