"""Command-line tools for KuralGPT data ingestion."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

import httpx

from kuralgpt.ingest.fetch import Fetcher, FetchResult, Manifest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MANIFEST_FILE = DATA_DIR / "manifest.jsonl"
SOURCES_FILE = DATA_DIR / "sources.csv"

REQUIRED_COLUMNS = ["url", "source", "licence", "title"]


def load_sources(path: Path = SOURCES_FILE) -> list[dict[str, str]]:
    """Read and validate the source CSV."""
    if not path.exists():
        raise FileNotFoundError(f"Source file not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)

        if not reader.fieldnames or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
            raise ValueError("sources.csv must contain: url, source, licence, title")

        sources = []
        seen = set()

        for row in reader:
            url = (row.get("url") or "").strip()
            source = (row.get("source") or "").strip()
            licence = (row.get("licence") or "").strip()

            if not url or not source or not licence:
                raise ValueError("Every source row needs URL, source and licence")

            if urlparse(url).scheme not in {"http", "https"}:
                raise ValueError(f"Invalid URL: {url}")

            if url not in seen:
                sources.append({"url": url, "source": source})
                seen.add(url)

    return sources


def save_sources(new_rows: list[dict[str, str]]) -> int:
    """Add new sitemap URLs to sources.csv without duplicates."""
    existing = []
    existing_urls = set()

    if SOURCES_FILE.exists():
        with SOURCES_FILE.open("r", encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            existing = list(reader)
            existing_urls = {row.get("url", "").strip() for row in existing}

    added = 0

    for row in new_rows:
        if row["url"] not in existing_urls:
            existing.append(row)
            existing_urls.add(row["url"])
            added += 1

    with SOURCES_FILE.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(existing)

    return added


async def run_urls(
    delay: float,
    concurrency: int,
    sources_file: Path = SOURCES_FILE,
    output_dir: Path = RAW_DIR,
    manifest_file: Path = MANIFEST_FILE,
) -> None:
    """Download permitted URLs from the selected sources CSV."""
    sources = load_sources(sources_file)

    async with Fetcher(
        output_dir=output_dir,
        manifest_path=manifest_file,
        max_concurrent=concurrency,
        per_host_delay=delay,
    ) as fetcher:
        counts = await fetcher.fetch_all(sources)

    print("\nDownload summary")

    for status, count in counts.items():
        print(f"{status}: {count}")


async def run_repo(
    repository: str,
    paths: list[str],
    extensions: list[str],
    ref: str,
) -> None:
    """Download selected files from a GitHub repository at a fixed commit."""
    if "/" not in repository:
        raise ValueError("Repository must use owner/repository format")

    owner, repo = repository.split("/", 1)

    api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/{ref}?recursive=1"

    async with Fetcher(
        output_dir=RAW_DIR,
        manifest_path=MANIFEST_FILE,
    ) as fetcher:
        tree_result = await fetcher.fetch_one(
            api_url,
            f"github-{owner}-{repo}-tree",
        )

        if tree_result.status != "completed" or not tree_result.path:
            raise RuntimeError(f"Could not retrieve GitHub tree: {tree_result.error}")

        tree_file = Path(tree_result.path)
        tree_data = json.loads(tree_file.read_text(encoding="utf-8"))
        commit_sha = tree_data.get("sha")

        if not commit_sha:
            raise RuntimeError("GitHub did not return a commit SHA")

        if tree_data.get("truncated"):
            raise RuntimeError(
                "GitHub returned a truncated repository tree. Use a smaller --path filter."
            )

        files = []

        for item in tree_data.get("tree", []):
            if item.get("type") != "blob":
                continue

            file_path = item.get("path", "")

            if paths and not any(
                selected in {".", ""}
                or file_path == selected.strip("/")
                or file_path.startswith(selected.strip("/") + "/")
                for selected in paths
            ):
                continue

            if extensions and not any(file_path.endswith(ext) for ext in extensions):
                continue

            files.append(file_path)

        # Save repository name and exact commit SHA in the manifest.
        fetcher.manifest.append_repository(repository, commit_sha)

        print(f"Repository commit: {commit_sha}")
        print(f"Matching files: {len(files)}")

        sources = [
            {
                "url": (
                    f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{file_path}"
                ),
                "source": f"github-{owner}-{repo}",
            }
            for file_path in files
        ]

        counts = await fetcher.fetch_all(sources)

    print("\nRepository download summary")

    for status, count in counts.items():
        print(f"{status}: {count}")

    print(f"added={counts['completed']} unchanged={counts['skipped']}")


async def run_sitemap(
    sitemap_url: str,
    includes: list[str],
    excludes: list[str],
) -> None:
    """Read a sitemap and register matching URLs in sources.csv."""
    async with Fetcher(
        output_dir=RAW_DIR,
        manifest_path=MANIFEST_FILE,
    ) as fetcher:
        result = await fetcher.fetch_one(
            sitemap_url,
            "sitemap",
        )

    if result.status != "completed" or not result.path:
        raise RuntimeError(f"Sitemap fetch failed: {result.error}")

    root = ET.parse(result.path).getroot()
    rows = []

    for element in root.iter():
        if element.tag.endswith("loc") and element.text:
            url = element.text.strip()
            path = urlparse(url).path

            if includes and not any(part in path for part in includes):
                continue

            if any(part in path for part in excludes):
                continue

            rows.append(
                {
                    "url": url,
                    "source": urlparse(url).netloc,
                    "licence": "Review required",
                    "title": path.rsplit("/", 1)[-1] or url,
                }
            )

    added = save_sources(rows)

    print(f"Sitemap URLs found: {len(rows)}")
    print(f"New URLs added to sources.csv: {added}")
    print("Review source terms and licences before downloading.")


def run_manual(folder: Path, source_url: str) -> None:
    """Register manually saved files in the manifest."""
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Folder not found: {folder}")

    if urlparse(source_url).scheme not in {"http", "https"}:
        raise ValueError("from-url must be an HTTP or HTTPS URL")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(MANIFEST_FILE)
    root = DATA_DIR
    source_name = urlparse(source_url).netloc
    added = 0

    existing_records = manifest.records()

    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue

        digest = hashlib.sha256()
        size = 0

        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                digest.update(chunk)
                size += len(chunk)

        relative_path = path.relative_to(root).as_posix()

        already_registered = any(
            record.get("path") == relative_path and record.get("status") == "completed"
            for record in existing_records
        )

        if already_registered:
            continue

        result = FetchResult(
            url=source_url,
            status="completed",
            path=str(path),
            sha256=digest.hexdigest(),
            size=size,
            error=f"Manually registered from {source_name}",
        )

        manifest.append(result, root)
        existing_records.append(
            {
                "path": relative_path,
                "status": "completed",
            }
        )
        added += 1

    print(f"New files registered: {added}")


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="KuralGPT polite and resumable data downloader")

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    urls_parser = subparsers.add_parser(
        "urls",
        help="Download permitted URLs from data/sources.csv",
    )
    urls_parser.add_argument("--delay", type=float, default=0.5)
    urls_parser.add_argument("--max-concurrency", type=int, default=4)
    urls_parser.add_argument("--sources", type=Path, default=SOURCES_FILE)
    urls_parser.add_argument("--output-dir", type=Path, default=RAW_DIR)
    urls_parser.add_argument("--manifest", type=Path, default=MANIFEST_FILE)

    repo_parser = subparsers.add_parser(
        "repo",
        help="Download selected files from a GitHub repository",
    )
    repo_parser.add_argument("repository")
    repo_parser.add_argument("--path", action="append", default=[])
    repo_parser.add_argument("--ext", action="append", default=[])
    repo_parser.add_argument("--ref", default="master")

    sitemap_parser = subparsers.add_parser(
        "sitemap",
        help="Add matching sitemap URLs to sources.csv",
    )
    sitemap_parser.add_argument("url")
    sitemap_parser.add_argument("--include", action="append", default=[])
    sitemap_parser.add_argument("--exclude", action="append", default=[])

    manual_parser = subparsers.add_parser(
        "manual",
        help="Register manually downloaded files",
    )
    manual_parser.add_argument("folder", type=Path)
    manual_parser.add_argument("--from-url", required=True)

    return parser


def main() -> None:
    """Run the selected downloader command."""
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "urls":
            if args.delay < 0:
                parser.error("--delay cannot be negative")

            if not 1 <= args.max_concurrency <= 4:
                parser.error("--max-concurrency must be between 1 and 4")

            asyncio.run(
                run_urls(
                    args.delay,
                    args.max_concurrency,
                    args.sources,
                    args.output_dir,
                    args.manifest,
                )
            )

        elif args.command == "repo":
            asyncio.run(
                run_repo(
                    args.repository,
                    args.path,
                    args.ext,
                    args.ref,
                )
            )

        elif args.command == "sitemap":
            asyncio.run(
                run_sitemap(
                    args.url,
                    args.include,
                    args.exclude,
                )
            )

        elif args.command == "manual":
            run_manual(
                args.folder,
                args.from_url,
            )

    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
