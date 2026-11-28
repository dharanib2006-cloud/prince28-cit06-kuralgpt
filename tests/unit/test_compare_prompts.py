"""Tests for the prompt comparison report writer."""

from scripts import compare_prompts


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
