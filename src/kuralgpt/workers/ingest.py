"""ARQ worker for processing one document from download to metadata extraction."""

import asyncio
import hashlib
import logging
from pathlib import Path
from urllib.parse import urlparse

from kuralgpt.database import get_session_factory as get_sync_session_factory
from kuralgpt.ingest.parse import ParseError, parse_file
from kuralgpt.ingest.store import record_parse_failure, store_parsed_document
from kuralgpt.llm.extract import document_text, extract, get_document, save
from kuralgpt.llm.prompts import load_prompt
from kuralgpt.models import IngestItem

logger = logging.getLogger(__name__)

PROMPT_VERSION = 7


def plan(
    manifest,
    known_ids: set[str],
    *,
    source: str = "",
    limit: int = 20,
) -> list[dict]:
    """Select completed manifest records that still need ingestion."""
    if limit <= 0:
        return []

    selected = []
    source_filter = source.strip().casefold()

    for record in manifest.records():
        if record.get("type") == "repository":
            continue

        if record.get("status") != "completed":
            continue

        url = record.get("url")
        relative_path = record.get("path")

        if not url or not relative_path:
            continue

        if source_filter:
            from urllib.parse import urlparse

            hostname = urlparse(url).hostname or ""
            record_source = str(record.get("source", ""))
            searchable_source = f"{hostname} {record_source}".casefold()

            if source_filter not in searchable_source:
                continue

        local_path = _find_local_file(record, Path(manifest.path))

        if local_path is None:
            local_path = Path("data/raw") / Path(relative_path).name

        external_id = (
            "raw:" + hashlib.sha256(local_path.resolve().as_posix().encode("utf-8")).hexdigest()
        )

        if external_id in known_ids:
            continue

        selected.append(record)

        if len(selected) >= limit:
            break

    return selected


async def _update_item(
    session_factory,
    item_id: int,
    *,
    status: str,
    attempts: int,
    error: str = "",
    pages: int = 0,
) -> None:
    """Update the PostgreSQL ingestion item."""
    async with session_factory() as session:
        item = await session.get(IngestItem, item_id)

        if item is None:
            raise ValueError(f"Ingestion item {item_id} was not found.")

        item.status = status
        item.attempts = attempts
        item.error = error
        item.pages = pages
        await session.commit()


def _find_local_file(record: dict, manifest_path: Path) -> Path | None:
    """Find a downloaded file using its manifest path or filename."""
    relative_path = record.get("path")

    if not relative_path:
        return None

    candidates = [
        manifest_path.parent / relative_path,
        Path("data/raw") / Path(relative_path).name,
    ]

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    return None


def _store_document(path: Path, parsed, source_url: str | None) -> int:
    """Store a parsed document using the synchronous database session."""
    session_factory = get_sync_session_factory()

    with session_factory() as session:
        document = store_parsed_document(
            session,
            path,
            parsed,
            source_url=source_url,
        )
        document_id = document.id
        session.commit()

    return document_id


def _record_failure(
    path: Path,
    error: ParseError,
    source_url: str | None,
) -> None:
    """Persist a parsing failure."""
    session_factory = get_sync_session_factory()

    with session_factory() as session:
        record_parse_failure(
            session,
            path,
            error,
            source_url=source_url,
        )
        session.commit()


async def _wait_for_llm_slot(ctx: dict) -> None:
    """Apply the configured minimum delay between LLM calls."""
    rpm = max(float(ctx["settings"].ingest_rpm), 0.1)
    interval = 60.0 / rpm
    lock = ctx["pace_lock"]

    async with lock:
        loop = asyncio.get_running_loop()
        now = loop.time()
        wait = interval - (now - ctx["last_llm_call"])

        if wait > 0:
            await asyncio.sleep(wait)

        ctx["last_llm_call"] = loop.time()


async def ingest_document(ctx: dict, item_id: int) -> dict:
    """Fetch, parse, store, and extract metadata for one queued item."""
    settings = ctx["settings"]
    session_factory = ctx["async_session_factory"]
    attempts = int(ctx.get("job_try", 1))
    pages_count = 0

    semaphore = ctx["ingest_semaphore"]

    async with semaphore:
        try:
            async with session_factory() as session:
                item = await session.get(IngestItem, item_id)

                if item is None:
                    raise ValueError(f"Ingestion item {item_id} was not found.")

                record = dict(item.record)

            await _update_item(
                session_factory,
                item_id,
                status="processing",
                attempts=attempts,
            )

            source_url = record.get("url")
            manifest_path = Path(settings.manifest_file)
            path = _find_local_file(record, manifest_path)

            if path is None:
                if not source_url:
                    raise ValueError("Manifest item has no URL or local file.")

                fetcher = ctx["fetcher"]
                source = urlparse(source_url).hostname or "unknown"

                result = await fetcher.fetch_one(source_url, source)

                if result.status != "completed" or result.path is None:
                    raise RuntimeError(result.error or f"Download failed: {result.status}")

                fetcher.manifest.append(result, fetcher.root)
                path = Path(result.path)

                if not path.is_file():
                    path = _find_local_file(
                        {**record, "path": str(result.path)},
                        manifest_path,
                    )

                if path is None or not path.is_file():
                    raise FileNotFoundError(f"Downloaded file could not be located: {result.path}")

            try:
                parsed = await asyncio.to_thread(parse_file, path)
            except ParseError as error:
                await asyncio.to_thread(
                    _record_failure,
                    path,
                    error,
                    source_url,
                )
                raise

            pages_count = len(parsed.pages)

            document_id = await asyncio.to_thread(
                _store_document,
                path,
                parsed,
                source_url,
            )

            document = await asyncio.to_thread(get_document, document_id)

            if document is None:
                raise ValueError(f"Stored document {document_id} could not be loaded.")

            text = await asyncio.to_thread(document_text, document)

            if not text.strip():
                raise ValueError("Document contains no extractable text.")

            prompt = load_prompt("extract", PROMPT_VERSION)

            await _wait_for_llm_slot(ctx)

            extraction = await extract(
                gateway=ctx["gateway"],
                prompt=prompt,
                version=str(PROMPT_VERSION),
                document_text=text,
                document_title=parsed.title,
            )

            if extraction.metadata is None:
                raise ValueError(extraction.error or "Metadata extraction returned no metadata.")

            await asyncio.to_thread(
                save,
                document_id,
                extraction,
                str(PROMPT_VERSION),
            )

            await _update_item(
                session_factory,
                item_id,
                status="completed",
                attempts=attempts,
                pages=pages_count,
            )

            logger.info(
                "Ingestion item %s completed; document ID %s",
                item_id,
                document_id,
            )

            return {
                "item_id": item_id,
                "document_id": document_id,
                "status": "completed",
                "pages": pages_count,
            }

        except asyncio.CancelledError:
            logger.warning(
                "Ingestion item %s was cancelled or timed out",
                item_id,
            )
            try:
                await _update_item(
                    session_factory,
                    item_id,
                    status="failed",
                    attempts=attempts,
                    error="Worker job was cancelled or exceeded its timeout.",
                    pages=pages_count,
                )
            except Exception:
                logger.exception(
                    "Could not update cancelled status for item %s",
                    item_id,
                )
            raise

        except Exception as error:
            logger.exception("Ingestion item %s failed", item_id)

            try:
                await _update_item(
                    session_factory,
                    item_id,
                    status="failed",
                    attempts=attempts,
                    error=str(error)[:2000],
                    pages=pages_count,
                )
            except Exception:
                logger.exception(
                    "Could not update failed status for item %s",
                    item_id,
                )

            raise
