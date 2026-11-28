"""Database operations for ingestion jobs and their items."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.models import IngestItem, IngestJob


async def create_job(
    session: AsyncSession,
    job_id: str,
    records: list[dict],
) -> IngestJob:
    """Create a job and its queued ingestion items."""
    job = IngestJob(id=job_id, requested=len(records))

    job.items = [IngestItem(job_id=job_id, record=record, status="queued") for record in records]

    session.add(job)
    await session.commit()
    await session.refresh(job)

    return job


async def get_job(
    session: AsyncSession,
    job_id: str,
) -> IngestJob | None:
    """Retrieve a job and its items."""
    statement = select(IngestJob).where(IngestJob.id == job_id)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def update_item(
    session: AsyncSession,
    item_id: int,
    *,
    status: str,
    attempts: int | None = None,
    error: str | None = None,
    pages: int | None = None,
) -> IngestItem | None:
    """Update the status and progress of an ingestion item."""
    statement = select(IngestItem).where(IngestItem.id == item_id)
    result = await session.execute(statement)
    item = result.scalar_one_or_none()

    if item is None:
        return None

    item.status = status

    if attempts is not None:
        item.attempts = attempts

    if error is not None:
        item.error = error

    if pages is not None:
        item.pages = pages

    await session.commit()
    await session.refresh(item)

    return item
