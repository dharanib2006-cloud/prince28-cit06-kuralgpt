"""Manage the asynchronous PostgreSQL engine and sessions."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from kuralgpt.config import get_settings
from kuralgpt.db.url import to_asyncpg_url


@lru_cache
def get_engine():
    """Create and return the asynchronous PostgreSQL engine."""
    settings = get_settings()

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured. Add it to your local .env file.")

    database_url = to_asyncpg_url(settings.database_url)

    return create_async_engine(
        database_url,
        echo=True,
        pool_size=5,
        max_overflow=2,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the asynchronous database session factory."""
    return async_sessionmaker(
        bind=get_engine(),
        class_=AsyncSession,
        expire_on_commit=False,
    )
