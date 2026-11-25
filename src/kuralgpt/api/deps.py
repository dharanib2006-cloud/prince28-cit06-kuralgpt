"""Dependencies shared by API routes."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.config import Settings, get_settings
from kuralgpt.db.llm_calls import by_day as get_usage_by_day
from kuralgpt.db.llm_calls import record_call
from kuralgpt.db.session import get_session_factory
from kuralgpt.llm.gateway import LLMGateway, build_gateway


def get_app_settings() -> Settings:
    """Return application settings."""
    return get_settings()


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


GatewayDep = Annotated[LLMGateway, Depends(get_gateway)]
UsageDep = Annotated[UsageRepository, Depends(get_usage_repository)]
