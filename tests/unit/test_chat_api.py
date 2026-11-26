from pathlib import Path

from kuralgpt.api.deps import get_gateway
from kuralgpt.api.routes.chat import load_prompt


def test_load_prompt():
    prompt = load_prompt(Path("prompts"))

    assert "KuralGPT" in prompt
    assert "I am not sure" in prompt


def test_chat_non_streaming(client):
    response = client.post(
        "/v1/chat",
        json={"message": "Explain the first kural", "stream": False},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["answer"] == "This is a test answer."
    assert data["provider"] == "fake"
    assert data["model"] == "fake-1"
    assert data["tokens_in"] == 12
    assert data["tokens_out"] == 8
    assert data["fallback_used"] is False


def test_chat_streaming(client):
    response = client.post(
        "/v1/chat",
        json={"message": "Explain the first kural", "stream": True},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in response.text
    assert '"delta": "This is "' in response.text
    assert '"delta": "a test answer."' in response.text


def test_chat_rejects_empty_message(client):
    response = client.post(
        "/v1/chat",
        json={"message": "", "stream": False},
    )

    assert response.status_code == 422


def test_chat_rejects_message_over_4000_characters(client):
    response = client.post(
        "/v1/chat",
        json={"message": "a" * 4001, "stream": False},
    )

    assert response.status_code == 422


def test_usage_summary(client):
    response = client.get("/v1/usage")

    assert response.status_code == 200

    data = response.json()

    assert data["calls"] == 4
    assert data["errors"] == 1
    assert data["fallbacks"] == 2
    assert data["tokens_in"] == 500
    assert data["tokens_out"] == 300
    assert data["total_cost_inr"] == 0.05

    assert len(data["days"]) == 1
    assert data["days"][0]["calls"] == 4
    assert data["days"][0]["errors"] == 1
    assert data["days"][0]["fallbacks"] == 2
    assert data["days"][0]["tokens_in"] == 500
    assert data["days"][0]["tokens_out"] == 300


def test_usage_rejects_invalid_days(client):
    response = client.get("/v1/usage?days=100")

    assert response.status_code == 422


def test_llm_status_returns_providers_and_breaker_states(client):
    response = client.get("/v1/llm/status")

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "providers": [
            {
                "name": "gemini",
                "model": "gemini-test",
                "breaker_state": "closed",
            },
            {
                "name": "groq",
                "model": "groq-test",
                "breaker_state": "closed",
            },
        ]
    }


def test_llm_status_reflects_breaker_state_changes(client):
    gateway = client.app.dependency_overrides[get_gateway]()

    gateway.breakers["gemini"].failure()
    gateway.breakers["gemini"].failure()
    gateway.breakers["gemini"].failure()

    response = client.get("/v1/llm/status")

    assert response.status_code == 200
    assert response.json()["providers"][0]["breaker_state"] == "open"

    gateway.breakers["gemini"]._opened_at -= gateway.breakers["gemini"].cooldown

    response = client.get("/v1/llm/status")

    assert response.status_code == 200
    assert response.json()["providers"][0]["breaker_state"] == "half-open"
