from collections import Counter
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from kuralgpt.api.deps import get_db_session
from kuralgpt.models import Document

router = APIRouter(prefix="/v1/stats", tags=["statistics"])


@router.get("")
async def get_statistics(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:

    total = await session.scalar(select(func.count()).select_from(Document)) or 0

    result = await session.scalars(select(Document.metadata_["paal"].as_string()))

    counts = dict(Counter(value for value in result.all() if value is not None))

    return {
        "total_records": total,
        "counts_by_paal": counts,
    }
