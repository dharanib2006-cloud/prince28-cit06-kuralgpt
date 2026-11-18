from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.config import Settings, get_settings
from kuralgpt.db.session import get_session_factory


def get_app_settings() -> Settings:
    return get_settings()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
