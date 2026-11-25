"""Integration test for saving and retrieving LLM call records."""

import asyncio
import uuid

from sqlalchemy import select

from kuralgpt.db.session import get_session_factory
from kuralgpt.models import LlmCall


def test_llm_call_can_be_saved_and_retrieved():
    request_id = f"test-{uuid.uuid4().hex}"

    async def verify_record():
        session_factory = get_session_factory()

        async with session_factory() as session:
            try:
                call = LlmCall(
                    request_id=request_id,
                    provider="test-provider",
                    model="test-model",
                    purpose="chat",
                    prompt_version="v1",
                    status="ok",
                    error="",
                    tokens_in=10,
                    tokens_out=20,
                    latency_ms=100,
                    cost_inr=0.01,
                    fallback_used=False,
                )

                session.add(call)
                await session.commit()

                result = await session.execute(
                    select(LlmCall).where(LlmCall.request_id == request_id)
                )

                saved_call = result.scalar_one()

                assert saved_call.provider == "test-provider"
                assert saved_call.model == "test-model"
                assert saved_call.tokens_in == 10
                assert saved_call.tokens_out == 20
                assert saved_call.fallback_used is False

            except Exception:
                await session.rollback()
                raise

    asyncio.run(verify_record())
