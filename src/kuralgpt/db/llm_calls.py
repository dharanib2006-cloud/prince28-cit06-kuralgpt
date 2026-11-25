"""Database operations for recording and summarizing LLM calls."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import Date, case, cast, func, select

from kuralgpt.db.session import get_session_factory
from kuralgpt.models import LlmCall


async def record_call(row: dict) -> None:
    """Save one LLM call to the database."""
    session_factory = get_session_factory()

    async with session_factory() as session:
        session.add(LlmCall(**row))
        await session.commit()


async def by_day(days: int = 7) -> list[dict]:
    """Return daily LLM call counts, tokens, errors, fallbacks and costs."""
    since = datetime.now(UTC) - timedelta(days=days)
    call_date = cast(LlmCall.created_at, Date)

    statement = (
        select(
            call_date.label("day"),
            func.count(LlmCall.id).label("calls"),
            func.coalesce(func.sum(LlmCall.cost_inr), 0).label("cost_inr"),
            func.coalesce(func.sum(case((LlmCall.status == "error", 1), else_=0)), 0).label(
                "errors"
            ),
            func.coalesce(func.sum(case((LlmCall.fallback_used.is_(True), 1), else_=0)), 0).label(
                "fallbacks"
            ),
            func.coalesce(func.sum(LlmCall.tokens_in), 0).label("tokens_in"),
            func.coalesce(func.sum(LlmCall.tokens_out), 0).label("tokens_out"),
        )
        .where(LlmCall.created_at >= since)
        .group_by(call_date)
        .order_by(call_date)
    )

    session_factory = get_session_factory()

    async with session_factory() as session:
        result = await session.execute(statement)

        return [
            {
                "day": row.day,
                "calls": row.calls,
                "cost_inr": float(row.cost_inr),
                "errors": row.errors,
                "fallbacks": row.fallbacks,
                "tokens_in": row.tokens_in,
                "tokens_out": row.tokens_out,
            }
            for row in result
        ]
