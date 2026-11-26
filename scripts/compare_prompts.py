"""Compare versioned classification prompts against the evaluation test set."""

import asyncio
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from kuralgpt.config import get_settings
from kuralgpt.llm.classify import classify, find_leaks
from kuralgpt.llm.gateway import build_gateway
from kuralgpt.llm.prompts import list_prompt_versions, load_prompt

ROOT = Path(__file__).resolve().parents[1]
TESTSET = ROOT / "eval" / "prompt_testset.jsonl"
CACHE_DIR = ROOT / "eval" / "cache"
NOTES_FILE = ROOT / "NOTES.md"
DELAY_SECONDS = 5


def load_testset() -> list[dict]:
    """Load the evaluation questions."""
    rows = []
    for line_number, line in enumerate(TESTSET.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("label") not in ("docs", "personal", "off_topic"):
            raise ValueError(f"Invalid label on testset line {line_number}")
        if not isinstance(row.get("question"), str):
            raise ValueError(f"Missing question on testset line {line_number}")
        row["line"] = len(rows) + 1
        rows.append(row)
    return rows


def cache_path(version: str, prompt: str, question: str) -> Path:
    """Create a stable cache filename for a prompt and question."""
    content = f"{version}\n{prompt}\n{question}"
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return CACHE_DIR / f"{digest}.json"


def append_notes(section: str) -> None:
    """Append or replace only this script's section in NOTES.md."""
    existing = NOTES_FILE.read_text(encoding="utf-8") if NOTES_FILE.exists() else ""
    marker = "## Day 9 — Prompt comparison"
    if marker in existing:
        existing = existing.split(marker, 1)[0].rstrip()
    NOTES_FILE.write_text(
        existing.rstrip() + "\n\n" + marker + "\n\n" + section.strip() + "\n",
        encoding="utf-8",
    )


async def main() -> None:
    settings = get_settings()
    versions = list_prompt_versions("classify")
    if not versions:
        raise FileNotFoundError("No classify_v*.md prompt files were found.")

    rows = load_testset()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    gateway = build_gateway(settings)

    results = []
    last_call = 0.0

    print(f"Questions: {len(rows)}")
    print(f"Prompt versions: {len(versions)}")
    print(f"Maximum uncached calls: {len(rows) * len(versions)}")
    print("Cached answers will be reused.\n")

    for prompt_path in versions:
        version_number = int(prompt_path.stem.rsplit("_v", 1)[1])
        version = f"v{version_number}"
        prompt = load_prompt("classify", version_number)
        predictions = []

        for row in rows:
            question = row["question"]
            path = cache_path(version, prompt, question)

            if path.exists():
                cached = json.loads(path.read_text(encoding="utf-8"))
                got = cached["got"]
                raw = cached["raw"]
                print(f"CACHE {version} | question {row['line']}")
            else:
                elapsed = time.monotonic() - last_call
                if last_call and elapsed < DELAY_SECONDS:
                    await asyncio.sleep(DELAY_SECONDS - elapsed)

                print(f"CALL  {version} | question {row['line']}")
                got, result = await classify(gateway, prompt, version, question)
                raw = result.text
                last_call = time.monotonic()

                path.write_text(
                    json.dumps(
                        {"got": got, "raw": raw},
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

            predictions.append(
                {
                    **row,
                    "got": got,
                    "raw": raw,
                }
            )

        correct = sum(item["got"] == item["label"] for item in predictions)
        accuracy = correct / len(rows) if rows else 0.0
        misses = [item for item in predictions if item["got"] != item["label"]]

        results.append(
            {
                "version": version,
                "correct": correct,
                "total": len(rows),
                "accuracy": accuracy,
                "misses": misses,
            }
        )

        print(f"\n{version}: {correct}/{len(rows)} ({accuracy:.1%}) — {len(misses)} incorrect\n")

        leaks = find_leaks(prompt, [item["question"] for item in rows])
        if leaks:
            print(f"LEAK {version}: {leaks}")

    print("\nPROMPT COMPARISON")
    print("| Version | Correct | Accuracy |")
    print("|---|---:|---:|")
    for result in results:
        print(
            f"| {result['version']} | "
            f"{result['correct']}/{result['total']} | "
            f"{result['accuracy']:.1%} |"
        )

    best = max(results, key=lambda item: item["accuracy"])
    print(f"\nBest version: {best['version']} ({best['accuracy']:.1%})")

    notes = [
        f"Comparison run: {datetime.now().astimezone().isoformat(timespec='minutes')}",
        "",
        "| Version | Correct | Accuracy |",
        "|---|---:|---:|",
    ]

    for result in results:
        notes.append(
            f"| {result['version']} | {result['correct']}/{result['total']} "
            f"| {result['accuracy']:.1%} |"
        )

    notes.extend(
        [
            "",
            f"**Best version:** {best['version']} "
            f"({best['correct']}/{best['total']}, {best['accuracy']:.1%}).",
            "",
            "### Incorrect predictions",
        ]
    )

    for result in results:
        notes.extend(["", f"**{result['version']}**"])
        if not result["misses"]:
            notes.append("- No incorrect predictions.")
        for item in result["misses"]:
            notes.append(
                f"- Test question {item['line']}: expected "
                f"`{item['label']}`, got `{item['got']}`. "
                f"Question: {item['question']} "
                f"Raw reply: {item['raw']!r}"
            )

    notes.extend(
        [
            "",
            "### Best-version errors to review",
        ]
    )
    if best["misses"]:
        for item in best["misses"]:
            notes.append(
                f"- Question {item['line']} (`{item['label']}` → "
                f"`{item['got']}`): {item['question']}"
            )
    else:
        notes.append("- No incorrect predictions.")

    append_notes("\n".join(notes))
    print("\nResults have been added to NOTES.md.")


if __name__ == "__main__":
    asyncio.run(main())
