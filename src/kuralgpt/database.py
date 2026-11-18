"""PostgreSQL database connection management."""

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from kuralgpt.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """Create and return the PostgreSQL engine."""
    settings = get_settings()

    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured. Add it to your local .env file.")

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=2,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Create and return the database session factory."""
    return sessionmaker(
        bind=get_engine(),
        class_=Session,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )
