import argparse
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from kuralgpt.ingest.parse import ParseError, parse_file
from kuralgpt.ingest.store import (
    record_parse_failure,
    store_parsed_document,
)
from kuralgpt.models import Document, ParseFailure

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"

SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".html",
    ".htm",
    ".json",
    ".md",
    ".rst",
    ".txt",
    ".log",
    ".csv",
    ".xml",
    ".yaml",
    ".yml",
}


def main():
    parser = argparse.ArgumentParser(
        description="Parse files from data/raw and store them in the database."
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=RAW_DIR,
        help="Directory to scan for files (default: data/raw).",
    )
    parser.add_argument(
        "--ocr",
        type=str,
        default=None,
        help="OCR language(s) for scanned PDF pages, e.g. eng or eng+tam.",
    )

    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from the environment.")

    source_dir = args.source_dir

    if not source_dir.is_absolute():
        source_dir = ROOT / source_dir

    if not source_dir.is_dir():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    files = sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    if args.limit is not None:
        files = files[: args.limit]

    print(f"Files found: {len(files)}")

    engine = create_engine(database_url)
    successful = 0
    failed = 0
    already_parsed = 0
    failed_before = 0
    pages_added = 0
    start = time.time()

    try:
        with Session(engine) as session:
            for index, path in enumerate(files, start=1):
                path_string = str(path)

                existing_document = session.scalar(
                    select(Document).where(Document.metadata_["path"].as_string() == path_string)
                )

                existing_failure = session.scalar(
                    select(ParseFailure).where(ParseFailure.path == path_string)
                )

                if (
                    existing_document is not None
                    and existing_failure is None
                    and not args.retry_failed
                ):
                    already_parsed += 1
                    continue

                if existing_failure is not None and not args.retry_failed:
                    failed_before += 1
                    continue

                print(f"\n[{index}/{len(files)}] Processing: {path.name}")

                try:
                    parsed = parse_file(
                        path,
                        ocr_language=args.ocr,
                    )

                    document = store_parsed_document(
                        session,
                        path,
                        parsed,
                    )
                    session.commit()

                    successful += 1
                    pages_added += len(parsed.pages)

                    print(
                        f"SUCCESS: {parsed.kind} | "
                        f"{len(parsed.pages)} pages | "
                        f"Document ID: {document.id}"
                    )

                except ParseError as error:
                    session.rollback()

                    record_parse_failure(session, path, error)
                    session.commit()

                    failed += 1
                    print(f"FAILED: {error.reason} - {error.detail}")

                except Exception as error:
                    session.rollback()

                    parse_error = ParseError(
                        "unexpected_error",
                        str(error),
                    )

                    record_parse_failure(session, path, parse_error)
                    session.commit()

                    failed += 1
                    print(f"FAILED: {error}")

                if index % 50 == 0:
                    print(f"Progress: {index}/{len(files)} files")

    finally:
        engine.dispose()

    elapsed = time.time() - start

    print("\n========== PARSING SUMMARY ==========")
    print(f"Total files: {len(files)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    print(f"Already parsed: {already_parsed}")
    print(f"Failed before: {failed_before}")
    print(f"Pages added: {pages_added}")
    print(f"Seconds: {elapsed:.1f}")
    print("=====================================")


if __name__ == "__main__":
    main()
