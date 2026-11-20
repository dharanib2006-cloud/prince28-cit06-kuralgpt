from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.api.deps import get_db_session
from kuralgpt.config import get_settings
from kuralgpt.models import Document

router = APIRouter(tags=["health"])
MINIMUM_RECORDS = 20


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "git_sha": get_settings().git_sha}


@router.get("/ready")
async def ready(
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    try:
        await session.execute(text("SELECT 1"))
        count = await session.scalar(select(func.count()).select_from(Document)) or 0
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "checks": {"database": False},
            },
        ) from exc

    if count < MINIMUM_RECORDS:
        raise HTTPException(
            status_code=503,
            detail={
                "status": "not_ready",
                "records_count": count,
                "checks": {"database": True},
            },
        )

    return {
        "status": "ready",
        "records_count": count,
        "checks": {"database": True},
    }
