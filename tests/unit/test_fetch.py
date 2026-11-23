"""Offline tests for the KuralGPT downloader."""

import asyncio
import hashlib
import json
from pathlib import Path

import httpx
import pytest

from kuralgpt.ingest.fetch import (
    MAX_BYTES,
    Fetcher,
    FetchResult,
    HostGate,
    Manifest,
    Robots,
    retry_wait,
)


def make_client(handler):
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        headers={"User-Agent": "examate-student-bot/0.1"},
    )


def robots_404_and_document(handler):
    def wrapped(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        return handler(request)

    return wrapped


def test_manifest_creates_parent_directory(tmp_path):
    path = tmp_path / "nested" / "manifest.jsonl"

    Manifest(path)

    assert path.parent.exists()


def test_manifest_returns_empty_when_missing(tmp_path):
    manifest = Manifest(tmp_path / "manifest.jsonl")

    assert manifest.completed_urls() == set()


def test_manifest_reads_completed_urls(tmp_path):
    path = tmp_path / "manifest.jsonl"

    path.write_text(
        '{"url":"https://example.com/a","status":"completed"}\n',
        encoding="utf-8",
    )

    assert Manifest(path).completed_urls() == {"https://example.com/a"}


def test_manifest_ignores_invalid_json(tmp_path):
    path = tmp_path / "manifest.jsonl"

    path.write_text(
        "invalid json\n",
        encoding="utf-8",
    )

    assert Manifest(path).completed_urls() == set()


def test_manifest_appends_result(tmp_path):
    path = tmp_path / "manifest.jsonl"
    manifest = Manifest(path)

    manifest.append(
        FetchResult(
            url="https://example.com/a",
            status="completed",
            sha256="abc",
            size=10,
        )
    )

    record = json.loads(path.read_text(encoding="utf-8"))

    assert record["status"] == "completed"
    assert record["sha256"] == "abc"


def test_retry_wait_respects_numeric_retry_after():
    assert retry_wait(1, "10") == 10


def test_retry_wait_caps_retry_after():
    assert retry_wait(1, "500") == 120


def test_retry_wait_uses_backoff():
    wait = retry_wait(1)

    assert 2 <= wait <= 3


def test_fetcher_rejects_more_than_four_connections():
    with pytest.raises(ValueError):
        Fetcher(max_concurrent=5)


def test_fetcher_rejects_zero_connections():
    with pytest.raises(ValueError):
        Fetcher(max_concurrent=0)


def test_destination_uses_source_folder(tmp_path):
    fetcher = Fetcher(output_dir=tmp_path)

    path = fetcher.destination(
        "https://example.com/book.pdf",
        "test-source",
    )

    assert path.parent == tmp_path / "test-source"
    assert path.name.endswith(".pdf")
    assert "test-source" in path.name


@pytest.mark.asyncio
async def test_robots_allows_when_robots_file_is_missing():
    async with make_client(lambda request: httpx.Response(404)) as client:
        robots = Robots(client)

        assert await robots.allowed("https://example.com/book.pdf") is True


@pytest.mark.asyncio
async def test_robots_blocks_disallowed_path():
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private",
            )

        return httpx.Response(200)

    async with make_client(handler) as client:
        robots = Robots(client)

        assert await robots.allowed("https://example.com/private/book") is False


@pytest.mark.asyncio
async def test_robots_fails_closed_on_server_error():
    async with make_client(lambda request: httpx.Response(503)) as client:
        robots = Robots(client)

        assert await robots.allowed("https://example.com/book") is False


@pytest.mark.asyncio
async def test_successful_download_saves_file_and_hash(tmp_path):
    body = b"sample kural content"

    async with (
        make_client(
            robots_404_and_document(
                lambda request: httpx.Response(
                    200,
                    content=body,
                )
            )
        ) as client,
        Fetcher(
            output_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.jsonl",
            client=client,
        ) as fetcher,
    ):
        result = await fetcher.fetch_one(
            "https://example.com/book.txt",
            "sample",
        )

    assert result.status == "completed"
    assert Path(result.path).read_bytes() == body
    assert result.sha256 == hashlib.sha256(body).hexdigest()


@pytest.mark.asyncio
async def test_download_rejects_http_403(tmp_path):
    async with (
        make_client(robots_404_and_document(lambda request: httpx.Response(403))) as client,
        Fetcher(
            output_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.jsonl",
            client=client,
        ) as fetcher,
    ):
        result = await fetcher.fetch_one(
            "https://example.com/book.txt",
            "sample",
        )

    assert result.status == "failed"
    assert "403" in result.error


@pytest.mark.asyncio
async def test_download_rejects_http_404(tmp_path):
    async with (
        make_client(robots_404_and_document(lambda request: httpx.Response(404))) as client,
        Fetcher(
            output_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.jsonl",
            client=client,
        ) as fetcher,
    ):
        result = await fetcher.fetch_one(
            "https://example.com/missing.txt",
            "sample",
        )

    assert result.status == "failed"
    assert "404" in result.error


@pytest.mark.asyncio
async def test_download_rejects_large_content_length(tmp_path):
    async with (
        make_client(
            robots_404_and_document(
                lambda request: httpx.Response(
                    200,
                    headers={"Content-Length": str(MAX_BYTES + 1)},
                )
            )
        ) as client,
        Fetcher(
            output_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.jsonl",
            client=client,
        ) as fetcher,
    ):
        result = await fetcher.fetch_one(
            "https://example.com/large.pdf",
            "sample",
        )

    assert result.status == "too_large"


@pytest.mark.asyncio
async def test_blocked_url_is_not_downloaded(tmp_path):
    document_requested = False

    def handler(request):
        nonlocal document_requested

        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /",
            )

        document_requested = True

        return httpx.Response(200)

    async with (
        make_client(handler) as client,
        Fetcher(
            output_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.jsonl",
            client=client,
        ) as fetcher,
    ):
        result = await fetcher.fetch_one(
            "https://example.com/book.pdf",
            "sample",
        )

    assert result.status == "blocked"
    assert document_requested is False


@pytest.mark.asyncio
async def test_fetch_all_skips_completed_url(tmp_path):
    manifest_path = tmp_path / "manifest.jsonl"
    raw_dir = tmp_path / "raw"

    completed_file = raw_dir / "sample" / "book.pdf"
    completed_file.parent.mkdir(parents=True)
    completed_file.write_bytes(b"already downloaded")

    manifest_path.write_text(
        json.dumps(
            {
                "url": "https://example.com/book.pdf",
                "status": "completed",
                "path": "raw/sample/book.pdf",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    async with (
        make_client(lambda request: httpx.Response(500)) as client,
        Fetcher(
            output_dir=raw_dir,
            manifest_path=manifest_path,
            client=client,
        ) as fetcher,
    ):
        counts = await fetcher.fetch_all(
            [
                {
                    "url": "https://example.com/book.pdf",
                    "source": "sample",
                }
            ]
        )

    assert counts["skipped"] == 1
    assert counts["completed"] == 0


@pytest.mark.asyncio
async def test_host_gate_can_wait_without_error():
    gate = HostGate()

    await gate.wait("https://example.com/a", 0)
    await gate.wait("https://example.com/b", 0)


class InterruptedStream(httpx.AsyncByteStream):
    async def __aiter__(self):
        yield b"partial download"
        raise asyncio.CancelledError

    async def aclose(self):
        pass


@pytest.mark.asyncio
async def test_interrupted_download_removes_part_file(tmp_path):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        return httpx.Response(
            200,
            stream=InterruptedStream(),
        )

    async with (
        make_client(handler) as client,
        Fetcher(
            output_dir=tmp_path / "raw",
            manifest_path=tmp_path / "manifest.jsonl",
            client=client,
        ) as fetcher,
    ):
        with pytest.raises(asyncio.CancelledError):
            await fetcher.fetch_one(
                "https://example.com/book.txt",
                "sample",
            )

    part_files = list((tmp_path / "raw").rglob("*.part"))
    assert part_files == []


@pytest.mark.asyncio
async def test_deleted_file_is_downloaded_again(tmp_path):
    body = b"sample kural content"
    calls = 0

    def handler(request):
        nonlocal calls
        if request.url.path == "/robots.txt":
            return httpx.Response(404)

        calls += 1
        return httpx.Response(200, content=body)

    raw_dir = tmp_path / "raw"
    manifest_path = tmp_path / "manifest.jsonl"
    source = [{"url": "https://example.com/book.txt", "source": "sample"}]

    async with (
        make_client(robots_404_and_document(handler)) as client,
        Fetcher(
            output_dir=raw_dir,
            manifest_path=manifest_path,
            client=client,
        ) as fetcher,
    ):
        first = await fetcher.fetch_all(source)
        destination = fetcher.destination(source[0]["url"], source[0]["source"], "text/plain")
        destination.unlink()
        second = await fetcher.fetch_all(source)

    assert first["completed"] == 1
    assert second["completed"] == 1
    assert calls == 2
    assert destination.read_bytes() == body
