"""Bulk-load Thirukkural records into PostgreSQL."""

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
BATCH_SIZE = 100

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


async def main(
    prune: bool = False,
    input_file: Path = DATA_FILE,
) -> None:
    """Bulk-load records in batches."""
    if not input_file.exists():
        raise FileNotFoundError(f"Data file not found: {input_file}")

    records = json.loads(input_file.read_text(encoding="utf-8"))

    if not isinstance(records, list) or not records:
        raise ValueError("The input file must contain a non-empty JSON list.")

    document_data = [build_document(record) for record in records]
    source_ids = {item["external_id"] for item in document_data}

    engine = get_engine()
    inserted_or_updated = 0
    pages_processed = 0

    try:
        async with engine.begin() as connection:
            # Load existing IDs once, instead of querying each record.
            existing_result = await connection.execute(
                select(
                    DOCUMENTS_TABLE.c.external_id,
                    DOCUMENTS_TABLE.c.sha256,
                ).where(DOCUMENTS_TABLE.c.external_id.in_(list(source_ids)))
            )
            existing_hashes = {row.external_id: row.sha256 for row in existing_result}

            for start in range(0, len(document_data), BATCH_SIZE):
                batch = document_data[start : start + BATCH_SIZE]

                statement = insert(DOCUMENTS_TABLE).values(batch)

                statement = statement.on_conflict_do_update(
                    index_elements=[DOCUMENTS_TABLE.c.external_id],
                    set_={
                        key: getattr(statement.excluded, key)
                        for key in batch[0]
                        if key != "external_id"
                    },
                ).returning(
                    DOCUMENTS_TABLE.c.id,
                    DOCUMENTS_TABLE.c.external_id,
                )

                result = await connection.execute(statement)
                document_ids = {row.external_id: row.id for row in result}

                page_batch = []

                for record in records[start : start + BATCH_SIZE]:
                    external_id = str(record["id"])
                    page_batch.append(build_page(record, document_ids[external_id]))

                page_statement = insert(PAGES_TABLE).values(page_batch)

                page_statement = page_statement.on_conflict_do_update(
                    index_elements=[
                        PAGES_TABLE.c.document_id,
                        PAGES_TABLE.c.page_no,
                    ],
                    set_={"text": page_statement.excluded.text},
                )

                await connection.execute(page_statement)

                inserted_or_updated += len(batch)
                pages_processed += len(page_batch)

                print(
                    f"Processed {min(start + BATCH_SIZE, len(document_data))}"
                    f"/{len(document_data)} records"
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
                    await connection.execute(
                        delete(DOCUMENTS_TABLE).where(
                            DOCUMENTS_TABLE.c.doc_type == "kural",
                            DOCUMENTS_TABLE.c.source_url == SOURCE_URL,
                            DOCUMENTS_TABLE.c.external_id.in_(stale_ids),
                        )
                    )

        print("\nDatabase loading completed!")
        print(f"Records processed: {inserted_or_updated}")
        print(f"Pages processed: {pages_processed}")
        print(f"Previously existing records: {len(existing_hashes)}")
        print("Deleted: 0 (unless --prune was explicitly used)")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load Thirukkural records into PostgreSQL.")
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Delete records absent from the input file.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DATA_FILE,
        help="Path to the JSON records file.",
    )

    args = parser.parse_args()
    asyncio.run(main(prune=args.prune, input_file=args.input))
