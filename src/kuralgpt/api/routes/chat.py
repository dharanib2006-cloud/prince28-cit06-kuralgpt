"""POST /v1/chat (streaming) and GET /v1/usage (LLM usage and cost)."""

import json
from collections.abc import AsyncIterator
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from kuralgpt.api.deps import GatewayDep, UsageDep
from kuralgpt.llm.classify import classify
from kuralgpt.llm.gateway import LLMResult, LLMUnavailable

router = APIRouter(tags=["chat"])

PROMPT_VERSION = "chat_system_v1"
CLASSIFY_PROMPT_VERSION = "classify_v4"

PERSONAL_ANSWER = "I can't know that."
OFF_TOPIC_ANSWER = (
    "I can only help with questions about Thirukkural, Tamil classics, and their use in teaching."
)


def load_prompt(directory: Path, name: str = PROMPT_VERSION) -> str:
    """Read a prompt file. A missing file stops the app at startup."""
    return (directory / f"{name}.md").read_text(encoding="utf-8").strip()


class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    stream: bool = True
    history: list[HistoryMessage] = Field(default_factory=list, max_length=6)


def sse(data: dict, event: str = "") -> str:
    """Build one server-sent event."""
    head = f"event: {event}\n" if event else ""
    return f"{head}data: {json.dumps(data, ensure_ascii=False)}\n\n"


def summary(result: LLMResult) -> dict:
    """Return result metadata without the answer text."""
    return {key: value for key, value in asdict(result).items() if key != "text"}


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request: Request,
    gateway: GatewayDep,
):
    try:
        label, classification_result = await classify(
            gateway,
            request.app.state.classify_prompt,
            CLASSIFY_PROMPT_VERSION,
            body.message,
        )

        if label in {"personal", "off_topic"}:
            answer = PERSONAL_ANSWER if label == "personal" else OFF_TOPIC_ANSWER

            if not body.stream:
                return {
                    "answer": answer,
                    **summary(classification_result),
                }

            async def fixed_events() -> AsyncIterator[str]:
                yield sse({"delta": answer})
                yield sse(summary(classification_result), event="done")

            return StreamingResponse(
                fixed_events(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        messages = [
            {"role": "system", "content": request.app.state.system_prompt},
            *[item.model_dump() for item in body.history],
            {"role": "user", "content": body.message},
        ]

        if not body.stream:
            result = await gateway.generate(
                messages,
                prompt_version=PROMPT_VERSION,
            )
            return {"answer": result.text, **summary(result)}

        stream = gateway.stream(
            messages,
            prompt_version=PROMPT_VERSION,
        )
        first = await anext(stream)

    except LLMUnavailable as exc:
        raise HTTPException(
            status_code=503,
            detail=f"No model could answer: {exc}",
        ) from exc

    async def events() -> AsyncIterator[str]:
        item: str | LLMResult = first

        try:
            while True:
                if isinstance(item, LLMResult):
                    yield sse(summary(item), event="done")
                    return

                yield sse({"delta": item})
                item = await anext(stream)

        except LLMUnavailable as exc:
            yield sse({"detail": str(exc)}, event="error")

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/usage")
async def usage(
    repo: UsageDep,
    days: Annotated[int, Query(ge=1, le=90)] = 7,
) -> dict:
    """Return daily LLM calls, tokens, errors, fallbacks and rupee costs."""
    rows = await repo.by_day(days)

    return {
        "days": rows,
        "calls": sum(row["calls"] for row in rows),
        "errors": sum(row["errors"] for row in rows),
        "fallbacks": sum(row["fallbacks"] for row in rows),
        "tokens_in": sum(row["tokens_in"] for row in rows),
        "tokens_out": sum(row["tokens_out"] for row in rows),
        "total_cost_inr": round(
            sum(row["cost_inr"] for row in rows),
            4,
        ),
    }
