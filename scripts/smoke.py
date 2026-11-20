import argparse
import sys
import time

import httpx


def check_endpoint(
    client: httpx.Client,
    path: str,
    expected_status: int = 200,
) -> httpx.Response:
    response = client.get(path)

    if response.status_code != expected_status:
        raise RuntimeError(
            f"FAIL {path} -> expected {expected_status}, received {response.status_code}"
        )

    print(f"ok {path} -> {response.status_code}")
    return response


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--expect-version")
    parser.add_argument("--attempts", type=int, default=30)
    parser.add_argument("--delay", type=int, default=10)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")

    try:
        with httpx.Client(
            base_url=base_url,
            timeout=20.0,
        ) as client:
            for attempt in range(args.attempts):
                try:
                    health = check_endpoint(client, "/health")
                    health_data = health.json()
                    version = health_data.get("git_sha", "unknown")
                    print(f"   version: {version}")

                    if args.expect_version and version != args.expect_version:
                        print(f"Waiting for version {args.expect_version}; current: {version}")
                        time.sleep(args.delay)
                        continue

                    ready = check_endpoint(client, "/ready")
                    ready_data = ready.json()

                    if ready_data.get("status") != "ready" or not ready_data.get("checks", {}).get(
                        "database"
                    ):
                        raise RuntimeError("Database is not ready")

                    documents = check_endpoint(
                        client,
                        "/v1/documents?limit=1",
                    )

                    if not isinstance(documents.json().get("items"), list):
                        raise RuntimeError("Invalid documents response")

                    print("Smoke test passed")
                    return 0

                except (httpx.HTTPError, RuntimeError, ValueError) as exc:
                    print(f"Attempt {attempt + 1}: {exc}")

                    if attempt + 1 < args.attempts:
                        time.sleep(args.delay)

    except httpx.HTTPError as exc:
        print(f"Smoke test failed: {exc}")
        return 1

    print("Smoke test failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
