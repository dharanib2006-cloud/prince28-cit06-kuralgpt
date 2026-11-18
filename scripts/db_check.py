"""Check the PostgreSQL database connection."""

import asyncio

from sqlalchemy import text

from kuralgpt.db.session import get_engine


async def main() -> None:
    """Connect to PostgreSQL and display database information."""
    engine = get_engine()

    try:
        async with engine.connect() as connection:
            result = await connection.execute(text("SELECT current_database(), version()"))

            database_name, database_version = result.one()

            print(f"Connected to database '{database_name}'")
            print(database_version)

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
