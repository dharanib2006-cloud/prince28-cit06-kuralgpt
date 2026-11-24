"""Create a timestamped JSON backup of documents and pages."""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from kuralgpt.db.session import get_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKUP_DIR = PROJECT_ROOT / "data" / "backups"


async def main() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"postgres_backup_{timestamp}.json"

    engine = get_engine()

    try:
        async with engine.connect() as connection:
            documents_result = await connection.execute(text("SELECT * FROM documents ORDER BY id"))
            documents = [dict(row) for row in documents_result.mappings()]

            pages_result = await connection.execute(
                text("SELECT * FROM pages ORDER BY document_id, page_no")
            )
            pages = [dict(row) for row in pages_result.mappings()]

            backup = {
                "created_at": timestamp,
                "documents": documents,
                "pages": pages,
            }

            backup_file.write_text(
                json.dumps(
                    backup,
                    ensure_ascii=False,
                    indent=2,
                    default=str,
                ),
                encoding="utf-8",
            )

            print("Backup completed!")
            print(f"File: {backup_file}")
            print(f"Documents: {len(documents)}")
            print(f"Pages: {len(pages)}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
