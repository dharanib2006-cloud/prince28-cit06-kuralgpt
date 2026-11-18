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


def test_typed_kural_numbers_are_backfilled():
    result = run_db_check(
        """
        SELECT COUNT(*), COUNT(kural_no), MIN(kural_no), MAX(kural_no)
        FROM documents
        WHERE doc_type = 'kural'
        """
    )

    total, populated, minimum, maximum = result.one()

    assert total == 20
    assert populated == 20
    assert minimum == 1
    assert maximum == 20


def test_typed_kural_number_filter_works():
    result = run_db_check(
        """
        SELECT kural_no
        FROM documents
        WHERE doc_type = 'kural' AND kural_no = :kural_no
        """,
        {"kural_no": 2},
    )

    assert result.scalar_one() == 2


def test_kural_number_btree_index_exists():
    result = run_db_check(
        """
        SELECT COUNT(*)
        FROM pg_indexes
        WHERE tablename = 'documents'
          AND indexname = 'ix_documents_kural_no'
        """
    )

    assert result.scalar_one() == 1
