"""Week 2 self-check for KuralGPT.

Checks D06-D10, unit tests and (optionally) live endpoints.
Uses only the Python standard library.
"""

import contextlib
import json
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path.cwd()
OK, BAD, WARN = " ok ", " ✗ ", " ! "
LABELS = {"docs", "personal", "off_topic"}
KEY_SHAPES = r"AIza[0-9A-Za-z_-]{35}|gsk_[0-9A-Za-z]{30,}"
results = []


def check(day, label, passed, hint="", warn_only=False):
    mark = OK if passed else (WARN if warn_only else BAD)
    print(mark + label + ("" if passed or not hint else f"\n       → {hint}"))
    if not warn_only:
        results.append((day, passed))


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def exists(path):
    return (ROOT / path).exists()


def read_text(path):
    return (ROOT / path).read_text(encoding="utf-8", errors="replace") if exists(path) else ""


def parse_response(raw):
    """Parse either normal JSON or Server-Sent Events."""
    try:
        return json.loads(raw or b"null")
    except (ValueError, UnicodeDecodeError):
        text = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw

        result = None
        for line in text.splitlines():
            if line.startswith("data:"):
                payload = line[5:].strip()
                try:
                    result = json.loads(payload)
                except ValueError:
                    continue

        return result


def call(url, body=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            return response.status, parse_response(raw)

    except urllib.error.HTTPError as error:
        raw = error.read()
        return error.code, parse_response(raw)


def main():
    live = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else None

    if not exists("pyproject.toml"):
        print("Run this from your project folder (where pyproject.toml is).")
        return 2

    pyproject = tomllib.loads(read_text("pyproject.toml"))
    pkg = pyproject["project"]["name"].replace("-", "_")
    deps = " ".join(pyproject["project"].get("dependencies", [])).lower()

    readme = read_text("README.md")
    notes = read_text("NOTES.md")
    tracked = run(["git", "ls-files"]).stdout.splitlines()

    migrations = (
        " ".join(
            p.read_text(encoding="utf-8", errors="replace")
            for p in (ROOT / "migrations/versions").glob("*.py")
        )
        if exists("migrations/versions")
        else ""
    )

    print("\nD06 · collecting your corpus (D06 Build Lab)")
    for path in [
        f"src/{pkg}/ingest/fetch.py",
        "scripts/fetch.py",
        "DATASET.md",
    ]:
        check("D06", path, exists(path), "missing: see the D06 Build Lab")

    downloaded = 0
    for line in read_text("data/manifest.jsonl").splitlines():
        with contextlib.suppress(ValueError):
            downloaded += json.loads(line).get("status") == "completed"

    check(
        "D06",
        f"data/manifest.jsonl lists downloaded files ({downloaded} found)",
        downloaded > 0,
        "run scripts/fetch.py and commit data/manifest.jsonl",
    )

    raw = [p for p in tracked if p.startswith("data/raw/")]
    check(
        "D06",
        "data/raw/ is NOT committed",
        not raw,
        "remove raw files from Git tracking",
    )

    print("\nD07 · parsing (D07 Build Lab)")
    for path in [
        f"src/{pkg}/ingest/parse.py",
        f"src/{pkg}/ingest/store.py",
        "scripts/parse_corpus.py",
    ]:
        check("D07", path, exists(path), "missing: see the D07 Build Lab")

    check(
        "D07",
        "a migration creates parse_failures",
        "parse_failures" in migrations,
        "check the D07 database migration",
    )

    pinned = re.search(r"pymupdf[^ ]*<2", deps) is not None
    check(
        "D07",
        "pymupdf is pinned below version 2",
        pinned,
        'uv add "pymupdf<2"',
    )

    check(
        "D07",
        "NOTES.md has the parser comparison table",
        "<!-- parsers:start -->" in notes,
        "uv run python scripts/compare_parsers.py",
    )

    print("\nD08 · LLM gateway (D08 Build Lab)")
    for path in [
        f"src/{pkg}/llm/gateway.py",
        f"src/{pkg}/api/routes/chat.py",
    ]:
        check("D08", path, exists(path), "missing: see the D08 Build Lab")

    prompt = read_text("prompts/chat_system_v1.md")
    check(
        "D08",
        'prompts/chat_system_v1.md allows "I am not sure"',
        "not sure" in prompt.lower(),
        "check the chat system prompt",
    )

    check(
        "D08",
        "a migration creates llm_calls",
        "llm_calls" in migrations,
        "check the D08 database migration",
    )

    env_example = read_text(".env.example")
    names_only = all(
        re.search(rf"^{name}=[ \t]*$", env_example, flags=re.M)
        for name in ("GEMINI_API_KEY", "GROQ_API_KEY")
    )
    check(
        "D08",
        ".env.example names both keys, with empty values",
        names_only,
        "GEMINI_API_KEY= and GROQ_API_KEY= with empty values",
    )

    leaked = run(["git", "grep", "-I", "-l", "-E", KEY_SHAPES]).stdout.splitlines()
    check(
        "D08",
        "no model key in any committed file",
        ".env" not in tracked and not leaked,
        f"check for exposed keys in: {leaked}",
    )

    check(
        "D08",
        "the Dockerfile copies prompts/",
        "prompts ./prompts" in read_text("Dockerfile"),
        "check Dockerfile for COPY --chown=app:app prompts ./prompts",
    )

    print("\nD09 · prompts and structured output (D09 Build Lab)")
    versions = (
        sorted(p.name for p in (ROOT / "prompts").glob("classify_v*.md"))
        if exists("prompts")
        else []
    )

    check(
        "D09",
        f"3+ router prompts in prompts/ ({len(versions)} found)",
        len(versions) >= 3,
        "classify_v1.md, classify_v2.md, classify_v3.md",
    )

    unfinished = [name for name in versions if "TODO" in read_text(f"prompts/{name}")]
    check(
        "D09",
        "no TODO left in the router prompts",
        not unfinished,
        f"write your own examples in {unfinished}",
        warn_only=True,
    )

    rows, todo = [], 0
    for line in read_text("eval/prompt_testset.jsonl").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("label") in LABELS and row.get("question"):
            rows.append(row)
            todo += "TODO" in row["question"]

    check(
        "D09",
        f"eval/prompt_testset.jsonl has 20 labelled questions ({len(rows) - todo} usable)",
        len(rows) - todo >= 20,
        f"{todo} lines still say TODO" if todo else "use one JSON object per line",
    )

    for path in [
        f"src/{pkg}/llm/extract.py",
        f"src/{pkg}/llm/doc_meta.py",
    ]:
        check("D09", path, exists(path), "missing: see the D09 Build Lab")

    extract_prompts = list((ROOT / "prompts").glob("extract_v*.md"))
    check(
        "D09",
        "an extract prompt exists (prompts/extract_v*.md)",
        bool(extract_prompts),
        "D09 Milestone 4",
    )

    check(
        "D09",
        "NOTES.md has the prompt comparison table",
        "<!-- prompts:start -->" in notes,
        "uv run python scripts/compare_prompts.py",
    )

    print("\nD10 · queue and worker (D10 Build Lab)")
    for path in [
        f"src/{pkg}/workers/ingest.py",
        f"src/{pkg}/api/routes/ingest.py",
    ]:
        check("D10", path, exists(path), "missing: see the D10 Build Lab")

    check(
        "D10",
        "a migration creates ingest_items",
        "ingest_items" in migrations,
        "check the D10 database migration",
    )

    check(
        "D10",
        "docker-compose.yml has a worker service",
        re.search(r"^  worker:", read_text("docker-compose.yml"), flags=re.M) is not None,
        "D10 Milestone 6",
    )

    report = read_text("docs/INGEST_REPORT.md")
    check(
        "D10",
        "docs/INGEST_REPORT.md is generated and committed",
        "<!-- generated:start -->" in report and "docs/INGEST_REPORT.md" in tracked,
        "uv run python scripts/ingest_report.py, then commit it",
    )

    tags = run(["git", "tag", "--list", "week-2"]).stdout.strip()
    check(
        "D10",
        "tag week-2 exists",
        tags == "week-2",
        'git tag -a week-2 -m "Week 2 complete"',
    )

    print("\nTests")
    tests = run(["uv", "run", "pytest", "tests/unit"])
    found = re.search(r"\d+ (passed|failed|error)[^\n]*", tests.stdout)
    check(
        "TESTS",
        f"unit tests pass ({found.group(0) if found else 'no test summary'})",
        tests.returncode == 0,
        "uv run poe test, and read the FIRST failure",
    )

    url_in_readme = re.search(r"https://[\w.-]+\.onrender\.com", readme)

    if live:
        base = live
    elif url_in_readme:
        base = url_in_readme.group(0)
    else:
        base = None

    if base:
        print(f"\nLive · {base}")
        try:
            status, body = call(f"{base}/health")
            version = (
                str(body.get("git_sha", body.get("version", "")))[:7]
                if isinstance(body, dict)
                else "?"
            )
            check(
                "LIVE",
                f"/health → {status}, version {version}",
                status == 200,
                "open Render and check deployment logs",
            )

            status, body = call(
                f"{base}/v1/chat",
                {"message": "Reply with OK"},
            )
            who = body.get("provider") if isinstance(body, dict) else None
            check(
                "LIVE",
                f"POST /v1/chat → {status}" + (f", answered by {who}" if who else ""),
                status == 200 and bool(who),
                "check provider keys and Render logs",
            )

            status, body = call(f"{base}/v1/usage")
            calls = body.get("calls", 0) if isinstance(body, dict) else 0
            check(
                "LIVE",
                f"/v1/usage → {status}, {calls} model calls this week",
                status == 200 and calls > 0,
                "check whether the llm_calls migration is applied",
            )

            # Verify that ingestion rejects requests without an admin token.
            status, _ = call(f"{base}/v1/ingest", {"limit": 1})
            check(
                "LIVE",
                f"unauthenticated POST /v1/ingest → {status}",
                status == 401,
                "Set ADMIN_TOKEN in Render or inspect the ingest route authentication",
            )

            status, body = call(f"{base}/v1/ingest/dead-letter")
            count = body.get("count") if isinstance(body, dict) else "?"
            check(
                "LIVE",
                f"/v1/ingest/dead-letter → {status} ({count} items)",
                status == 200,
                "check the D10 ingest router and Render logs",
            )

        except Exception as error:
            check(
                "LIVE",
                "the live URL answers",
                False,
                f"{error}: check the Render service",
            )

    total = len(results)
    passed = sum(ok for _, ok in results)
    print(f"\n{passed} of {total} checks passed.")

    for day in ["D06", "D07", "D08", "D09", "D10", "TESTS", "LIVE"]:
        missing = [ok for d, ok in results if d == day and not ok]
        if missing:
            print(f"Start with {day}: it has {len(missing)} open item(s).")
            break
    else:
        print("Week 2 is complete. 🚀")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
