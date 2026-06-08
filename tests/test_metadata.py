"""Tests for document metadata extraction and frontmatter rendering."""

from __future__ import annotations

import struct
from datetime import date
from pathlib import Path
from typing import List

import pytest

from hwp2md.metadata import (
    DocumentMetadata,
    _parse_packed_hwp_date,
    parse_iso_date,
    prepend_frontmatter,
    render_frontmatter,
)
from hwp2md.backends.hwpx import convert_hwpx, extract_metadata_hwpx
from hwp2md.exceptions import ConversionError
from tests.fixtures.hwpx_builder import HwpxDocument, build_hwpx_bytes


# metadata module unit tests

def test_render_frontmatter_empty() -> None:
    assert render_frontmatter(DocumentMetadata()) == ""


def test_render_frontmatter_with_title() -> None:
    md = DocumentMetadata(title="보고서")
    out = render_frontmatter(md)
    assert out.startswith("---\n")
    assert "title: 보고서" in out
    assert out.rstrip().endswith("---")


def test_render_frontmatter_full() -> None:
    md = DocumentMetadata(
        title="2025년 동향",
        author="홍길동",
        date=date(2025, 1, 15),
        keywords=["AI", "산업"],
    )
    out = render_frontmatter(md)
    assert "title: 2025년 동향" in out
    assert "author: 홍길동" in out
    assert "date: 2025-01-15" in out
    assert "keywords:" in out
    assert "  - AI" in out
    assert "  - 산업" in out


def test_render_frontmatter_quotes_unsafe_strings() -> None:
    md = DocumentMetadata(title='He said "hi"')
    out = render_frontmatter(md)
    assert 'title: "He said \\"hi\\""' in out


def test_render_frontmatter_quotes_yes_no_null() -> None:
    for word in ("yes", "no", "null", "true", "false"):
        out = render_frontmatter(DocumentMetadata(title=word))
        assert f'title: "{word}"' in out


def test_prepend_frontmatter_only_when_present() -> None:
    body = "# Title\n\nHello."
    assert prepend_frontmatter(body, DocumentMetadata()) == body
    out = prepend_frontmatter(body, DocumentMetadata(title="t"))
    assert out.startswith("---\n")
    assert out.endswith("# Title\n\nHello.")


def test_parse_iso_date_variants() -> None:
    assert parse_iso_date("2025-01-15") == date(2025, 1, 15)
    assert parse_iso_date("2025-01-15T10:30:00") == date(2025, 1, 15)
    assert parse_iso_date("2025-01-15T10:30:00Z") == date(2025, 1, 15)
    assert parse_iso_date("") is None
    assert parse_iso_date("garbage") is None


def test_parse_packed_hwp_date() -> None:
    value = (2025 << 16) | (1 << 8) | 15
    payload = struct.pack("<I", value)
    assert _parse_packed_hwp_date(payload, 0) == date(2025, 1, 15)


def test_parse_packed_hwp_date_year_only_offset() -> None:
    value = (125 << 16) | (3 << 8) | 20
    assert _parse_packed_hwp_date(struct.pack("<I", value), 0) == date(2025, 3, 20)


def test_parse_packed_hwp_date_too_short() -> None:
    assert _parse_packed_hwp_date(b"abc", 0) is None


def test_parse_packed_hwp_date_invalid_components() -> None:
    value = (2025 << 16) | (13 << 8) | 50
    assert _parse_packed_hwp_date(struct.pack("<I", value), 0) is None


def test_document_metadata_is_empty() -> None:
    assert DocumentMetadata().is_empty()
    assert not DocumentMetadata(title="x").is_empty()
    assert not DocumentMetadata(keywords=["x"]).is_empty()


# HWPX integration: metadata in header.xml

def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_hwpx_with_metadata_renders_frontmatter(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.set_metadata(
        title="2025년 동향 보고서",
        author="홍길동",
        date="2025-01-15",
        keywords=["AI", "산업", "동향"],
    )
    doc.add_para("본문", outline=1)
    target = _write(tmp_path, "meta.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert md.startswith("---\n")
    assert "title: 2025년 동향 보고서" in md
    assert "author: 홍길동" in md
    assert "date: 2025-01-15" in md
    assert "  - AI" in md
    assert "# 본문" in md


def test_hwpx_without_metadata_skips_frontmatter(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_para("본문", outline=1)
    target = _write(tmp_path, "plain.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert not md.startswith("---\n")
    assert md.startswith("# 본문")


def test_hwpx_with_metadata_disabled(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.set_metadata(title="My Title", author="Author")
    doc.add_para("body")
    target = _write(tmp_path, "x.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target, with_metadata=False)
    assert "My Title" not in md
    assert "Author" not in md
    assert md.startswith("body")


def test_hwpx_extract_metadata(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.set_metadata(title="T", author="A", date="2025-02-20", keywords=["k1"])
    target = _write(tmp_path, "x.hwpx", build_hwpx_bytes(doc))
    meta = extract_metadata_hwpx(target)
    assert meta.title == "T"
    assert meta.author == "A"
    assert meta.date == date(2025, 2, 20)
    assert meta.keywords == ["k1"]


def test_hwpx_extract_metadata_invalid_archive(tmp_path: Path) -> None:
    target = _write(tmp_path, "bad.hwpx", b"not a zip")
    with pytest.raises(ConversionError):
        extract_metadata_hwpx(target)


def test_hwpx_keywords_split_by_comma(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.set_metadata(title="T", keywords=["A", "B", "C"])
    target = _write(tmp_path, "x.hwpx", build_hwpx_bytes(doc))
    meta = extract_metadata_hwpx(target)
    assert meta.keywords == ["A", "B", "C"]


def test_hwpx_partial_metadata(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.set_metadata(title="Only Title")
    doc.add_para("body")
    target = _write(tmp_path, "x.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert "title: Only Title" in md
    assert "author:" not in md
    assert "date:" not in md
    assert "keywords:" not in md
