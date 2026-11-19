"""Create and clean up an isolated PostgreSQL database for integration tests."""

import asyncio
import os
import uuid
from collections.abc import Iterator

import asyncpg
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from kuralgpt.config import get_settings
from kuralgpt.db.session import get_engine, get_session_factory


@pytest.fixture(scope="session")
def integration_database_url() -> Iterator[str]:
    """Run integration tests against a fresh, migrated database."""
    base_url = os.getenv("TEST_DATABASE_URL")

    if not base_url:
        pytest.skip("TEST_DATABASE_URL is not configured")

    database_name = f"test_{uuid.uuid4().hex[:8]}"
    admin_url = make_url(base_url).set(
        drivername="postgresql",
        database="postgres",
    )
    admin_dsn = admin_url.render_as_string(hide_password=False)
    temporary_url = make_url(base_url).set(database=database_name)
    temporary_url_string = temporary_url.render_as_string(hide_password=False)

    previous_database_url = os.environ.get("DATABASE_URL")
    previous_app_env = os.environ.get("APP_ENV")
    database_created = False

    async def create_database() -> None:
        connection = await asyncpg.connect(admin_dsn)
        try:
            await connection.execute(f'CREATE DATABASE "{database_name}"')
        finally:
            await connection.close()

    async def drop_database() -> None:
        connection = await asyncpg.connect(admin_dsn)
        try:
            await connection.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        finally:
            await connection.close()

    try:
        asyncio.run(create_database())
        database_created = True

        os.environ["DATABASE_URL"] = temporary_url_string
        os.environ["APP_ENV"] = "ci"

        get_settings.cache_clear()
        get_session_factory.cache_clear()
        get_engine.cache_clear()

        command.upgrade(Config("alembic.ini"), "head")

        yield temporary_url_string

    finally:
        # The API lifespan disposes its engine after each TestClient session.
        get_session_factory.cache_clear()
        get_engine.cache_clear()

        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

        if previous_app_env is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_app_env

        get_settings.cache_clear()

        if database_created:
            asyncio.run(drop_database())


@pytest.fixture
def clean_database(integration_database_url):
    """Start each test with empty document and page tables."""

    async def clean() -> None:
        connection = await asyncpg.connect(
            make_url(integration_database_url)
            .set(drivername="postgresql")
            .render_as_string(hide_password=False)
        )
        try:
            await connection.execute("TRUNCATE TABLE pages, documents RESTART IDENTITY CASCADE")
        finally:
            await connection.close()

    asyncio.run(clean())
    return integration_database_url
