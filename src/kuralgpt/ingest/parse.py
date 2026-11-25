"""Document parsers for KuralGPT."""

from __future__ import annotations

import csv
import html
import json
import os
import re
import statistics
import unicodedata
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf
import trafilatura
import yaml
from pypdf import PdfReader

PAGE_SIZE = 3000


@dataclass
class ParsedPage:
    """One extracted page of document text."""

    page_no: int
    text: str
    headings: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)


@dataclass
class ParsedDoc:
    """Complete parsed document."""

    parser: str
    kind: str
    title: str
    pages: list[ParsedPage]


class ParseError(Exception):
    """Raised when a document cannot be parsed."""

    def __init__(self, reason: str, detail: str = ""):
        self.reason = reason
        self.detail = detail
        super().__init__(f"{reason}: {detail}" if detail else reason)


def clean_text(text: str) -> str:
    """Normalize text without damaging Tamil or other Unicode scripts."""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\x00", "").replace("\u00ad", "")
    text = re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_headings(text: str) -> list[str]:
    """Extract Markdown headings, ignoring fenced code blocks."""
    headings = []
    in_code = False
    fence = None

    for line in text.splitlines():
        stripped = line.strip()

        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if not in_code:
                in_code = True
                fence = marker
            elif marker == fence:
                in_code = False
                fence = None
            continue

        if in_code:
            continue

        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
        if match:
            headings.append(match.group(2).strip())

    return headings


def _split_text(text: str) -> list[str]:
    """Split text into pages without splitting at arbitrary word boundaries."""
    if not text:
        return []

    paragraphs = re.split(r"\n\s*\n", text)
    pages: list[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue

        while len(paragraph) > PAGE_SIZE:
            if current:
                pages.append(current)
                current = ""

            cut = paragraph.rfind(" ", 0, PAGE_SIZE)
            if cut <= 0:
                cut = PAGE_SIZE

            pages.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()

        candidate = f"{current}\n\n{paragraph}".strip()

        if len(candidate) > PAGE_SIZE and current:
            pages.append(current)
            current = paragraph
        else:
            current = candidate

    if current:
        pages.append(current)

    return pages


def _heading_events(text: str) -> list[tuple[int, str]]:
    """Find Markdown heading paths and their character positions."""
    events = []
    stack: list[tuple[int, str]] = []
    in_code = False
    fence = None
    offset = 0

    for line in text.splitlines(keepends=True):
        stripped = line.strip()

        if stripped.startswith(("```", "~~~")):
            marker = stripped[:3]
            if not in_code:
                in_code = True
                fence = marker
            elif marker == fence:
                in_code = False
                fence = None
            offset += len(line)
            continue

        if not in_code:
            match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", stripped)
            if match:
                level = len(match.group(1))
                title = match.group(2).strip()

                while stack and stack[-1][0] >= level:
                    stack.pop()

                stack.append((level, title))
                path = " > ".join(item[1] for item in stack)
                events.append((offset, path))

        offset += len(line)

    return events


def _make_pages(text: str) -> list[ParsedPage]:
    """Create numbered pages and retain the active heading path."""
    chunks = _split_text(text)
    events = _heading_events(text)

    pages = []
    search_from = 0

    for page_no, chunk in enumerate(chunks, start=1):
        position = text.find(chunk, search_from)

        if position < 0:
            position = search_from

        end_position = position + len(chunk)
        active = [path for event_position, path in events if event_position <= end_position]

        pages.append(
            ParsedPage(
                page_no=page_no,
                text=chunk,
                headings=list(dict.fromkeys(active)),
            )
        )

        search_from = end_position

    return pages


def _title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip()


def _remove_repeated_headers_footers(
    page_lines: list[list[str]],
) -> list[list[str]]:
    """Remove lines repeated at the top or bottom of most PDF pages."""
    if len(page_lines) < 2:
        return page_lines

    top_counts = Counter(lines[0].strip() for lines in page_lines if lines and lines[0].strip())
    bottom_counts = Counter(
        lines[-1].strip() for lines in page_lines if lines and lines[-1].strip()
    )

    threshold = max(2, len(page_lines) // 2 + 1)
    repeated_top = {line for line, count in top_counts.items() if count >= threshold}
    repeated_bottom = {line for line, count in bottom_counts.items() if count >= threshold}

    cleaned = []

    for lines in page_lines:
        current = list(lines)

        if current and current[0].strip() in repeated_top:
            current.pop(0)

        if current and current[-1].strip() in repeated_bottom:
            current.pop()

        cleaned.append(current)

    return cleaned


def _extract_pdf_table(page) -> list[str]:
    """Extract tables from a PDF page when PyMuPDF detects them."""
    tables = []

    try:
        finder = page.find_tables()
        for table in finder.tables:
            rows = table.extract()
            formatted = [" | ".join(str(cell or "").strip() for cell in row) for row in rows]
            if formatted:
                tables.append("\n".join(formatted))
    except Exception:
        # Table detection is optional; preserve the page text.
        pass

    return tables


def _extract_pdf_page(page, page_number: int) -> ParsedPage:
    """Extract text, font-size headings, and tables from one PDF page."""
    text = page.get_text("text") or ""
    headings = []

    try:
        blocks = page.get_text("dict")["blocks"]
        spans = [
            span
            for block in blocks
            if "lines" in block
            for line in block["lines"]
            for span in line["spans"]
            if span["text"].strip()
        ]

        sizes = [span["size"] for span in spans]
        body_size = statistics.median(sizes) if sizes else 0

        for span in spans:
            span_text = clean_text(span["text"])
            if span_text and body_size and span["size"] >= body_size * 1.25:
                headings.append(span_text)

    except (KeyError, TypeError, ValueError):
        pass

    return ParsedPage(
        page_no=page_number,
        text=clean_text(text),
        headings=list(dict.fromkeys(headings)),
        tables=_extract_pdf_table(page),
    )


def _parse_pdf_pages(path: Path) -> tuple[list[ParsedPage], str]:
    """Extract PDF pages with PyMuPDF, using OCR when needed."""
    try:
        document = pymupdf.open(path)
    except Exception as exc:
        raise ParseError("corrupt", str(exc)) from exc

    with document:
        if document.is_encrypted:
            raise ParseError("encrypted", "PDF is password protected")

        pages = [_extract_pdf_page(page, index) for index, page in enumerate(document, start=1)]

        if not any(page.text for page in pages):
            try:
                language = os.getenv("KURALGPT_OCR_LANG", "eng")

                pages = [
                    ParsedPage(
                        page_no=index,
                        text=clean_text(
                            page.get_textpage_ocr(
                                language=language,
                                dpi=200,
                            ).extractText()
                        ),
                        headings=[],
                        tables=[],
                    )
                    for index, page in enumerate(document, start=1)
                ]
            except Exception as exc:
                raise ParseError(
                    "no_text_layer",
                    "PDF has no text layer and OCR is unavailable. "
                    "Install Tesseract and its language data. "
                    f"Details: {exc}",
                ) from exc

    if not any(page.text for page in pages):
        raise ParseError("no_text_layer", "No text extracted from PDF")

    page_lines = [page.text.splitlines() for page in pages]
    cleaned_lines = _remove_repeated_headers_footers(page_lines)

    for page, lines in zip(pages, cleaned_lines, strict=True):
        page.text = clean_text("\n".join(lines))

    return pages, "pymupdf"


def _parse_pdf(path: Path, pdf_parser: str) -> tuple[str, str]:
    """Extract PDF text using PyMuPDF or pypdf."""
    if pdf_parser == "pymupdf":
        pages, parser = _parse_pdf_pages(path)
        return "\n\n".join(page.text for page in pages), parser

    if pdf_parser == "pypdf":
        try:
            reader = PdfReader(str(path))

            if reader.is_encrypted:
                raise ParseError("encrypted", "PDF is password protected")

            text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError("corrupt", str(exc)) from exc

        if not text.strip():
            raise ParseError("no_text_layer", "PDF contains no extractable text")

        return text, "pypdf"

    raise ParseError("unsupported_parser", pdf_parser)


def _parse_html(path: Path) -> tuple[str, str]:
    """Extract readable HTML content with BOM-aware Unicode decoding."""
    try:
        raw = path.read_bytes()

        if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
            source = raw.decode("utf-16")
        else:
            source = raw.decode("utf-8-sig")

    except UnicodeDecodeError as exc:
        raise ParseError("corrupt", str(exc)) from exc

    extracted = trafilatura.extract(
        source,
        output_format="markdown",
        include_tables=True,
        include_links=True,
    )

    if not extracted:
        raise ParseError("empty", "No readable HTML content found")

    return html.unescape(extracted), "trafilatura"


def _parse_json(path: Path) -> tuple[str, str]:
    """Format JSON as readable text while preserving Unicode."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ParseError("corrupt", str(exc)) from exc

    return json.dumps(data, ensure_ascii=False, indent=2), "json"


def _parse_yaml(path: Path) -> tuple[str, str]:
    """Parse YAML safely and preserve Unicode."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ParseError("corrupt", str(exc)) from exc

    return (
        yaml.safe_dump(
            data,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
        ),
        "pyyaml",
    )


def _parse_markdown(path: Path) -> tuple[str, str]:
    return path.read_text(encoding="utf-8-sig"), "markdown"


def _parse_text(path: Path) -> tuple[str, str]:
    return path.read_text(encoding="utf-8-sig"), "text"


def _parse_csv(path: Path) -> tuple[str, str]:
    with path.open("r", encoding="utf-8-sig", newline="") as file:
        rows = list(csv.reader(file))

    return "\n".join(" | ".join(row) for row in rows), "csv"


def _parse_xml(path: Path) -> tuple[str, str]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ParseError("corrupt", str(exc)) from exc

    lines = []

    for element in root.iter():
        value = (element.text or "").strip()
        if value:
            lines.append(f"{element.tag}: {value}")

    return "\n".join(lines), "xml"


def parse_file(path: Path, pdf_parser: str = "pymupdf") -> ParsedDoc:
    """Parse a supported file into normalized, numbered pages."""
    path = Path(path)

    if not path.is_file():
        raise ParseError("missing", str(path))

    suffix = path.suffix.lower()
    pdf_pages = None

    try:
        if suffix == ".pdf":
            if pdf_parser == "pymupdf":
                pdf_pages, parser = _parse_pdf_pages(path)
                kind = "pdf"
                text = "\n\n".join(page.text for page in pdf_pages)
            else:
                text, parser = _parse_pdf(path, pdf_parser)
                kind = "pdf"

        elif suffix in {".html", ".htm"}:
            text, parser = _parse_html(path)
            kind = "html"

        elif suffix == ".json":
            text, parser = _parse_json(path)
            kind = "json"

        elif suffix in {".yaml", ".yml"}:
            text, parser = _parse_yaml(path)
            kind = "yaml"

        elif suffix in {".md", ".markdown", ".rst"}:
            text, parser = _parse_markdown(path)
            kind = "markdown"

        elif suffix in {".txt", ".log"}:
            text, parser = _parse_text(path)
            kind = "text"

        elif suffix == ".csv":
            text, parser = _parse_csv(path)
            kind = "csv"

        elif suffix == ".xml":
            text, parser = _parse_xml(path)
            kind = "xml"

        else:
            raise ParseError("unsupported_type", suffix or "No extension")

    except ParseError:
        raise

    except UnicodeDecodeError as exc:
        raise ParseError("corrupt", str(exc)) from exc

    except OSError as exc:
        raise ParseError("read_error", str(exc)) from exc

    text = clean_text(text)

    if not text:
        raise ParseError("empty", "No extractable text found")

    if pdf_pages is not None:
        pages = [page for page in pdf_pages if page.text or page.tables]
    else:
        pages = _make_pages(text)

    if not pages:
        raise ParseError("empty", "No pages were produced")

    return ParsedDoc(
        parser=parser,
        kind=kind,
        title=_title(path),
        pages=pages,
    )
