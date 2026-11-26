"""Extract metadata from parsed KuralGPT documents."""

import argparse
import asyncio
import time
from pathlib import Path

from dotenv import load_dotenv

from kuralgpt.config import get_settings
from kuralgpt.db.llm_calls import record_call
from kuralgpt.llm.extract import (
    Extraction,
    document_text,
    extract,
    failed_documents,
    get_document,
    pending,
    save,
)
from kuralgpt.llm.gateway import LLMUnavailable, build_gateway
from kuralgpt.llm.prompts import list_prompt_versions, load_prompt

ROOT = Path(__file__).resolve().parents[1]


async def run(
    limit: int | None = None,
    rpm: int = 12,
    max_chars: int = 6000,
    max_attempts: int = 3,
    document_id: int | None = None,
    retry_failed: bool = False,
) -> None:
    """Extract metadata from pending documents with API pacing."""
    if rpm < 1:
        raise ValueError("rpm must be at least 1.")

    if limit is not None and limit < 1:
        raise ValueError("limit must be at least 1.")

    if max_chars < 1:
        raise ValueError("max_chars must be at least 1.")

    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1.")

    if document_id is not None and retry_failed:
        raise ValueError("--document-id and --retry-failed cannot be used together.")

    prompt_files = list_prompt_versions("extract")

    if not prompt_files:
        raise FileNotFoundError("No extraction prompt found. Create prompts/extract_v1.md first.")

    latest_prompt = prompt_files[-1]
    version = latest_prompt.stem.removeprefix("extract_")
    prompt = load_prompt("extract", int(version.removeprefix("v")))

    if document_id is not None:
        document_ids = [document_id]
    elif retry_failed:
        document_ids = failed_documents(limit)
    else:
        document_ids = pending(version, limit)

    print(f"Prompt version: {version}")
    print(f"Selected documents: {len(document_ids)}")

    if not document_ids:
        print("No documents need extraction.")
        return

    settings = get_settings()
    gateway = build_gateway(settings, recorder=record_call)

    if gateway is None:
        raise RuntimeError("No LLM provider is configured.")

    delay = 60 / rpm
    successful = 0
    failed = 0
    repaired = 0
    tokens_in = 0
    tokens_out = 0
    consecutive_unavailable = 0

    started = time.time()

    for index, document_id in enumerate(document_ids, start=1):
        if index % 10 == 0:
            print(f"\nProgress: Processing document {index}/{len(document_ids)}")

        print(f"\n[{index}/{len(document_ids)}] Document ID: {document_id}")

        document = get_document(document_id)

        if document is None:
            print("SKIPPED: Document not found.")
            failed += 1
            continue

        text = document_text(document, max_chars=max_chars)

        if not text.strip():
            print("SKIPPED: Document has no readable page text.")

            save(
                document_id,
                Extraction(
                    metadata=None,
                    result=None,
                    attempts=0,
                    error="Document has no readable page text.",
                ),
                version,
            )

            failed += 1
            continue

        try:
            result = await extract(
                gateway=gateway,
                prompt=prompt,
                version=version,
                document_text=text,
                document_title=document.title,
                max_attempts=max_attempts,
            )

            save(document_id, result, version)

            if result.result is not None:
                tokens_in += result.result.tokens_in
                tokens_out += result.result.tokens_out

            if result.metadata is not None:
                successful += 1

                if result.attempts > 1:
                    repaired += 1

                print(f"SUCCESS: {document.title or 'Untitled'} | Attempts: {result.attempts}")
            else:
                failed += 1
                print(f"FAILED: {result.error}")

            consecutive_unavailable = 0

        except LLMUnavailable as error:
            failed += 1
            consecutive_unavailable += 1

            print(f"LLM UNAVAILABLE: {error}")

            if consecutive_unavailable >= 2:
                print(
                    "Stopping because the LLM has been unavailable for two consecutive documents."
                )
                break

        except Exception as error:
            failed += 1
            consecutive_unavailable = 0
            print(f"FAILED: {error}")

        if index < len(document_ids):
            await asyncio.sleep(delay)

    elapsed = time.time() - started

    print("\n========== EXTRACTION SUMMARY ==========")
    print(f"Documents selected: {len(document_ids)}")
    print(f"Successful: {successful}")
    print(f"Repaired after retry: {repaired}")
    print(f"Failed: {failed}")
    print(f"Input tokens: {tokens_in}")
    print(f"Output tokens: {tokens_out}")
    print(f"Seconds: {elapsed:.1f}")
    print("========================================")


def main() -> None:
    """Parse command-line options and run extraction."""
    parser = argparse.ArgumentParser(description="Extract metadata from parsed KuralGPT documents.")

    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--rpm", type=int, default=12)
    parser.add_argument("--max-chars", type=int, default=6000)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--document-id", type=int, default=None)
    parser.add_argument("--retry-failed", action="store_true")

    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    get_settings.cache_clear()

    asyncio.run(
        run(
            document_id=args.document_id,
            retry_failed=args.retry_failed,
            limit=args.limit,
            rpm=args.rpm,
            max_chars=args.max_chars,
            max_attempts=args.max_attempts,
        )
    )


if __name__ == "__main__":
    main()
