import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from kuralgpt.db.url import to_asyncpg_url

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL is not configured",
)


def run_db_check(query, params=None):
    async def check():
        engine = create_async_engine(to_asyncpg_url(TEST_DATABASE_URL))
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text(query), params or {})
                return result
        finally:
            await engine.dispose()

    return asyncio.run(check())


def test_database_connection():
    result = run_db_check("SELECT 1")
    assert result.scalar_one() == 1


def test_documents_table_contains_records():
    result = run_db_check("SELECT COUNT(*) FROM documents")
    assert result.scalar_one() >= 20


def test_metadata_gin_index_exists():
    result = run_db_check(
        """
        SELECT COUNT(*)
        FROM pg_indexes
        WHERE tablename = 'documents'
          AND indexname = 'ix_documents_metadata_gin'
        """
    )
    assert result.scalar_one() == 1
