"""Ask KuralGPT a question and display the answer with usage details."""

import argparse
import asyncio
import json
import time
import uuid
from dataclasses import asdict

from kuralgpt.api.routes.chat import PROMPT_VERSION, load_prompt
from kuralgpt.config import get_settings
from kuralgpt.db.llm_calls import record_call
from kuralgpt.llm.gateway import LLMResult, LLMUnavailable, build_gateway
from kuralgpt.logging_setup import request_id_ctx


async def ask(question: str, json_output: bool = False) -> None:
    """Send a question through the LLM gateway."""
    settings = get_settings()
    gateway = build_gateway(settings, recorder=record_call)

    request_id = str(uuid.uuid4())
    token = request_id_ctx.set(request_id)

    messages = [
        {
            "role": "system",
            "content": load_prompt(settings.prompts_dir),
        },
        {"role": "user", "content": question},
    ]

    started = time.perf_counter()

    try:
        if json_output:
            result = await gateway.generate(
                messages,
                prompt_version=PROMPT_VERSION,
            )
            print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
            return

        print("\nKuralGPT: ", end="", flush=True)

        final_result = None

        async for item in gateway.stream(
            messages,
            prompt_version=PROMPT_VERSION,
        ):
            if isinstance(item, LLMResult):
                final_result = item
            else:
                print(item, end="", flush=True)

        if final_result is None:
            raise RuntimeError("Gateway finished without usage information.")

        elapsed_ms = round((time.perf_counter() - started) * 1000)

        print("\n\n--- Usage ---")
        print(f"Provider       : {final_result.provider}")
        print(f"Model          : {final_result.model}")
        print(f"Input tokens   : {final_result.tokens_in}")
        print(f"Output tokens  : {final_result.tokens_out}")
        print(f"Cost           : ₹{final_result.cost_inr:.6f}")
        print(f"Attempts       : {final_result.attempts}")
        print(f"Fallback used  : {final_result.fallback_used}")
        print(f"Response time  : {elapsed_ms} ms")

    except LLMUnavailable as exc:
        print(f"\nKuralGPT could not answer: {exc}")

    finally:
        request_id_ctx.reset(token)


def main() -> None:
    """Parse command-line arguments and run the chat."""
    parser = argparse.ArgumentParser(description="Ask KuralGPT")
    parser.add_argument("question", help="Your question for KuralGPT")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Return the response and usage as JSON instead of streaming",
    )

    args = parser.parse_args()
    asyncio.run(ask(args.question, args.json))


if __name__ == "__main__":
    main()
