"""Tests for the HWP 5.x (legacy OLE) parser backend."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import List

import pytest

from hwp2md.backends.hwp5 import (
    HWP5_SIGNATURE,
    PARA_TEXT,
    _decompress_section,
    _decode_para_text,
    _iter_records,
    _paragraphs_from_section,
    _looks_encrypted,
    convert_hwp5,
)
from hwp2md.exceptions import ConversionError, EncryptedDocumentError


def _text_record(text: str) -> bytes:
    encoded = text.encode("utf-16-le")
    return struct.pack("<HHI", PARA_TEXT, 0, len(encoded)) + encoded


def _section_with_paragraphs(paragraphs: List[str], *, compressed: bool = False) -> bytes:
    body = b""
    for p in paragraphs:
        body += struct.pack("<HHI", 66, 0, 0)
        body += _text_record(p)
    if compressed:
        compressor = zlib.compressobj(wbits=-15)
        raw_deflate = compressor.compress(body) + compressor.flush()
        header = struct.pack("<II", len(raw_deflate), 0x01)
        return header + raw_deflate
    return body


def test_decode_para_text_basic() -> None:
    payload = "안녕".encode("utf-16-le")
    assert _decode_para_text(payload) == "안녕"


def test_decode_para_text_with_line_break() -> None:
    text = "첫줄\n둘째"
    payload = text.replace("\n", "\x00\x0a").encode("utf-16-le")
    assert _decode_para_text(payload) == "첫줄\n둘째"


def test_decode_para_text_with_tab() -> None:
    payload = "a\tb".encode("utf-16-le")
    assert _decode_para_text(payload) == "a\tb"


def test_decode_para_text_strips_invalid_chars() -> None:
    payload = b"\x00\x00" + "OK".encode("utf-16-le") + b"\xff\xfe"
    assert _decode_para_text(payload) == "OK"


def test_iter_records_walks_correctly() -> None:
    data = struct.pack("<HHI", 1, 0, 3) + b"abc"
    data += struct.pack("<HHI", 2, 0, 4) + b"wxyz"
    records = list(_iter_records(data))
    assert len(records) == 2
    assert records[0] == (1, 0, b"abc")
    assert records[1] == (2, 0, b"wxyz")


def test_iter_records_truncates_on_bad_size() -> None:
    data = struct.pack("<HHI", 1, 0, 100) + b"short"
    records = list(_iter_records(data))
    assert records == []


def test_decompress_section_uncompressed() -> None:
    data = _section_with_paragraphs(["hello"], compressed=False)
    assert _decompress_section(data) == data


def test_decompress_section_compressed() -> None:
    original = _section_with_paragraphs(["hello", "world"], compressed=False)
    compressed = _section_with_paragraphs(["hello", "world"], compressed=True)
    assert _decompress_section(compressed) == original


def test_paragraphs_from_section() -> None:
    data = _section_with_paragraphs(["첫째 단락", "둘째 단락"])
    paras = _paragraphs_from_section(data)
    assert paras == ["첫째 단락", "둘째 단락"]


def test_paragraphs_from_section_empty() -> None:
    assert _paragraphs_from_section(b"") == []


def test_paragraphs_preserves_newlines_in_text() -> None:
    data = _section_with_paragraphs(["한 줄에\n두 줄"])
    paras = _paragraphs_from_section(data)
    assert paras == ["한 줄에\n두 줄"]


def test_looks_encrypted_recognizes_wire_signature() -> None:
    assert _looks_encrypted(bytes.fromhex("77697265") + b"\x00" * 4) is True


def test_looks_encrypted_recognizes_v3_signatures() -> None:
    assert _looks_encrypted(bytes.fromhex("C2BC6B9B") + b"\x00" * 4) is True


def test_looks_encrypted_returns_false_for_normal_header() -> None:
    assert _looks_encrypted(bytes.fromhex("D0CF11E0A1B11AE1")) is False


def test_looks_encrypted_returns_false_for_short_input() -> None:
    assert _looks_encrypted(b"") is False


def test_convert_hwp5_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        convert_hwp5(tmp_path / "nope.hwp")


def test_convert_hwp5_rejects_non_ole_file(tmp_path: Path) -> None:
    target = tmp_path / "fake.hwp"
    target.write_bytes(HWP5_SIGNATURE + b"\x00" * 1024)
    with pytest.raises(ConversionError):
        convert_hwp5(target)


def test_convert_hwp5_detects_encrypted_header(tmp_path: Path) -> None:
    target = tmp_path / "encrypted.hwp"
    target.write_bytes(b"WIRE" + b"\x00" * 1024)
    with pytest.raises(EncryptedDocumentError):
        convert_hwp5(target)


def test_convert_hwp5_signature_mismatch_raises(tmp_path: Path) -> None:
    target = tmp_path / "wrong.hwp"
    target.write_bytes(b"NOT_AN_OLE_FILE" + b"\x00" * 1024)
    with pytest.raises(ConversionError):
        convert_hwp5(target)
