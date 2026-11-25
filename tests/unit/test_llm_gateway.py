"""Unit tests for the LLM gateway."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from kuralgpt.llm.gateway import (
    CircuitBreaker,
    FakeLLM,
    LLMError,
    LLMGateway,
    LLMResult,
    LLMUnavailable,
    Reply,
    cost_inr,
    estimate_tokens,
)

MESSAGES = [{"role": "user", "content": "Hello"}]


async def no_sleep(seconds):
    """Avoid real waiting during retry tests."""


def test_cost_inr_for_gemini():
    cost = cost_inr("gemini-3.6-flash", 1_000_000, 1_000_000, 95)
    assert cost == 427.5


def test_cost_inr_for_groq():
    cost = cost_inr("openai/gpt-oss-20b", 1_000_000, 1_000_000, 95)
    assert cost == 35.625


def test_unknown_model_cost_is_zero():
    assert cost_inr("unknown-model", 1000, 1000, 95) == 0


def test_estimate_tokens_for_text():
    assert estimate_tokens("abcdefgh") == 2


def test_estimate_tokens_for_empty_text():
    assert estimate_tokens("") == 1


def test_llm_error_stores_retry_information():
    error = LLMError("Temporary failure", retryable=True, retry_after=2)

    assert str(error) == "Temporary failure"
    assert error.retryable is True
    assert error.retry_after == 2


def test_circuit_breaker_starts_closed():
    breaker = CircuitBreaker(threshold=2)

    assert breaker.state == "closed"
    assert breaker.allow() is True


def test_circuit_breaker_opens_after_threshold():
    breaker = CircuitBreaker(threshold=2)

    breaker.failure()
    breaker.failure()

    assert breaker.state == "open"
    assert breaker.allow() is False


def test_circuit_breaker_becomes_half_open_after_cooldown():
    current_time = [10.0]
    breaker = CircuitBreaker(
        threshold=1,
        cooldown=5,
        clock=lambda: current_time[0],
    )

    breaker.failure()
    assert breaker.state == "open"

    current_time[0] = 16.0

    assert breaker.state == "half-open"
    assert breaker.allow() is True


def test_circuit_breaker_success_resets_failures():
    breaker = CircuitBreaker(threshold=2)

    breaker.failure()
    breaker.success()

    assert breaker.failures == 0
    assert breaker.state == "closed"


def test_fake_llm_generate():
    provider = FakeLLM(script=["Hello there"])

    result = asyncio.run(provider.generate(MESSAGES))

    assert isinstance(result, Reply)
    assert result.text == "Hello there"
    assert result.tokens_in == 12
    assert result.tokens_out == 2


def test_fake_llm_stream():
    provider = FakeLLM(script=["Hello there"])

    async def collect():
        usage = Reply()
        pieces = [piece async for piece in provider.stream(MESSAGES, usage)]
        return pieces, usage

    pieces, usage = asyncio.run(collect())

    assert "".join(pieces) == "Hello there "
    assert usage.tokens_in == 12
    assert usage.tokens_out == 2


def test_gateway_generate_success_and_recording():
    recorder = AsyncMock()
    provider = FakeLLM(name="primary", model="fake-1", script=["Hello"])

    gateway = LLMGateway(
        [provider],
        recorder=recorder,
        sleep=no_sleep,
    )

    result = asyncio.run(gateway.generate(MESSAGES, prompt_version="v1"))

    assert result.text == "Hello"
    assert result.provider == "primary"
    assert result.fallback_used is False
    recorder.assert_awaited_once()

    recorded_row = recorder.await_args.args[0]
    assert recorded_row["status"] == "ok"
    assert recorded_row["provider"] == "primary"
    assert recorded_row["prompt_version"] == "v1"


def test_gateway_retries_temporary_failure():
    provider = FakeLLM(
        name="primary",
        script=[
            LLMError("Temporary error", retryable=True),
            "Recovered",
        ],
    )

    gateway = LLMGateway(
        [provider],
        max_attempts=2,
        sleep=no_sleep,
    )

    result = asyncio.run(gateway.generate(MESSAGES))

    assert result.text == "Recovered"
    assert result.attempts == 2
    assert provider.calls == 2


def test_gateway_uses_fallback_after_non_retryable_failure():
    primary = FakeLLM(
        name="primary",
        script=[LLMError("Invalid request", retryable=False)],
    )
    fallback = FakeLLM(name="fallback", script=["Fallback answer"])

    gateway = LLMGateway(
        [primary, fallback],
        sleep=no_sleep,
    )

    result = asyncio.run(gateway.generate(MESSAGES))

    assert result.text == "Fallback answer"
    assert result.provider == "fallback"
    assert result.fallback_used is True
    assert primary.calls == 1


def test_gateway_raises_when_all_providers_fail():
    primary = FakeLLM(
        name="primary",
        script=[LLMError("Primary down", retryable=False)],
    )
    fallback = FakeLLM(
        name="fallback",
        script=[LLMError("Fallback down", retryable=False)],
    )

    gateway = LLMGateway(
        [primary, fallback],
        sleep=no_sleep,
    )

    with pytest.raises(LLMUnavailable):
        asyncio.run(gateway.generate(MESSAGES))


def test_gateway_skips_open_circuit():
    primary = FakeLLM(name="primary", script=["Should not be called"])
    fallback = FakeLLM(name="fallback", script=["Fallback answer"])

    gateway = LLMGateway([primary, fallback])
    gateway.breakers["primary"].failure()
    gateway.breakers["primary"].failure()
    gateway.breakers["primary"].failure()

    result = asyncio.run(gateway.generate(MESSAGES))

    assert primary.calls == 0
    assert fallback.calls == 1
    assert result.provider == "fallback"


def test_gateway_stream_success():
    provider = FakeLLM(name="primary", script=["Hello world"])
    gateway = LLMGateway([provider])

    async def collect():
        return [item async for item in gateway.stream(MESSAGES)]

    items = asyncio.run(collect())

    assert items[:-1] == ["Hello ", "world "]
    assert isinstance(items[-1], LLMResult)
    assert items[-1].text == "Hello world "


def test_gateway_stream_falls_back_before_first_piece():
    primary = FakeLLM(
        name="primary",
        script=[LLMError("Connection failed", retryable=True)],
    )
    fallback = FakeLLM(name="fallback", script=["Fallback answer"])

    gateway = LLMGateway([primary, fallback])

    async def collect():
        return [item async for item in gateway.stream(MESSAGES)]

    items = asyncio.run(collect())

    assert "".join(item for item in items if isinstance(item, str)) == ("Fallback answer ")
    assert items[-1].provider == "fallback"
    assert items[-1].fallback_used is True


def test_gateway_stream_does_not_fallback_mid_answer():
    primary = FakeLLM(
        name="primary",
        script=[
            (
                "partial",
                LLMError("Stream interrupted", retryable=True),
            )
        ],
    )
    fallback = FakeLLM(name="fallback", script=["Fallback answer"])

    gateway = LLMGateway([primary, fallback])

    async def collect():
        return [item async for item in gateway.stream(MESSAGES)]

    with pytest.raises(LLMUnavailable, match="failed mid-answer"):
        asyncio.run(collect())

    assert fallback.calls == 0


def test_recorder_failure_does_not_break_gateway():
    recorder = AsyncMock(side_effect=RuntimeError("Database unavailable"))
    provider = FakeLLM(name="primary", script=["Still works"])

    gateway = LLMGateway(
        [provider],
        recorder=recorder,
        sleep=no_sleep,
    )

    result = asyncio.run(gateway.generate(MESSAGES))

    assert result.text == "Still works"
    recorder.assert_awaited_once()
