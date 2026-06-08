"""Tests for the HWP 5.x (legacy OLE) parser backend."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import List

import pytest

from hwp2md.backends.hwp5 import (
    HWP5_SIGNATURE,
    PARA_CHAR_SHAPE,
    PARA_HEADER,
    PARA_TEXT,
    TABLE,
    TABLE_CELL,
    _decode_para_char_shape,
    _decode_para_text,
    _decompress_section,
    _iter_records,
    _looks_encrypted,
    _parse_char_shape_payload,
    _SectionParser,
    convert_hwp5,
)
from hwp2md.exceptions import ConversionError, EncryptedDocumentError


CHAR_SHAPE_SIZE = 34


def _para_header(level: int = 0) -> bytes:
    return struct.pack("<HHI", PARA_HEADER, level, 0)


def _text_record(text: str, level: int = 0) -> bytes:
    encoded = text.encode("utf-16-le")
    return struct.pack("<HHI", PARA_TEXT, level, len(encoded)) + encoded


def _para_char_shape(
    slots: List[tuple], para_shape_id: int = 0, level: int = 0
) -> bytes:
    body = struct.pack("<H", len(slots))
    for pos, shape_id in slots:
        body += struct.pack("<HH", pos, shape_id)
    body += struct.pack("<H", para_shape_id)
    return struct.pack("<HHI", PARA_CHAR_SHAPE, level, len(body)) + body


def _table_record(level: int = 0, rows: int = 1, cols: int = 1) -> bytes:
    payload = struct.pack("<HHH", 1, rows, cols)
    return struct.pack("<HHI", TABLE, level, len(payload)) + payload


def _table_cell_record(level: int = 0) -> bytes:
    return struct.pack("<HHI", TABLE_CELL, level, 0)


def _section_with_paragraphs(
    paragraphs: List[str], *, compressed: bool = False
) -> bytes:
    body = b""
    for p in paragraphs:
        body += _para_header(0)
        body += _text_record(p, 0)
    if compressed:
        compressor = zlib.compressobj(wbits=-15)
        raw_deflate = compressor.compress(body) + compressor.flush()
        header = struct.pack("<II", len(raw_deflate), 0x01)
        return header + raw_deflate
    return body


def _section_with_records(records: List[bytes], *, compressed: bool = False) -> bytes:
    body = b"".join(records)
    if compressed:
        compressor = zlib.compressobj(wbits=-15)
        raw_deflate = compressor.compress(body) + compressor.flush()
        header = struct.pack("<II", len(raw_deflate), 0x01)
        return header + raw_deflate
    return body


def _char_shape_with(
    *,
    bold: bool = False,
    italic: bool = False,
    underline: bool = False,
    strikethrough: bool = False,
) -> bytes:
    payload = bytearray(CHAR_SHAPE_SIZE)
    payload[7] = 1 if bold else 0
    payload[8] = 1 if italic else 0
    payload[9] = 1 if underline else 0
    payload[10] = 1 if strikethrough else 0
    return bytes(payload)


def test_decode_para_text_basic() -> None:
    assert _decode_para_text("안녕".encode("utf-16-le")) == "안녕"


def test_decode_para_text_with_line_break() -> None:
    payload = ("첫줄" + "\x00\x0a" + "둘째").encode("utf-16-le")
    assert _decode_para_text(payload) == "첫줄\n둘째"


def test_decode_para_text_with_tab() -> None:
    assert _decode_para_text("a\tb".encode("utf-16-le")) == "a\tb"


def test_decode_para_text_strips_bom() -> None:
    payload = b"\x00\x00" + "OK".encode("utf-16-le") + b"\xff\xfe"
    assert _decode_para_text(payload) == "OK"


def test_iter_records_walks_correctly() -> None:
    data = struct.pack("<HHI", 1, 0, 3) + b"abc"
    data += struct.pack("<HHI", 2, 0, 4) + b"wxyz"
    assert list(_iter_records(data)) == [(1, 0, b"abc"), (2, 0, b"wxyz")]


def test_iter_records_truncates_on_bad_size() -> None:
    data = struct.pack("<HHI", 1, 0, 100) + b"short"
    assert list(_iter_records(data)) == []


def test_decompress_section_uncompressed() -> None:
    data = _section_with_paragraphs(["hello"], compressed=False)
    assert _decompress_section(data) == data


def test_decompress_section_compressed() -> None:
    original = _section_with_paragraphs(["hello", "world"], compressed=False)
    assert (
        _decompress_section(
            _section_with_paragraphs(["hello", "world"], compressed=True)
        )
        == original
    )


def test_looks_encrypted_recognizes_wire_signature() -> None:
    assert _looks_encrypted(bytes.fromhex("77697265") + b"\x00" * 4) is True


def test_looks_encrypted_recognizes_v3_signatures() -> None:
    assert _looks_encrypted(bytes.fromhex("C2BC6B9B") + b"\x00" * 4) is True


def test_looks_encrypted_returns_false_for_normal_header() -> None:
    assert _looks_encrypted(bytes.fromhex("D0CF11E0A1B11AE1")) is False


def test_looks_encrypted_returns_false_for_short_input() -> None:
    assert _looks_encrypted(b"") is False


def test_section_parser_returns_paragraphs() -> None:
    data = _section_with_records(
        [_para_header(0), _text_record("첫째"), _para_header(0), _text_record("둘째")]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, {}).parse()
    assert [p.runs[0].text for p in paras] == ["첫째", "둘째"]


def test_section_parser_recognizes_simple_table() -> None:
    data = _section_with_records(
        [
            _para_header(0),
            _text_record("서론"),
            _table_record(0, rows=2, cols=2),
            _table_cell_record(0),
            _para_header(0),
            _text_record("A1", 0),
            _table_cell_record(0),
            _para_header(0),
            _text_record("B1", 0),
            _table_cell_record(0),
            _para_header(0),
            _text_record("A2", 0),
            _table_cell_record(0),
            _para_header(0),
            _text_record("B2", 0),
        ]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, {}).parse()
    assert len(paras) == 2
    assert not paras[0].is_table
    assert paras[1].is_table
    assert paras[1].table_rows == [["A1", "B1"], ["A2", "B2"]]


def test_section_parser_uses_char_shapes_for_formatting() -> None:
    char_shapes = {
        0: _parse_char_shape_payload(_char_shape_with(bold=True, italic=False)),
        1: _parse_char_shape_payload(_char_shape_with(bold=False, italic=True)),
    }
    data = _section_with_records(
        [
            _para_header(0),
            _para_char_shape([(0, 0), (2, 1)], 0, 0),
            _text_record("ABCD", 0),
        ]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, char_shapes).parse()
    assert len(paras) == 1
    runs = paras[0].runs
    assert len(runs) == 2
    assert runs[0].text == "AB" and runs[0].bold and not runs[0].italic
    assert runs[1].text == "CD" and not runs[1].bold and runs[1].italic


def test_section_parser_underline_and_strikethrough() -> None:
    char_shapes = {
        0: _parse_char_shape_payload(_char_shape_with(underline=True, strikethrough=True)),
    }
    data = _section_with_records(
        [
            _para_header(0),
            _para_char_shape([(0, 0)], 0, 0),
            _text_record("X", 0),
        ]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, char_shapes).parse()
    run = paras[0].runs[0]
    assert run.underline and run.strikethrough


def test_section_parser_skips_blank_paragraph() -> None:
    data = _section_with_records([_para_header(0), _text_record("   ")])
    records = list(_iter_records(data))
    paras = _SectionParser(records, {}).parse()
    assert paras == []


def test_decode_para_char_shape_extracts_slots() -> None:
    body = struct.pack("<H", 2)
    body += struct.pack("<HH", 0, 5)
    body += struct.pack("<HH", 4, 7)
    body += struct.pack("<H", 99)
    slots, para_id = _decode_para_char_shape(body)
    assert slots == [(0, 5), (4, 7)]
    assert para_id == 99


def test_decode_para_char_shape_handles_short_payload() -> None:
    slots, para_id = _decode_para_char_shape(b"")
    assert slots == []
    assert para_id == 0


def test_parse_char_shape_payload_detects_bold() -> None:
    shape = _parse_char_shape_payload(_char_shape_with(bold=True))
    assert shape.bold is True
    assert shape.italic is False
    assert shape.underline is False
    assert shape.strikethrough is False


def test_parse_char_shape_payload_detects_all_flags() -> None:
    shape = _parse_char_shape_payload(
        _char_shape_with(bold=True, italic=True, underline=True, strikethrough=True)
    )
    assert shape.bold and shape.italic and shape.underline and shape.strikethrough


def test_parse_char_shape_payload_too_short() -> None:
    shape = _parse_char_shape_payload(b"\x00" * 10)
    assert shape.bold is False
    assert shape.italic is False


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


def test_convert_hwp5_invalid_image_mode(tmp_path: Path) -> None:
    target = tmp_path / "x.hwp"
    target.write_bytes(HWP5_SIGNATURE + b"\x00" * 1024)
    with pytest.raises(ConversionError):
        convert_hwp5(target, image_mode="bogus")


def test_section_parser_combines_multi_paragraph_cell() -> None:
    data = _section_with_records(
        [
            _table_record(0, rows=1, cols=1),
            _table_cell_record(0),
            _para_header(0),
            _text_record("first", 0),
            _para_header(0),
            _text_record("second", 0),
        ]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, {}).parse()
    assert len(paras) == 1
    assert paras[0].is_table
    assert paras[0].table_rows == [["first\nsecond"]]


def test_section_parser_ignores_table_with_no_cells() -> None:
    data = _section_with_records(
        [_para_header(0), _text_record("before"), _table_record(0, rows=1, cols=1)]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, {}).parse()
    assert len(paras) == 1
    assert not paras[0].is_table


def test_section_parser_handles_table_with_no_payload() -> None:
    table_record = struct.pack("<HHI", TABLE, 0, 0)
    data = _section_with_records(
        [
            table_record,
            _table_cell_record(0),
            _para_header(0),
            _text_record("only", 0),
        ]
    )
    records = list(_iter_records(data))
    paras = _SectionParser(records, {}).parse()
    assert len(paras) == 1
    assert paras[0].is_table
    assert paras[0].table_rows == [["only"]]
