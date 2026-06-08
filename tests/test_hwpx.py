"""Tests for the HWPX (XML-based) parser backend."""

from __future__ import annotations

import base64
from pathlib import Path

import pytest

from hwp2md.backends.hwpx import convert_hwpx
from hwp2md.exceptions import (
    ConversionError,
    EncryptedDocumentError,
)
from tests.fixtures.hwpx_builder import HwpxDocument, build_hwpx_bytes


PNG_BYTES = bytes.fromhex(
    "89504E470D0A1A0A0000000D49484452000000010000000108060000001F15C4"
    "890000000A49444154789C6300010000000500010D0A2DB40000000049454E44AE"
    "426082"
)


def _write(tmp_path: Path, name: str, data: bytes) -> Path:
    p = tmp_path / name
    p.write_bytes(data)
    return p


def test_basic_paragraph(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_para("안녕하세요")
    target = _write(tmp_path, "hello.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert md.strip() == "안녕하세요"


def test_heading_uses_outline_level(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_para("제목", outline=1)
    doc.add_para("소제목", outline=2)
    doc.add_para("본문")
    target = _write(tmp_path, "headings.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert "# 제목" in md
    assert "## 소제목" in md
    assert "본문" in md
    assert "###" not in md


def test_outline_level_clamped_to_six(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_para("deep", outline=9)
    target = _write(tmp_path, "deep.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert "###### deep" in md


def test_bold_and_italic(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_para("굵게", bold=True)
    doc.add_para("기울임", italic=True)
    doc.add_para("둘 다", bold=True, italic=True)
    target = _write(tmp_path, "fmt.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert "**굵게**" in md
    assert "*기울임*" in md
    assert "***둘 다***" in md


def test_simple_table_renders_as_gfm(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_table([
        ["이름", "나이"],
        ["홍길동", "30"],
        ["김철수", "25"],
    ])
    target = _write(tmp_path, "tbl.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert "| 이름 | 나이 |" in md
    assert "| --- | --- |" in md
    assert "| 홍길동 | 30 |" in md
    assert "| 김철수 | 25 |" in md


def test_image_link_mode_extracts_to_image_dir(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_image("image1.png", PNG_BYTES)
    doc.add_para("본문", images=[("img001", "BinData/image1.png")])
    target = _write(tmp_path, "img.hwpx", build_hwpx_bytes(doc))
    image_dir = tmp_path / "images"
    md = convert_hwpx(target, image_mode="link", image_dir=image_dir)
    extracted = list(image_dir.iterdir())
    assert len(extracted) == 1
    assert extracted[0].read_bytes() == PNG_BYTES
    assert "images/" in md
    assert ".png" in md


def test_image_embed_mode_uses_data_uri(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_image("image1.png", PNG_BYTES)
    doc.add_para("본문", images=[("img001", "BinData/image1.png")])
    target = _write(tmp_path, "img.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target, image_mode="embed")
    assert "data:image/png;base64," in md
    encoded = base64.b64encode(PNG_BYTES).decode("ascii")
    assert encoded in md


def test_image_skip_mode_omits_image(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_image("image1.png", PNG_BYTES)
    doc.add_para("앞", images=[("img001", "BinData/image1.png")])
    doc.add_para("뒤")
    target = _write(tmp_path, "img.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target, image_mode="skip")
    assert "img" not in md
    assert "data:" not in md
    assert "앞" in md and "뒤" in md


def test_repeated_image_reference_uses_same_placeholder(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_image("image1.png", PNG_BYTES)
    doc.add_para("first", images=[("img001", "BinData/image1.png")])
    doc.add_para("second", images=[("img001", "BinData/image1.png")])
    target = _write(tmp_path, "img.hwpx", build_hwpx_bytes(doc))
    image_dir = tmp_path / "images"
    md = convert_hwpx(target, image_mode="link", image_dir=image_dir)
    matches = list(image_dir.iterdir())
    assert len(matches) == 1
    assert md.count("](img001)") == 0
    assert md.count("img001.png") == 2


def test_wrong_mimetype_raises_encrypted_error(tmp_path: Path) -> None:
    target = _write(
        tmp_path, "fake.hwpx", build_hwpx_bytes(HwpxDocument(), mimetype="text/plain")
    )
    with pytest.raises(EncryptedDocumentError):
        convert_hwpx(target)


def test_missing_mimetype_raises_conversion_error(tmp_path: Path) -> None:
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("Contents/section0.xml", "<x/>")
    target = _write(tmp_path, "no-mime.hwpx", buf.getvalue())
    with pytest.raises(ConversionError):
        convert_hwpx(target)


def test_invalid_zip_raises_conversion_error(tmp_path: Path) -> None:
    target = _write(tmp_path, "bad.hwpx", b"not a zip file")
    with pytest.raises(ConversionError):
        convert_hwpx(target)


def test_empty_document(tmp_path: Path) -> None:
    doc = HwpxDocument()
    target = _write(tmp_path, "empty.hwpx", build_hwpx_bytes(doc))
    md = convert_hwpx(target)
    assert md == ""


def test_invalid_image_mode_rejected(tmp_path: Path) -> None:
    doc = HwpxDocument()
    doc.add_para("x")
    target = _write(tmp_path, "x.hwpx", build_hwpx_bytes(doc))
    with pytest.raises(ConversionError):
        convert_hwpx(target, image_mode="bogus")


def test_missing_source_file_raises_filenotfound(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        convert_hwpx(tmp_path / "missing.hwpx")
