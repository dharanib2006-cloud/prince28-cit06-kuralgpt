"""Measure the KuralGPT dataset and generate capacity documentation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
DATASET_FILE = ROOT / "DATASET.md"
CAPACITY_FILE = ROOT / "docs" / "CAPACITY.md"

START = "<!-- generated:start -->"
END = "<!-- generated:end -->"

DEFAULT_EMBED_USD = 0.20
DEFAULT_DIMS = 1024
DEFAULT_CHUNK_TOKENS = 500
DEFAULT_USD_INR = 95


def measure_files() -> tuple[list[dict], int, int, int]:
    """Measure downloaded files and count PDF pages."""
    files = []
    total_bytes = 0
    pdf_pages = 0
    pdf_count = 0

    if not RAW_DIR.exists():
        return files, total_bytes, pdf_pages, pdf_count

    for path in sorted(RAW_DIR.rglob("*")):
        if not path.is_file() or path.name.endswith(".part"):
            continue

        size = path.stat().st_size
        total_bytes += size
        pages = 0
        note = ""

        if path.suffix.lower() == ".pdf":
            pdf_count += 1

            try:
                pages = len(PdfReader(str(path)).pages)
                pdf_pages += pages
            except Exception as exc:
                note = f"PDF page count failed: {exc}"

        files.append(
            {
                "name": path.relative_to(ROOT).as_posix(),
                "bytes": size,
                "pages": pages,
                "note": note,
            }
        )

    return files, total_bytes, pdf_pages, pdf_count


def count_kurals() -> int:
    """Count Kural records in the main Thirukkural JSON file."""
    candidates = [
        path
        for path in RAW_DIR.rglob("*.json")
        if "thirukkural" in path.name.lower()
        and "detail" not in path.name.lower()
        and "tree" not in path.name.lower()
    ]

    for path in candidates:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        records = data.get("kural") if isinstance(data, dict) else data

        if isinstance(records, list):
            return len(records)

    return 0


def replace_generated_section(path: Path, content: str) -> None:
    """Replace only the content between generated markers."""
    path.parent.mkdir(parents=True, exist_ok=True)

    existing = path.read_text(encoding="utf-8") if path.exists() else ""

    if START in existing and END in existing:
        before, remainder = existing.split(START, 1)
        _, after = remainder.split(END, 1)
        updated = f"{before}{START}\n{content}\n{END}{after}"
    else:
        updated = f"{existing.rstrip()}\n\n{START}\n{content}\n{END}\n"

    path.write_text(updated, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure KuralGPT dataset size and estimate capacity."
    )

    parser.add_argument("--full-pages", type=int, default=3000)
    parser.add_argument("--embed-usd", type=float, default=DEFAULT_EMBED_USD)
    parser.add_argument("--dims", type=int, default=DEFAULT_DIMS)
    parser.add_argument("--chunk-tokens", type=int, default=DEFAULT_CHUNK_TOKENS)
    parser.add_argument("--usd-inr", type=float, default=DEFAULT_USD_INR)

    args = parser.parse_args()

    if args.full_pages < 0 or args.embed_usd < 0:
        parser.error("Page count and embedding price cannot be negative.")

    if args.dims <= 0 or args.chunk_tokens <= 0 or args.usd_inr <= 0:
        parser.error("Dimensions, chunk tokens and exchange rate must be positive.")

    files, total_bytes, pdf_pages, pdf_count = measure_files()
    kural_count = count_kurals()

    total_mb = total_bytes / (1024 * 1024)
    total_gb = total_bytes / (1024**3)

    # Rough planning estimate: 100 tokens per Kural and 500 per PDF page.
    estimated_tokens = max(kural_count * 100, pdf_pages * 500)

    chunks = (estimated_tokens + args.chunk_tokens - 1) // args.chunk_tokens

    # float32 vector storage: 4 bytes per dimension.
    # Database indexes and overhead are excluded.
    vector_bytes = chunks * args.dims * 4
    vector_mb = vector_bytes / (1024 * 1024)

    estimated_cost_inr = args.embed_usd * args.usd_inr

    file_lines = [
        "| File | Size (bytes) | PDF pages | Notes |",
        "|---|---:|---:|---|",
    ]

    for item in files:
        file_lines.append(
            f"| `{item['name']}` | {item['bytes']:,} | {item['pages']:,} | {item['note'] or '-'} |"
        )

    file_lines.append(f"| **Total** | **{total_bytes:,}** | **{pdf_pages:,}** | - |")

    dataset_report = "\n".join(
        [
            "### Generated measurements",
            "",
            f"- Kural records detected: **{kural_count:,}**",
            f"- Files measured: **{len(files):,}**",
            f"- Total downloaded size: **{total_mb:.2f} MB** ({total_gb:.4f} GB)",
            f"- PDF files: **{pdf_count:,}**",
            f"- PDF pages counted: **{pdf_pages:,}**",
            "",
            *file_lines,
        ]
    )

    replace_generated_section(DATASET_FILE, dataset_report)

    capacity_report = "\n".join(
        [
            "### Generated measurements",
            "",
            f"- Current downloaded files: **{total_mb:.2f} MB**",
            f"- Current Kural records: **{kural_count:,}**",
            f"- Current PDF pages: **{pdf_pages:,}**",
            f"- Full corpus planning target: **{args.full_pages:,} PDF pages**",
            f"- Estimated text tokens (planning assumption): **{estimated_tokens:,}**",
            f"- Estimated chunks at {args.chunk_tokens:,} tokens each: **{chunks:,}**",
            f"- Vector dimensions: **{args.dims:,}**",
            f"- Estimated raw vector storage (float32): **{vector_mb:.2f} MB**",
            f"- Example embedding budget: **${args.embed_usd:.2f} "
            f"(INR {estimated_cost_inr:,.2f})**",
            "",
            "### What I conclude",
            "",
            "1. **Is embedding cost a problem?** The example budget is "
            f"${args.embed_usd:.2f} (approximately INR "
            f"{estimated_cost_inr:,.2f}); confirm the actual provider "
            "price and token count before deployment.",
            "",
            "2. **Do vectors and text fit in free Postgres?** Compare the "
            f"estimated {vector_mb:.2f} MB of raw vectors plus "
            f"{total_mb:.2f} MB of source files with the storage limit "
            "shown in your actual database dashboard. Database indexes "
            "and row overhead are not included.",
            "",
            "3. **Which number is least certain?** The token and chunk "
            "estimate is rough; measure actual extracted text tokens "
            "and chunk counts from the final corpus.",
            "",
            "4. **What changes if the corpus grows 10 times?** Text, "
            "vectors and index storage will grow substantially. "
            "Re-measure actual usage, embedding cost and database "
            "limits before scaling.",
        ]
    )

    replace_generated_section(CAPACITY_FILE, capacity_report)

    print(
        f"kurals={kural_count} files={len(files)} pages={pdf_pages} "
        "-> wrote DATASET.md and docs/CAPACITY.md"
    )


if __name__ == "__main__":
    main()
