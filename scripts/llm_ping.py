"""Check direct connectivity to Gemini and Groq using raw HTTP requests."""

import time

import httpx

from kuralgpt.config import get_settings


def ping_provider(
    name: str,
    api_key: str,
    model: str,
    base_url: str,
    timeout: float,
) -> None:
    """Send one simple chat request and print the result."""

    if not api_key:
        print(f"{name:<7} FAILED   API key is missing in .env")
        return

    url = f"{base_url.rstrip('/')}/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": "What is 2 + 2? Reply with only the answer.",
            }
        ],
        "max_tokens": 128,
    }

    start = time.perf_counter()

    try:
        response = httpx.post(
            url,
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.raise_for_status()

        result = response.json()
        message = result["choices"][0]["message"]
        answer = message.get("content") or ""
        usage = result.get("usage", {})

        tokens_in = usage.get("prompt_tokens", 0)
        tokens_out = usage.get("completion_tokens", 0)

        if answer.strip():
            print(
                f"{name:<7} OK       {model} said "
                f"{answer!r} in {elapsed_ms} ms, "
                f"tokens in={tokens_in} out={tokens_out}"
            )
        else:
            print(
                f"{name:<7} EMPTY    HTTP request succeeded, "
                f"but the response content was empty. "
                f"Finish reason: {result['choices'][0].get('finish_reason')}, "
                f"tokens in={tokens_in} out={tokens_out}"
            )

    except httpx.TimeoutException:
        print(f"{name:<7} FAILED   Request timed out after {timeout} seconds")

    except httpx.HTTPStatusError as exc:
        print(f"{name:<7} FAILED   HTTP {exc.response.status_code}: {exc.response.text[:300]}")

    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        print(f"{name:<7} FAILED   {type(exc).__name__}: {str(exc)[:300]}")


def main() -> None:
    """Test both configured LLM providers."""

    settings = get_settings()

    print("Testing direct LLM provider connections...\n")

    # Use a longer timeout for this connectivity check.
    timeout = max(settings.llm_timeout_seconds, 60.0)

    ping_provider(
        name="gemini",
        api_key=settings.gemini_api_key,
        model=settings.llm_primary_model,
        base_url=settings.llm_primary_base_url,
        timeout=timeout,
    )

    ping_provider(
        name="groq",
        api_key=settings.groq_api_key,
        model=settings.llm_fallback_model,
        base_url=settings.llm_fallback_base_url,
        timeout=timeout,
    )


if __name__ == "__main__":
    main()
