"""Inspect the existing PostgreSQL tables and columns."""

import asyncio

from sqlalchemy import text

from kuralgpt.db.session import get_engine


async def main() -> None:
    engine = get_engine()

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    """
                    SELECT table_name, column_name, data_type
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                    ORDER BY table_name, ordinal_position
                    """
                )
            )

            for table_name, column_name, data_type in result:
                print(f"{table_name}.{column_name}: {data_type}")

            documents = await connection.execute(text("SELECT COUNT(*) FROM documents"))
            print("Document count:", documents.scalar_one())

            pages = await connection.execute(text("SELECT COUNT(*) FROM pages"))
            print("Page count:", pages.scalar_one())

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
