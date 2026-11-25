"""Compare document extraction methods and append results to NOTES.md."""

from __future__ import annotations

import argparse
import re
import time
from html.parser import HTMLParser
from pathlib import Path

import pymupdf
import trafilatura
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "NOTES.md"

START_MARKER = "<!-- parser-comparison-start -->"
END_MARKER = "<!-- parser-comparison-end -->"


class PlainHTMLParser(HTMLParser):
    """Strip HTML tags while preserving basic document structure."""

    BLOCK_TAGS = {
        "p",
        "div",
        "section",
        "article",
        "header",
        "footer",
        "li",
        "ul",
        "ol",
        "br",
        "tr",
    }

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
            return

        if self.skip_depth:
            return

        if tag in self.BLOCK_TAGS:
            self.parts.append("\n")

        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("#" * int(tag[1]) + " ")

        if tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_endtag(self, tag):
        if tag in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
            return

        if self.skip_depth:
            return

        if tag in self.BLOCK_TAGS or tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.parts.append("\n")

        if tag in {"td", "th"}:
            self.parts.append(" | ")

    def handle_data(self, data):
        if not self.skip_depth:
            self.parts.append(data)

    def get_text(self):
        return "\n".join(line.strip() for line in "".join(self.parts).splitlines() if line.strip())


def read_html(path: Path) -> str:
    raw = path.read_bytes()

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw.decode("utf-16")

    return raw.decode("utf-8-sig")


def extract_html(path: Path, method: str) -> str:
    source = read_html(path)

    if method == "trafilatura":
        return (
            trafilatura.extract(
                source,
                output_format="markdown",
                include_tables=True,
                include_links=True,
            )
            or ""
        )

    parser = PlainHTMLParser()
    parser.feed(source)
    return parser.get_text()


def extract_pdf(path: Path, method: str) -> str:
    if method == "pymupdf":
        with pymupdf.open(path) as document:
            return "\n\n".join(page.get_text("text") for page in document)

    reader = PdfReader(str(path))

    if reader.is_encrypted:
        raise ValueError("Encrypted PDF")

    return "\n\n".join(page.extract_text() or "" for page in reader.pages)


def extract_file(path: Path, method: str) -> str:
    suffix = path.suffix.lower()

    if suffix in {".html", ".htm"}:
        return extract_html(path, method)

    if suffix == ".pdf":
        return extract_pdf(path, method)

    return path.read_text(encoding="utf-8-sig")


def metrics(text: str) -> tuple[int, int, int]:
    characters = len(text)
    headings = len(re.findall(r"(?m)^#{1,6}\s+", text))
    tables = sum(1 for line in text.splitlines() if line.count("|") >= 2)
    return characters, headings, tables


def compare(path: Path) -> dict:
    suffix = path.suffix.lower()

    if suffix in {".html", ".htm"}:
        methods = ("trafilatura", "plain tags")
        method_names = ("trafilatura", "plain")
    elif suffix == ".pdf":
        methods = ("PyMuPDF", "pypdf")
        method_names = ("pymupdf", "pypdf")
    else:
        methods = ("available parser", "not applicable")
        method_names = ("single", None)

    results = []

    for method in method_names:
        if method is None:
            results.append(None)
            continue

        started = time.perf_counter()

        try:
            text = extract_file(path, method)
            elapsed = time.perf_counter() - started
            chars, headings, tables = metrics(text)

            results.append(
                {
                    "chars": chars,
                    "headings": headings,
                    "tables": tables,
                    "seconds": elapsed,
                    "error": "",
                }
            )

        except Exception as exc:
            results.append(
                {
                    "chars": 0,
                    "headings": 0,
                    "tables": 0,
                    "seconds": 0,
                    "error": str(exc).replace("|", "/"),
                }
            )

    return {
        "file": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else path.name,
        "parser_a": methods[0],
        "parser_b": methods[1],
        "a": results[0],
        "b": results[1],
    }


def make_table(results: list[dict]) -> str:
    lines = [
        "| File | Parser A | A chars | A headings | A tables | A sec | "
        "Parser B | B chars | B headings | B tables | B sec | Better parser + why |",
        "|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---|",
    ]

    for result in results:
        a = result["a"]
        b = result["b"]

        def value(item, key):
            if item is None:
                return "—"
            if item["error"]:
                return "ERROR"
            if key == "seconds":
                return f"{item[key]:.3f}"
            return str(item[key])

        lines.append(
            f"| {result['file']} "
            f"| {result['parser_a']} "
            f"| {value(a, 'chars')} "
            f"| {value(a, 'headings')} "
            f"| {value(a, 'tables')} "
            f"| {value(a, 'seconds')} "
            f"| {result['parser_b']} "
            f"| {value(b, 'chars')} "
            f"| {value(b, 'headings')} "
            f"| {value(b, 'tables')} "
            f"| {value(b, 'seconds')} "
            f"|  |"
        )

        for label, item in (("A", a), ("B", b)):
            if item and item["error"]:
                lines.append(f"<!-- {result['file']}: Parser {label} error: {item['error']} -->")

    return "\n".join(lines)


def write_notes(table: str):
    existing = NOTES.read_text(encoding="utf-8")

    section = f"{START_MARKER}\n## Step 5 – Parser comparison\n\n{table}\n{END_MARKER}"

    if START_MARKER in existing and END_MARKER in existing:
        before = existing.split(START_MARKER)[0]
        after = existing.split(END_MARKER, 1)[1]
        updated = before.rstrip() + "\n\n" + section + after
    else:
        updated = existing.rstrip() + "\n\n" + section + "\n"

    NOTES.write_text(updated, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compare PDF and HTML extraction methods.")
    parser.add_argument("files", nargs="*", help="Files to compare")
    args = parser.parse_args()

    if args.files:
        paths = [Path(item).resolve() for item in args.files]
    else:
        candidates = [
            path
            for path in (ROOT / "data/raw").rglob("*")
            if path.is_file() and path.suffix.lower() in {".pdf", ".html", ".htm"}
        ]
        paths = sorted(
            candidates,
            key=lambda path: path.stat().st_size,
            reverse=True,
        )[:10]

    if not paths:
        raise SystemExit("No supported PDF or HTML files found.")

    results = []

    for path in paths:
        if not path.is_file():
            print(f"Skipping missing file: {path}")
            continue

        print(f"Comparing: {path.name}")
        results.append(compare(path))

    if not results:
        raise SystemExit("No files could be compared.")

    table = make_table(results)
    write_notes(table)

    print(f"\ncompared {len(results)} files -> table written to NOTES.md")


if __name__ == "__main__":
    main()
