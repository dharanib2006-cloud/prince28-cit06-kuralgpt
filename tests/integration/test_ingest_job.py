"""Integration tests for ingestion jobs and items."""

import uuid

import pytest
from sqlalchemy import select

from kuralgpt.db.ingest_jobs import create_job, get_job, update_item
from kuralgpt.db.session import get_session_factory
from kuralgpt.models import IngestItem

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_create_job_with_multiple_items(clean_database):
    """Create a job and verify its queued items are stored."""
    session_factory = get_session_factory()
    job_id = uuid.uuid4().hex

    records = [
        {"url": "https://example.com/one.pdf"},
        {"url": "https://example.com/two.pdf"},
    ]

    async with session_factory() as session:
        job = await create_job(session, job_id, records)

        assert job.id == job_id
        assert job.requested == 2

        result = await session.execute(select(IngestItem).where(IngestItem.job_id == job_id))
        items = result.scalars().all()

        assert len(items) == 2
        assert all(item.status == "queued" for item in items)
        assert {item.record["url"] for item in items} == {
            "https://example.com/one.pdf",
            "https://example.com/two.pdf",
        }


async def test_create_job_without_items(clean_database):
    """Create a job with an empty record list."""
    session_factory = get_session_factory()
    job_id = uuid.uuid4().hex

    async with session_factory() as session:
        job = await create_job(session, job_id, [])

        assert job.id == job_id
        assert job.requested == 0

        result = await session.execute(select(IngestItem).where(IngestItem.job_id == job_id))
        assert result.scalars().all() == []


async def test_get_existing_and_missing_job(clean_database):
    """Retrieve an existing job and handle an unknown job ID."""
    session_factory = get_session_factory()
    job_id = uuid.uuid4().hex

    async with session_factory() as session:
        await create_job(
            session,
            job_id,
            [{"url": "https://example.com/document.pdf"}],
        )

        job = await get_job(session, job_id)
        missing_job = await get_job(session, uuid.uuid4().hex)

        assert job is not None
        assert job.id == job_id
        assert job.requested == 1
        assert missing_job is None


async def test_update_item_status_and_missing_item(clean_database):
    """Update an item and handle an unknown item ID."""
    session_factory = get_session_factory()
    job_id = uuid.uuid4().hex

    async with session_factory() as session:
        await create_job(
            session,
            job_id,
            [{"url": "https://example.com/document.pdf"}],
        )

        result = await session.execute(select(IngestItem).where(IngestItem.job_id == job_id))
        item = result.scalar_one()

        updated = await update_item(
            session,
            item.id,
            status="completed",
            attempts=1,
            pages=3,
        )

        assert updated is not None
        assert updated.status == "completed"
        assert updated.attempts == 1
        assert updated.pages == 3

        missing = await update_item(
            session,
            -1,
            status="failed",
        )
        assert missing is None
