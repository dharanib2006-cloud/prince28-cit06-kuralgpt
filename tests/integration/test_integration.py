"""Integration tests for migrations, repository queries, API and loader."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from kuralgpt.api.main import create_app
from kuralgpt.config import Settings
from kuralgpt.db.url import to_asyncpg_url
from kuralgpt.repository import list_documents

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL is not configured",
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_db_check(database_url, query, params=None):
    async def check():
        engine = create_async_engine(to_asyncpg_url(database_url))
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text(query), params or {})
                return result.fetchall(), result.keys()
        finally:
            await engine.dispose()

    return asyncio.run(check())


def seed_records(database_url):
    records = [
        {
            "external_id": "integration-001",
            "title": "Thirukkural 1",
            "kural_no": 1,
            "metadata": {
                "kural_no": 1,
                "paal": "Arathuppal",
                "adhikaram": "Invocation",
                "languages": ["ta", "en"],
                "commentator": "Test Commentator",
                "couplet_tamil": "Sample couplet one",
                "meaning_tamil": "Sample meaning one",
                "meaning_english": "A begins all letters",
                "commentary_tamil": "test commentary",
                "theme": "virtue",
            },
            "sha256": "1" * 64,
        },
        {
            "external_id": "integration-002",
            "title": "Thirukkural 2",
            "kural_no": 2,
            "metadata": {
                "kural_no": 2,
                "paal": "Porutpal",
                "adhikaram": "Learning",
                "languages": ["ta"],
                "commentator": "Another Commentator",
                "couplet_tamil": "Sample couplet two",
                "meaning_tamil": "Sample meaning two",
                "meaning_english": "Learning",
                "commentary_tamil": "learning commentary",
                "theme": "education",
            },
            "sha256": "2" * 64,
        },
    ]

    async def insert_records():
        engine = create_async_engine(to_asyncpg_url(database_url))
        try:
            async with engine.begin() as connection:
                for record in records:
                    await connection.execute(
                        text(
                            """
                            INSERT INTO documents
                                (external_id, title, doc_type, kural_no, sha256, metadata)
                            VALUES
                                (:external_id, :title, 'kural', :kural_no, :sha256,
                                 CAST(:metadata AS jsonb))
                            """
                        ),
                        {
                            **record,
                            "metadata": json.dumps(record["metadata"], ensure_ascii=False),
                        },
                    )
        finally:
            await engine.dispose()

    asyncio.run(insert_records())


def test_migrations_create_required_tables(clean_database):
    rows, _ = run_db_check(
        clean_database,
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
        """,
    )
    tables = {row[0] for row in rows}
    assert {"documents", "pages", "alembic_version"} <= tables


def test_required_indexes_exist(clean_database):
    rows, _ = run_db_check(
        clean_database,
        """
        SELECT indexname FROM pg_indexes
        WHERE tablename = 'documents'
        """,
    )
    indexes = {row[0] for row in rows}
    assert "ix_documents_metadata_gin" in indexes
    assert "ix_documents_kural_no" in indexes


@pytest.mark.parametrize(
    ("filter_name", "filter_value", "expected_id"),
    [
        ("kural_no", 1, "integration-001"),
        ("paal", "Arathuppal", "integration-001"),
        ("adhikaram", "Learning", "integration-002"),
        ("language", "en", "integration-001"),
    ],
)
def test_repository_filters(clean_database, filter_name, filter_value, expected_id):
    seed_records(clean_database)

    async def query():
        engine = create_async_engine(to_asyncpg_url(clean_database))
        try:
            from sqlalchemy.ext.asyncio import async_sessionmaker

            factory = async_sessionmaker(engine, expire_on_commit=False)
            async with factory() as session:
                records, total = await list_documents(
                    session,
                    **{filter_name: filter_value},
                )
                return records, total
        finally:
            await engine.dispose()

    records, total = asyncio.run(query())
    assert total == 1
    assert records[0]["id"] == expected_id


def test_api_reads_real_postgresql_records(clean_database):
    seed_records(clean_database)

    settings = Settings(
        app_env="ci",
        database_url=clean_database,
    )

    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/documents", params={"kural_no": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == "integration-001"


def test_loader_is_idempotent(clean_database):
    command = [
        sys.executable,
        "scripts/load_db.py",
    ]
    environment = os.environ.copy()
    environment["DATABASE_URL"] = clean_database
    environment["APP_ENV"] = "ci"

    first = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )
    second = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    )

    assert "Inserted:" in first.stdout
    assert "Unchanged:" in second.stdout

    rows, _ = run_db_check(
        clean_database,
        "SELECT COUNT(*) FROM documents",
    )
    assert rows[0][0] > 0

    rows, _ = run_db_check(
        clean_database,
        "SELECT COUNT(*) FROM pages",
    )
    assert rows[0][0] > 0
