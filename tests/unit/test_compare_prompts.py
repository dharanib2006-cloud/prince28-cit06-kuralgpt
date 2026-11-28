"""Tests for the prompt comparison report writer."""

import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "compare_prompts.py"
SPEC = importlib.util.spec_from_file_location("compare_prompts", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
compare_prompts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(compare_prompts)


def test_append_notes_preserves_later_day_sections(tmp_path, monkeypatch):
    notes = tmp_path / "NOTES.md"
    notes.write_text(
        "# Project Notes\n\n"
        "## Day 9 — Prompt comparison\n\nOld comparison.\n\n"
        "## D10 - Queue and Worker\n\nDay 10 details must remain.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(compare_prompts, "NOTES_FILE", notes)

    compare_prompts.append_notes("New comparison table.")

    updated = notes.read_text(encoding="utf-8")
    assert "New comparison table." in updated
    assert "## D10 - Queue and Worker" in updated
    assert "Day 10 details must remain." in updated
    assert "Old comparison." not in updated
    assert updated.count("## Day 9 — Prompt comparison") == 1
