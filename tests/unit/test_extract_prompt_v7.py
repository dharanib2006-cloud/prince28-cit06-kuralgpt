from kuralgpt.llm.prompts import load_prompt
from kuralgpt.workers.ingest import PROMPT_VERSION


def test_worker_uses_extraction_prompt_v7():
    assert PROMPT_VERSION == 7
    prompt = load_prompt("extract", PROMPT_VERSION)
    assert "KuralGPT Document Metadata Extraction — v7" in prompt
    assert 'return `"year": null`' in prompt


def test_extraction_prompt_does_not_infer_historical_years():
    prompt = load_prompt("extract", 7)
    assert "Do not infer a year from the historical age of the work" in prompt
    assert "Do not guess a fallback year such as 1950" in prompt
