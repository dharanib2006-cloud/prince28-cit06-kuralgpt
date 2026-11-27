"""ARQ worker configuration and lifecycle."""

import asyncio
import logging

from arq.connections import RedisSettings

from kuralgpt.config import get_settings
from kuralgpt.db.llm_calls import record_call
from kuralgpt.db.session import get_session_factory
from kuralgpt.ingest.fetch import Fetcher
from kuralgpt.llm.gateway import build_gateway
from kuralgpt.workers.ingest import ingest_document

logger = logging.getLogger(__name__)


async def startup(ctx: dict) -> None:
    """Initialize shared resources when the worker starts."""
    settings = get_settings()

    fetcher = Fetcher(manifest_path=settings.manifest_file)
    await fetcher.__aenter__()

    ctx["settings"] = settings
    ctx["gateway"] = build_gateway(settings, recorder=record_call)
    ctx["async_session_factory"] = get_session_factory()
    ctx["fetcher"] = fetcher
    ctx["ingest_semaphore"] = asyncio.Semaphore(settings.ingest_concurrency)
    ctx["pace_lock"] = asyncio.Lock()
    ctx["last_llm_call"] = 0.0

    logger.info("KuralGPT ingestion worker started.")


async def shutdown(ctx: dict) -> None:
    """Close shared resources when the worker stops."""
    fetcher = ctx.get("fetcher")

    if fetcher is not None:
        await fetcher.__aexit__(None, None, None)

    logger.info("KuralGPT ingestion worker stopped.")


class WorkerSettings:
    """ARQ worker settings."""

    functions = [ingest_document]
    on_startup = startup
    on_shutdown = shutdown

    settings = get_settings()
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    max_jobs = settings.ingest_concurrency
    job_timeout = settings.ingest_job_timeout
    max_tries = settings.ingest_max_tries
