"""Dependencies shared by API routes."""

import hmac
import logging
from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from kuralgpt.config import Settings, get_settings
from kuralgpt.db.ingest_jobs import create_job
from kuralgpt.db.llm_calls import by_day as get_usage_by_day
from kuralgpt.db.llm_calls import record_call
from kuralgpt.db.session import get_session_factory
from kuralgpt.ingest.fetch import Manifest
from kuralgpt.llm.gateway import LLMGateway, build_gateway
from kuralgpt.models import Document, IngestItem, IngestJob
from kuralgpt.workers.queue import IngestQueue

bearer_scheme = HTTPBearer(auto_error=False)


def get_app_settings(request: Request) -> Settings:
    """Return the settings used by this application."""
    return getattr(request.app.state, "settings", get_settings())


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an asynchronous database session."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        yield session


def create_gateway(settings: Settings) -> LLMGateway:
    """Create the application LLM gateway."""
    return build_gateway(settings, recorder=record_call)


def get_gateway(request: Request) -> LLMGateway:
    """Return the application-wide LLM gateway."""
    return request.app.state.llm_gateway


class UsageRepository:
    """Provide access to daily LLM usage records."""

    async def by_day(self, days: int = 7) -> list[dict]:
        """Return daily usage records."""
        return await get_usage_by_day(days)


def get_usage_repository() -> UsageRepository:
    """Provide the usage repository."""
    return UsageRepository()


class IngestRepository:
    """Database operations used by the ingestion API."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def known_ids(self) -> set[str]:
        """Return external IDs of documents already stored."""
        result = await self.session.scalars(select(Document.external_id))
        return set(result.all())

    async def failed_records(self, limit: int = 2000) -> list[dict]:
        """Return only the latest failed attempt for each source path."""
        later_item = aliased(IngestItem)

        later_attempt_exists = (
            select(later_item.id)
            .where(
                later_item.record["path"].as_string() == IngestItem.record["path"].as_string(),
                later_item.id > IngestItem.id,
            )
            .exists()
        )

        statement = (
            select(IngestItem)
            .where(
                IngestItem.status == "failed",
                IngestItem.record["path"].as_string().is_not(None),
                ~later_attempt_exists,
            )
            .order_by(IngestItem.id.desc())
            .limit(limit)
        )

        result = await self.session.scalars(statement)
        return [item.record for item in result.all()]

    async def create(self, records: list[dict]) -> tuple[str, list[int]]:
        """Create a job and return its queued item IDs."""
        job_id = uuid4().hex
        await create_job(self.session, job_id, records)

        result = await self.session.scalars(
            select(IngestItem.id).where(IngestItem.job_id == job_id).order_by(IngestItem.id)
        )

        return job_id, list(result.all())

    async def progress(self, job_id: str) -> dict | None:
        """Return job progress and item counts."""
        statement = (
            select(IngestJob).options(selectinload(IngestJob.items)).where(IngestJob.id == job_id)
        )
        result = await self.session.execute(statement)
        job = result.scalar_one_or_none()

        if job is None:
            return None

        counts = {
            "queued": 0,
            "running": 0,
            "completed": 0,
            "skipped": 0,
            "failed": 0,
        }

        for item in job.items:
            if item.status in counts:
                counts[item.status] += 1

        return {
            "job_id": job.id,
            "requested": job.requested,
            "counts": counts,
            "items": [
                {
                    "id": item.id,
                    "status": item.status,
                    "attempts": item.attempts,
                    "error": item.error,
                    "pages": item.pages,
                    "record": item.record,
                }
                for item in job.items
            ],
        }

    async def dead_letter(self, limit: int = 50) -> list[dict]:
        """Return the most recently failed ingestion items."""
        statement = (
            select(IngestItem)
            .where(IngestItem.status == "failed")
            .order_by(IngestItem.updated_at.desc())
            .limit(limit)
        )
        result = await self.session.scalars(statement)

        return [
            {
                "id": item.id,
                "job_id": item.job_id,
                "record": item.record,
                "attempts": item.attempts,
                "error": item.error,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None,
            }
            for item in result.all()
        ]


async def get_ingest_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> IngestRepository:
    return IngestRepository(session)


def get_manifest(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> Manifest:
    """Provide the configured ingestion manifest."""
    return Manifest(settings.manifest_file)


async def get_ingest_queue(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> AsyncGenerator[IngestQueue, None]:
    """Connect to Redis and provide the ingestion queue."""
    try:
        queue = await IngestQueue.connect(settings.redis_url)
    except Exception as exc:
        logging.exception("Could not connect to the ingestion queue")
        raise HTTPException(
            status_code=503,
            detail="Ingestion queue is unavailable. Check the Redis connection.",
        ) from exc

    try:
        yield queue
    finally:
        await queue.close()


async def require_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(bearer_scheme),
    ],
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> None:
    """Require a valid configured admin bearer token."""
    if not settings.admin_token:
        raise HTTPException(
            status_code=503,
            detail="Admin authentication is not configured.",
        )

    if credentials is None or not hmac.compare_digest(
        credentials.credentials,
        settings.admin_token,
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid admin bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
UsageDep = Annotated[UsageRepository, Depends(get_usage_repository)]
IngestRepoDep = Annotated[IngestRepository, Depends(get_ingest_repository)]
ManifestDep = Annotated[Manifest, Depends(get_manifest)]
QueueDep = Annotated[IngestQueue, Depends(get_ingest_queue)]
