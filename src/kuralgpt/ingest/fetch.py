"""Polite, resumable downloader for KuralGPT data sources."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from protego import Protego

USER_AGENT = (
    "examate-student-bot/0.1 "
    "(student project; "
    "+https://github.com/dharanib2006-cloud/prince28-cit06-kuralgpt)"
)
ROBOTS_TOKEN = "examate-student-bot"

MAX_BYTES = 200 * 1024 * 1024
ATTEMPT_TIMEOUT = 300
MAX_ATTEMPTS = 4
MAX_RETRY_WAIT = 120
MAX_CONCURRENT = 4
DEFAULT_HOST_DELAY = 0.5

RETRY_STATUSES = {408, 425, 429, 500, 502, 503, 504}

MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    "application/json": ".json",
    "text/html": ".html",
    "text/plain": ".txt",
    "application/xml": ".xml",
    "text/xml": ".xml",
}


@dataclass
class FetchResult:
    """Result of one download attempt."""

    url: str
    status: str
    path: str | None = None
    sha256: str | None = None
    size: int = 0
    error: str | None = None
    content_type: str | None = None
    http_status: int | None = None


class DownloadTooLargeError(Exception):
    """Raised when a streamed download exceeds the size limit."""


class Manifest:
    """Append-only JSONL manifest of download results."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def records(self) -> list[dict]:
        if not self.path.exists():
            return []

        records = []

        with self.path.open("r", encoding="utf-8") as file:
            for line in file:
                try:
                    record = json.loads(line)
                    if isinstance(record, dict):
                        records.append(record)
                except json.JSONDecodeError:
                    continue

        return records

    def completed_urls(self) -> set[str]:
        """Return URLs whose latest manifest record is completed."""
        latest = {}

        for record in self.records():
            url = record.get("url")
            if url:
                latest[url] = record.get("status")

        return {url for url, status in latest.items() if status == "completed"}

    def done(self, url: str, root: Path) -> bool:
        """Check completion and confirm that the downloaded file exists."""
        for record in reversed(self.records()):
            if record.get("url") != url:
                continue

            if record.get("status") != "completed":
                return False

            relative_path = record.get("path")

            if not relative_path:
                return False

            return (root / relative_path).is_file()

        return False

    def append(
        self,
        result: FetchResult,
        root: Path | None = None,
    ) -> None:
        """Append one download result to the manifest."""
        relative_path = None

        if result.path:
            result_path = Path(result.path)

            if root is not None:
                try:
                    relative_path = result_path.relative_to(root).as_posix()
                except ValueError:
                    relative_path = result_path.as_posix()
            else:
                relative_path = result_path.as_posix()

        record = asdict(result)
        record["path"] = relative_path
        record["downloaded_at"] = datetime.now(UTC).isoformat()

        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")

    def append_repository(
        self,
        repository: str,
        commit_sha: str,
    ) -> None:
        """Record the repository and commit used for ingestion."""
        record = {
            "type": "repository",
            "repository": repository,
            "commit_sha": commit_sha,
            "downloaded_at": datetime.now(UTC).isoformat(),
        }

        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")


class Robots:
    """Fetch and cache robots.txt rules per origin."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.cache: dict[str, Protego | None] = {}
        self.locks: dict[str, asyncio.Lock] = {}

    async def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{origin}/robots.txt"

        lock = self.locks.setdefault(origin, asyncio.Lock())

        async with lock:
            if robots_url not in self.cache:
                try:
                    response = await self.client.get(
                        robots_url,
                        timeout=30,
                    )

                    if response.status_code == 200:
                        self.cache[robots_url] = Protego.parse(response.text)

                    elif 400 <= response.status_code < 500 and response.status_code != 429:
                        self.cache[robots_url] = None

                    else:
                        return False

                except httpx.HTTPError:
                    return False

        rules = self.cache[robots_url]

        return rules is None or rules.can_fetch(url, ROBOTS_TOKEN)

    def crawl_delay(self, url: str) -> float:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        rules = self.cache.get(f"{origin}/robots.txt")

        if rules is None:
            return 0.0

        delay = rules.crawl_delay(ROBOTS_TOKEN)

        return max(0.0, float(delay or 0.0))


class HostGate:
    """Space requests to the same host."""

    def __init__(self, default_delay: float = DEFAULT_HOST_DELAY):
        self.default_delay = default_delay
        self.locks: dict[str, asyncio.Lock] = {}
        self.last_request: dict[str, float] = {}

    async def wait(self, url: str, delay: float = 0.0) -> None:
        host = urlparse(url).netloc
        lock = self.locks.setdefault(host, asyncio.Lock())
        required_delay = max(self.default_delay, delay)

        async with lock:
            elapsed = time.monotonic() - self.last_request.get(host, 0.0)

            if elapsed < required_delay:
                await asyncio.sleep(required_delay - elapsed)

            self.last_request[host] = time.monotonic()


def retry_wait(attempt: int, retry_after: str | None = None) -> float:
    """Return a capped Retry-After value or exponential backoff with jitter."""
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            try:
                retry_date = parsedate_to_datetime(retry_after)

                if retry_date.tzinfo is None:
                    retry_date = retry_date.replace(tzinfo=UTC)

                seconds = (retry_date - datetime.now(UTC)).total_seconds()

            except (TypeError, ValueError, OverflowError):
                seconds = -1

        if seconds >= 0:
            return min(seconds, MAX_RETRY_WAIT)

    ceiling = min(MAX_RETRY_WAIT, 2**attempt)

    return random.uniform(
        ceiling,
        min(ceiling + 1, MAX_RETRY_WAIT),
    )


def file_stem(url: str, source: str) -> str:
    """Create a readable, stable filename from source and URL."""
    parsed = urlparse(url)
    name = Path(parsed.path).stem or "download"

    safe_source = "".join(char if char.isalnum() or char in "-_" else "-" for char in source)

    safe_name = "".join(char if char.isalnum() or char in "-_" else "-" for char in name)

    suffix = hashlib.sha256(url.encode("utf-8")).hexdigest()[:8]

    return f"{safe_source}-{safe_name}-{suffix}"


def pick_extension(
    url: str,
    content_type: str | None,
) -> str:
    """Preserve a known URL extension or infer one from Content-Type."""
    suffix = Path(urlparse(url).path).suffix.lower()

    if suffix and len(suffix) <= 10:
        return suffix

    media_type = (content_type or "").split(";")[0].strip().lower()

    return MIME_EXTENSIONS.get(media_type, ".bin")


class Fetcher:
    """Download permitted files with retries and resume support."""

    def __init__(
        self,
        output_dir: Path = Path("data/raw"),
        manifest_path: Path = Path("data/manifest.jsonl"),
        max_concurrent: int = MAX_CONCURRENT,
        per_host_delay: float = DEFAULT_HOST_DELAY,
        client: httpx.AsyncClient | None = None,
    ):
        if not 1 <= max_concurrent <= MAX_CONCURRENT:
            raise ValueError("max_concurrent must be between 1 and 4")

        self.output_dir = Path(output_dir)
        self.root = self.output_dir.parent
        self.manifest = Manifest(Path(manifest_path))
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.client = client
        self.owns_client = client is None
        self.robots: Robots | None = None
        self.host_gate = HostGate(per_host_delay)

    async def __aenter__(self) -> Fetcher:
        if self.client is None:
            self.client = httpx.AsyncClient(
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=httpx.Timeout(30, connect=10),
                limits=httpx.Limits(
                    max_connections=MAX_CONCURRENT,
                    max_keepalive_connections=MAX_CONCURRENT,
                ),
            )

        self.robots = Robots(self.client)

        return self

    async def __aexit__(
        self,
        exc_type,
        exc,
        traceback,
    ) -> None:
        if self.owns_client and self.client is not None:
            await self.client.aclose()

    def destination(
        self,
        url: str,
        source: str,
        content_type: str | None = None,
    ) -> Path:
        stem = file_stem(url, source)
        extension = pick_extension(url, content_type)

        return self.output_dir / source / f"{stem}{extension}"

    async def fetch_one(
        self,
        url: str,
        source: str,
    ) -> FetchResult:
        if self.client is None or self.robots is None:
            raise RuntimeError("Use Fetcher with 'async with'")

        if not await self.robots.allowed(url):
            return FetchResult(
                url=url,
                status="blocked",
                error="Robots.txt disallows access or could not be checked",
            )

        for attempt in range(MAX_ATTEMPTS):
            try:
                await self.host_gate.wait(
                    url,
                    self.robots.crawl_delay(url),
                )

                async with self.semaphore:
                    async with asyncio.timeout(ATTEMPT_TIMEOUT):
                        result = await self._download(url, source)

                if result.status == "retry":
                    if attempt + 1 >= MAX_ATTEMPTS:
                        return FetchResult(
                            url=url,
                            status="failed",
                            error=f"HTTP {result.http_status} after maximum attempts",
                            http_status=result.http_status,
                        )

                    wait = retry_wait(attempt, result.error)
                    await asyncio.sleep(wait)
                    continue

                return result

            except (httpx.TransportError, TimeoutError) as exc:
                if attempt + 1 >= MAX_ATTEMPTS:
                    return FetchResult(
                        url=url,
                        status="failed",
                        error=f"Network error after {MAX_ATTEMPTS} attempts: {exc}",
                    )

                await asyncio.sleep(retry_wait(attempt))

            except (OSError, ValueError) as exc:
                return FetchResult(
                    url=url,
                    status="failed",
                    error=str(exc),
                )

        return FetchResult(
            url=url,
            status="failed",
            error="Maximum attempts reached",
        )

    async def _download(
        self,
        url: str,
        source: str,
    ) -> FetchResult:
        assert self.client is not None

        async with self.client.stream(
            "GET",
            url,
            timeout=ATTEMPT_TIMEOUT,
        ) as response:
            status = response.status_code

            if status in RETRY_STATUSES:
                return FetchResult(
                    url=url,
                    status="retry",
                    error=response.headers.get("Retry-After"),
                    http_status=status,
                )

            if status != 200:
                return FetchResult(
                    url=url,
                    status="failed",
                    error=f"HTTP {status}",
                    http_status=status,
                )

            content_length = response.headers.get("Content-Length")

            if content_length:
                try:
                    if int(content_length) > MAX_BYTES:
                        return FetchResult(
                            url=url,
                            status="too_large",
                            error="Content-Length exceeds 200 MB",
                            http_status=status,
                        )
                except ValueError:
                    pass

            content_type = response.headers.get("Content-Type")

            destination = self.destination(
                url,
                source,
                content_type,
            )

            destination.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            part_path = destination.with_name(destination.name + ".part")

            digest = hashlib.sha256()
            size = 0

            try:
                with part_path.open("wb") as file:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)

                        if size > MAX_BYTES:
                            raise DownloadTooLargeError("Download exceeded 200 MB")

                        file.write(chunk)
                        digest.update(chunk)

                part_path.replace(destination)

            except DownloadTooLargeError as exc:
                part_path.unlink(missing_ok=True)

                return FetchResult(
                    url=url,
                    status="too_large",
                    error=str(exc),
                    http_status=status,
                )

            except BaseException:
                part_path.unlink(missing_ok=True)
                raise

            return FetchResult(
                url=url,
                status="completed",
                path=str(destination),
                sha256=digest.hexdigest(),
                size=size,
                content_type=content_type,
                http_status=status,
            )

    async def fetch_all(
        self,
        sources: list[dict[str, str]],
        on_result=None,
    ) -> dict[str, int]:
        counts = {
            "completed": 0,
            "blocked": 0,
            "failed": 0,
            "too_large": 0,
            "skipped": 0,
        }

        pending = []

        for item in sources:
            if self.manifest.done(item["url"], self.root):
                counts["skipped"] += 1
            else:
                pending.append(item)

        async def process(item: dict[str, str]) -> None:
            result = await self.fetch_one(
                item["url"],
                item["source"],
            )

            self.manifest.append(result, self.root)

            counts[result.status] = counts.get(result.status, 0) + 1

            if on_result is not None:
                callback_result = on_result(result)

                if asyncio.iscoroutine(callback_result):
                    await callback_result

        await asyncio.gather(*(process(item) for item in pending))

        return counts
