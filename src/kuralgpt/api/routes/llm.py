"""LLM provider health and circuit-breaker status."""

from fastapi import APIRouter

from kuralgpt.api.deps import GatewayDep

router = APIRouter(prefix="/v1/llm", tags=["llm"])


@router.get("/status")
async def llm_status(gateway: GatewayDep) -> dict:
    """Return the configured providers and their breaker states."""
    return {
        "providers": [
            {
                "name": provider.name,
                "model": provider.model,
                "breaker_state": gateway.breakers[provider.name].state,
            }
            for provider in gateway.providers
        ]
    }
