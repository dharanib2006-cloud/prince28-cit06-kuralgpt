import json

import pymupdf
import pytest

from kuralgpt.ingest.parse import (
    PAGE_SIZE,
    ParseError,
    _looks_like_garbled_tamil,
    _remove_repeated_headers_footers,
    clean_text,
    extract_headings,
    parse_file,
)


def test_clean_text_removes_null_and_soft_hyphen():
    result = clean_text("hello\x00 wor\u00adld")
    assert result == "hello world"


def test_clean_text_normalizes_unicode():
    result = clean_text("cafe\u0301")
    assert result == "café"


def test_clean_text_repairs_hyphenated_words():
    result = clean_text("docu-\nment")
    assert result == "document"


def test_clean_text_normalizes_whitespace():
    result = clean_text("hello   world\r\n\r\n\r\nnext")
    assert result == "hello world\n\nnext"


def test_extract_headings():
    text = "# Introduction\n## Background\n### Details"
    assert extract_headings(text) == [
        "Introduction",
        "Background",
        "Details",
    ]


def test_extract_headings_ignores_fenced_code():
    text = "# Real heading\n```python\n# Not a heading\n```\n## Another heading"
    assert extract_headings(text) == [
        "Real heading",
        "Another heading",
    ]


def test_extract_headings_supports_tilde_fence():
    text = "# Heading\n~~~\n## Not a heading\n~~~"
    assert extract_headings(text) == ["Heading"]


def test_empty_text_returns_no_pages():
    from kuralgpt.ingest.parse import _split_text

    assert _split_text("") == []


def test_split_text_creates_pages():
    from kuralgpt.ingest.parse import _split_text

    text = ("word " * 1000).strip()
    pages = _split_text(text)

    assert len(pages) > 1
    assert all(len(page) <= PAGE_SIZE for page in pages)


def test_parse_json_file(tmp_path):
    path = tmp_path / "sample.json"
    path.write_text(
        json.dumps({"title": "Test", "value": 10}),
        encoding="utf-8",
    )

    doc = parse_file(path)

    assert doc.parser == "json"
    assert doc.kind == "json"
    assert '"title": "Test"' in doc.pages[0].text


def test_parse_json_preserves_tamil(tmp_path):
    path = tmp_path / "tamil.json"
    path.write_text(
        json.dumps({"text": "அகர முதல எழுத்தெல்லாம்"}, ensure_ascii=False),
        encoding="utf-8",
    )

    doc = parse_file(path)

    assert "அகர முதல எழுத்தெல்லாம்" in doc.pages[0].text


def test_parse_markdown_file(tmp_path):
    path = tmp_path / "sample.md"
    path.write_text("# Introduction\nSome content.", encoding="utf-8")

    doc = parse_file(path)

    assert doc.parser == "markdown"
    assert doc.kind == "markdown"
    assert "Introduction" in doc.pages[0].headings


def test_parse_text_file(tmp_path):
    path = tmp_path / "sample.txt"
    path.write_text("Simple text document.", encoding="utf-8")

    doc = parse_file(path)

    assert doc.parser == "text"
    assert doc.kind == "text"
    assert "Simple text document." in doc.pages[0].text


def test_parse_csv_file(tmp_path):
    path = tmp_path / "sample.csv"
    path.write_text("name,age\nArun,20\nBala,21\n", encoding="utf-8")

    doc = parse_file(path)

    assert doc.parser == "csv"
    assert "name | age" in doc.pages[0].text
    assert "Arun | 20" in doc.pages[0].text


def test_parse_xml_file(tmp_path):
    path = tmp_path / "sample.xml"
    path.write_text(
        "<root><name>Thirukkural</name></root>",
        encoding="utf-8",
    )

    doc = parse_file(path)

    assert doc.parser == "xml"
    assert "name: Thirukkural" in doc.pages[0].text


def test_missing_file_raises_parse_error(tmp_path):
    path = tmp_path / "missing.json"

    with pytest.raises(ParseError) as error:
        parse_file(path)

    assert error.value.reason == "missing"


def test_unsupported_file_raises_parse_error(tmp_path):
    path = tmp_path / "sample.xyz"
    path.write_text("Some content", encoding="utf-8")

    with pytest.raises(ParseError) as error:
        parse_file(path)

    assert error.value.reason == "unsupported_type"


def test_corrupt_json_raises_parse_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{invalid json}", encoding="utf-8")

    with pytest.raises(ParseError) as error:
        parse_file(path)

    assert error.value.reason == "corrupt"


def test_parse_yaml_file(tmp_path):
    path = tmp_path / "sample.yaml"
    path.write_text(
        "title: Thirukkural\nlanguage: Tamil\n",
        encoding="utf-8",
    )

    doc = parse_file(path)

    assert doc.parser == "pyyaml"
    assert doc.kind == "yaml"
    assert "Thirukkural" in doc.pages[0].text
    assert "Tamil" in doc.pages[0].text


def test_parse_yaml_preserves_unicode(tmp_path):
    path = tmp_path / "tamil.yaml"
    path.write_text(
        "text: தமிழ்\n",
        encoding="utf-8",
    )

    doc = parse_file(path)

    assert "தமிழ்" in doc.pages[0].text


def test_corrupt_yaml_raises_parse_error(tmp_path):
    path = tmp_path / "broken.yaml"
    path.write_text("title: [invalid", encoding="utf-8")

    with pytest.raises(ParseError) as error:
        parse_file(path)

    assert error.value.reason == "corrupt"


def test_remove_repeated_pdf_headers_and_footers():
    page_lines = [
        ["Document Header", "Page one content", "Document Footer"],
        ["Document Header", "Page two content", "Document Footer"],
        ["Document Header", "Page three content", "Document Footer"],
    ]

    result = _remove_repeated_headers_footers(page_lines)

    assert result == [
        ["Page one content"],
        ["Page two content"],
        ["Page three content"],
    ]


def test_remove_headers_keeps_unique_content():
    page_lines = [
        ["Document Header", "First page content", "Page 1"],
        ["Document Header", "Second page content", "Page 2"],
        ["Document Header", "Third page content", "Page 3"],
    ]

    result = _remove_repeated_headers_footers(page_lines)

    assert all("Document Header" not in lines for lines in result)
    assert "Page 1" in result[0]
    assert "Page 2" in result[1]
    assert "Page 3" in result[2]


def test_parse_pdf_extracts_text_and_headings(tmp_path):
    path = tmp_path / "sample.pdf"

    document = pymupdf.open()
    page = document.new_page()

    page.insert_text(
        (72, 72),
        "Chapter One",
        fontsize=24,
    )
    page.insert_text(
        (72, 120),
        "This is the PDF body content.",
        fontsize=10,
    )

    document.save(path)
    document.close()

    doc = parse_file(path)

    assert doc.kind == "pdf"
    assert doc.parser == "pymupdf"
    assert len(doc.pages) == 1
    assert "Chapter One" in doc.pages[0].headings
    assert "PDF body content" in doc.pages[0].text


def test_parse_scanned_pdf_with_ocr(tmp_path, monkeypatch):
    path = tmp_path / "scanned.pdf"

    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    class FakeTextPage:
        def extractText(self):
            return "Recognized OCR text"

    def fake_ocr(self, language, dpi, full=False):
        assert language == "eng"
        assert dpi == 200
        assert full is True
        return FakeTextPage()

    monkeypatch.setattr(
        pymupdf.Page,
        "get_textpage_ocr",
        fake_ocr,
    )

    doc = parse_file(path, ocr_language="eng")

    assert len(doc.pages) == 1
    assert "Recognized OCR text" in doc.pages[0].text


def test_parse_mixed_pdf_ocr_only_scanned_page(tmp_path, monkeypatch):
    path = tmp_path / "mixed.pdf"

    document = pymupdf.open()

    text_page = document.new_page()
    text_page.insert_text((72, 72), "Normal text page.")

    document.new_page()

    document.save(path)
    document.close()

    ocr_calls = []

    class FakeTextPage:
        def extractText(self):
            return "Scanned page OCR text"

    def fake_ocr(self, language, dpi, full=False):
        ocr_calls.append(language)
        return FakeTextPage()

    monkeypatch.setattr(
        pymupdf.Page,
        "get_textpage_ocr",
        fake_ocr,
    )

    doc = parse_file(path, ocr_language="eng")

    assert len(doc.pages) == 2
    assert "Normal text page." in doc.pages[0].text
    assert "Scanned page OCR text" in doc.pages[1].text
    assert ocr_calls == ["eng"]


def test_parse_pdf_ocr_failure_raises_parse_error(tmp_path, monkeypatch):
    path = tmp_path / "scanned.pdf"

    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    def fake_ocr(self, language, dpi, full=False):
        raise RuntimeError("Tesseract unavailable")

    monkeypatch.setattr(
        pymupdf.Page,
        "get_textpage_ocr",
        fake_ocr,
    )

    with pytest.raises(ParseError) as error:
        parse_file(path, ocr_language="eng")

    assert error.value.reason == "ocr_failed"
    assert "Tesseract unavailable" in error.value.detail


def test_parse_pdf_detects_scanned_pages_by_original_page_number(tmp_path):
    path = tmp_path / "three_pages.pdf"

    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text(
        (72, 72),
        "This is the first normal text page with sufficient content.",
    )

    page2 = document.new_page()
    page2.insert_text(
        (72, 72),
        "This is the second normal text page with sufficient content.",
    )

    document.new_page()

    document.save(path)
    document.close()

    doc = parse_file(path)

    assert len(doc.pages) == 2
    assert doc.scanned_pages == [3]
    assert doc.pages[0].page_no == 1
    assert doc.pages[1].page_no == 2


def test_scanned_page_detection_is_preserved_after_ocr(tmp_path, monkeypatch):
    path = tmp_path / "scanned_detection.pdf"

    document = pymupdf.open()

    page1 = document.new_page()
    page1.insert_text(
        (72, 72),
        "This is a normal text page with sufficient content.",
    )

    document.new_page()

    document.save(path)
    document.close()

    class FakeTextPage:
        def extractText(self):
            return "Recognized scanned page content."

    def fake_ocr(self, language, dpi, full=False):
        return FakeTextPage()

    monkeypatch.setattr(
        pymupdf.Page,
        "get_textpage_ocr",
        fake_ocr,
    )

    doc = parse_file(path, ocr_language="eng")

    assert len(doc.pages) == 2
    assert "Recognized scanned page content." in doc.pages[1].text
    assert doc.scanned_pages == [2]


def test_detects_garbled_tscii_tamil():
    text = "«¢ÕÅûÙ÷ÇÂ§ÄØò¦¡õ¬ÀÃÓ¿ÉÁÌÈÆñÐÜö"

    assert _looks_like_garbled_tamil(text) is True


def test_preserves_readable_unicode_tamil():
    text = "திருக்குறள் உலகப் பொதுமறை ஆகும்"

    assert _looks_like_garbled_tamil(text) is False


def test_does_not_detect_normal_english_as_garbled_tamil():
    text = "This is a normal English document with sufficient content."

    assert _looks_like_garbled_tamil(text) is False
