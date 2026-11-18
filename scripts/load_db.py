"""Load Thirukkural records into PostgreSQL without creating duplicates."""

import hashlib
import json
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert

from kuralgpt.database import get_engine
from kuralgpt.models import Document, Page

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_ROOT / "data" / "sample_records.json"

SOURCE_URL = "https://github.com/tk120404/thirukkural"
SOURCE_LICENCE = "Apache-2.0"

DOCUMENTS_TABLE = Document.__table__
PAGES_TABLE = Page.__table__


def calculate_sha256(record: dict) -> str:
    """Return a stable SHA-256 hash for a record."""
    content = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def build_document(record: dict) -> dict:
    """Convert a Kural record into a database document."""
    metadata = {
        **record,
        "languages": ["ta", "en"],
        "commentator": None,
    }

    return {
        "id": str(record["id"]),
        "title": f"Thirukkural {record['kural_no']}",
        "source_url": SOURCE_URL,
        "licence": SOURCE_LICENCE,
        "doc_type": "kural",
        "published_on": None,
        "sha256": calculate_sha256(record),
        "metadata": metadata,
    }


def build_page(record: dict) -> dict:
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
        "doc_id": str(record["id"]),
        "page_no": 1,
        "text": searchable_text,
    }


def main() -> None:
    """Load records into PostgreSQL idempotently."""
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")

    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    if not isinstance(records, list):
        raise ValueError("The sample data must contain a JSON list.")

    if not records:
        raise ValueError("No records found in the sample data.")

    document_rows = [build_document(record) for record in records]
    page_rows = [build_page(record) for record in records]

    engine = get_engine()

    try:
        with engine.begin() as connection:
            document_result = connection.execute(
                insert(DOCUMENTS_TABLE)
                .values(document_rows)
                .on_conflict_do_nothing()
                .returning(DOCUMENTS_TABLE.c.id)
            )

            documents_inserted = len(document_result.fetchall())

            page_result = connection.execute(
                insert(PAGES_TABLE)
                .values(page_rows)
                .on_conflict_do_nothing()
                .returning(PAGES_TABLE.c.doc_id)
            )

            pages_inserted = len(page_result.fetchall())

        print("\nDatabase loading completed!")
        print(f"Records found: {len(records)}")
        print(f"Documents inserted: {documents_inserted}")
        print(f"Documents skipped: {len(records) - documents_inserted}")
        print(f"Pages inserted: {pages_inserted}")
        print(f"Pages skipped: {len(records) - pages_inserted}")

    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
