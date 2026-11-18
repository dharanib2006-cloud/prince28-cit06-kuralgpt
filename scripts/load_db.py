"""Load Thirukkural records into PostgreSQL idempotently."""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert

from kuralgpt.db.session import get_engine
from kuralgpt.models import Document, Page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "sample_records.json"

SOURCE_URL = "https://github.com/tk120404/thirukkural"
SOURCE_LICENCE = "Apache-2.0"

DOCUMENTS_TABLE = Document.__table__
PAGES_TABLE = Page.__table__


def calculate_sha256(record: dict) -> str:
    """Return a stable SHA-256 hash for a record."""
    content = json.dumps(record, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_document(record: dict) -> dict:
    """Convert a Kural record into a database document."""
    metadata = {
        **record,
        "languages": ["ta", "en"],
        "commentator": None,
    }

    return {
        "external_id": str(record["id"]),
        "title": f"Thirukkural {record['kural_no']}",
        "source_url": SOURCE_URL,
        "licence": SOURCE_LICENCE,
        "doc_type": "kural",
        "kural_no": int(record["kural_no"]),
        "published_on": None,
        "sha256": calculate_sha256(record),
        "metadata": metadata,
    }


def build_page(record: dict, document_id: int) -> dict:
    """Convert a Kural record into searchable page text."""
    text_parts = [
        record.get("couplet_tamil"),
        record.get("commentary_tamil"),
        record.get("meaning_tamil"),
        record.get("meaning_english"),
    ]

    searchable_text = "\n\n".join(
        part.strip() for part in text_parts if isinstance(part, str) and part.strip()
    )

    return {
        "document_id": document_id,
        "page_no": 1,
        "text": searchable_text,
    }


async def main(prune: bool = False) -> None:
    """Load records and optionally remove stale Thirukkural records."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")

    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    if not isinstance(records, list) or not records:
        raise ValueError("The sample data must contain a non-empty JSON list.")

    source_ids = {str(record["id"]) for record in records}
    engine = get_engine()

    inserted = 0
    updated = 0
    unchanged = 0
    deleted = 0

    try:
        async with engine.begin() as connection:
            for record in records:
                document_data = build_document(record)

                existing_result = await connection.execute(
                    select(
                        DOCUMENTS_TABLE.c.id,
                        DOCUMENTS_TABLE.c.sha256,
                    ).where(DOCUMENTS_TABLE.c.external_id == document_data["external_id"])
                )
                existing = existing_result.first()

                if existing is None:
                    result = await connection.execute(
                        insert(DOCUMENTS_TABLE)
                        .values(**document_data)
                        .returning(DOCUMENTS_TABLE.c.id)
                    )
                    document_id = result.scalar_one()
                    inserted += 1
                else:
                    document_id = existing.id

                    if existing.sha256 != document_data["sha256"]:
                        await connection.execute(
                            DOCUMENTS_TABLE.update()
                            .where(DOCUMENTS_TABLE.c.id == document_id)
                            .values(**document_data)
                        )
                        updated += 1
                    else:
                        unchanged += 1

                page_data = build_page(record, document_id)
                page_insert = insert(PAGES_TABLE).values(**page_data)

                await connection.execute(
                    page_insert.on_conflict_do_update(
                        constraint="uq_pages_document_id",
                        set_={"text": page_insert.excluded.text},
                    )
                )

            if prune:
                existing_result = await connection.execute(
                    select(DOCUMENTS_TABLE.c.external_id).where(
                        DOCUMENTS_TABLE.c.doc_type == "kural",
                        DOCUMENTS_TABLE.c.source_url == SOURCE_URL,
                    )
                )

                existing_ids = {row.external_id for row in existing_result}
                stale_ids = existing_ids - source_ids

                if stale_ids:
                    result = await connection.execute(
                        delete(DOCUMENTS_TABLE).where(
                            DOCUMENTS_TABLE.c.doc_type == "kural",
                            DOCUMENTS_TABLE.c.source_url == SOURCE_URL,
                            DOCUMENTS_TABLE.c.external_id.in_(stale_ids),
                        )
                    )
                    deleted = result.rowcount or 0

        print("\nDatabase loading completed!")
        print(f"Records: {len(records)}")
        print(f"Inserted: {inserted}")
        print(f"Updated: {updated}")
        print(f"Unchanged: {unchanged}")
        print(f"Deleted: {deleted}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Thirukkural records into PostgreSQL.")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete Thirukkural records absent from the JSON source file.",
    )
    args = parser.parse_args()

    asyncio.run(main(prune=args.prune))
