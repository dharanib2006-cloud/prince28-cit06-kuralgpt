"""Start document ingestion through the KuralGPT API and monitor progress."""

import argparse
import sys
import time

import httpx

from kuralgpt.config import get_settings


def main() -> None:
    """Submit an ingestion job and watch it until completion."""
    parser = argparse.ArgumentParser(description="Run document ingestion through the API.")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="API base URL")
    parser.add_argument("--limit", type=int, default=20, help="Maximum records to ingest")
    parser.add_argument("--source", default="", help="Filter records by source")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Retry previously failed records",
    )
    parser.add_argument("--interval", type=float, default=2.0, help="Polling interval in seconds")
    args = parser.parse_args()

    if args.limit < 1 or args.limit > 2000:
        parser.error("--limit must be between 1 and 2000")
    if args.interval <= 0:
        parser.error("--interval must be greater than 0")

    settings = get_settings()
    if not settings.admin_token:
        print("ERROR: admin_token is missing from your .env file.")
        sys.exit(1)

    base_url = args.url.rstrip("/")
    headers = {"Authorization": f"Bearer {settings.admin_token}"}
    payload = {
        "limit": args.limit,
        "source": args.source,
        "retry_failed": args.retry_failed,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            print("Starting document ingestion...")
            response = client.post(
                f"{base_url}/v1/ingest",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            result = response.json()

            job_id = result.get("job_id")
            queued = result.get("queued", 0)

            if not job_id:
                print(result.get("detail", "No documents to ingest."))
                return

            print(f"Job ID: {job_id}")
            print(f"Queued: {queued} documents")

            while True:
                response = client.get(
                    f"{base_url}/v1/ingest/{job_id}",
                    headers=headers,
                )
                response.raise_for_status()
                progress = response.json()

                counts = progress.get("counts", {})
                items = progress.get("items", [])
                statuses = [item.get("status") for item in items]

                completed = counts.get("completed", 0)
                skipped = counts.get("skipped", 0)
                failed = counts.get("failed", 0)

                print(
                    f"Progress: completed={completed}, "
                    f"skipped={skipped}, failed={failed}, "
                    f"queued={counts.get('queued', 0)}, "
                    f"running={counts.get('running', 0)}"
                )

                pending = any(status in {"queued", "running", "processing"} for status in statuses)

                if len(statuses) >= queued and not pending:
                    break

                time.sleep(args.interval)

            print("\nIngestion job finished.")
            print(f"Completed: {completed}")
            print(f"Skipped:   {skipped}")
            print(f"Failed:    {failed}")

            if failed:
                print(f"Check failed records at {base_url}/v1/ingest/dead-letter")
                sys.exit(1)

    except httpx.HTTPStatusError as exc:
        print(f"API error: HTTP {exc.response.status_code}")
        print(exc.response.text[:500])
        sys.exit(1)
    except httpx.HTTPError as exc:
        print(f"Could not connect to the KuralGPT API: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
