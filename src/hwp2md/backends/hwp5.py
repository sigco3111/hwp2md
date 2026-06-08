"""HWP 5.x (legacy OLE container) conversion backend.

HWP 5.x stores content in an OLE Compound Document with one
``BodyText/SectionN`` stream per section. Each stream is a sequence
of records, optionally zlib-compressed. Records are arranged in a
level-based tree (root paragraphs at level 0, their child controls
at level >= 1) so tables and inline marks require a stack walker.

For 0.3.0 the parser handles paragraphs, tables, character
formatting (bold/italic/underline/strikethrough), and image
extraction from BinData/* streams. Footnotes and header/footer
handling are still deferred.
"""

from __future__ import annotations

import io
import struct
import zlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Tuple

from hwp2md._markdown import gfm_table, sanitize_inline
from hwp2md.exceptions import ConversionError, EncryptedDocumentError
from hwp2md.metadata import (
    DocumentMetadata,
    _parse_packed_hwp_date,
    prepend_frontmatter,
)

HWP5_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")

CTRL_HEADER = 47
CHAR_SHAPE = 49
PARA_CHAR_SHAPE = 54
PARA_HEADER = 66
PARA_TEXT = 67
TABLE = 68
TABLE_CELL = 69
LIST_HEADER = 73
DOCUMENT_PROPERTIES = 78
IDENTITY_NAME = 72
SHAPE_COMPONENT = 81

PARA_CONTROL_NEW = 0x0000
PARA_CONTROL_LINE_BREAK = 0x000A
PARA_CONTROL_SOFT_BREAK = 0x000B
PARA_CONTROL_TAB = 0x0009
PARA_CONTROL_FIELDBEGIN = 0x0002
PARA_CONTROL_FIELDEND = 0x0003
PARA_CONTROL_UNKNOWN_EXT = 0x000C

DOCINFO_CHAR_SHAPE_SIZE_50 = 34
DOCINFO_CHAR_SHAPE_SIZE_51 = 38


@dataclass
class CharShape:
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False


@dataclass
class Hwp5Run:
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False


@dataclass
class Hwp5Paragraph:
    runs: List[Hwp5Run] = field(default_factory=list)
    table_rows: Optional[List[List[str]]] = None

    @property
    def is_table(self) -> bool:
        return self.table_rows is not None


def _read_olefile():
    try:
        import olefile  # type: ignore
    except ImportError as e:
        raise ConversionError(
            "HWP 5.x parsing requires the `olefile` optional dependency. "
            "Install with: pip install \"hwp2md[olefile]\""
        ) from e
    return olefile


def _check_encryption(source: Path) -> None:
    """Detect password-protected HWP files via the header signature."""
    with source.open("rb") as f:
        sig = f.read(8)
    if sig.startswith(bytes.fromhex("77697265")) or sig.startswith(b"WIRE"):
        raise EncryptedDocumentError(
            f"HWP file appears to be password-protected (WIRE): {source.name}"
        )
    if sig.startswith(bytes.fromhex("C2BC6B9B")):
        raise EncryptedDocumentError(
            f"HWP file is in a legacy encrypted format: {source.name}"
        )
    if not sig.startswith(HWP5_SIGNATURE):
        raise ConversionError(
            f"Not a valid HWP 5.x file (signature mismatch): {source.name}"
        )


def _looks_encrypted(sig_bytes: bytes) -> bool:
    if sig_bytes.startswith(bytes.fromhex("77697265")):
        return True
    if sig_bytes.startswith(bytes.fromhex("C2BC6B9B")):
        return True
    return False


def _decompress_section(data: bytes) -> bytes:
    if len(data) < 8:
        return data
    compressed_size = struct.unpack_from("<I", data, 0)[0]
    flag = struct.unpack_from("<I", data, 4)[0]
    payload = data[8:]
    if flag & 0x01 == 0:
        if compressed_size != len(data):
            return data
        return data[8:]
    if compressed_size > 2**24:
        return data
    try:
        return zlib.decompress(payload, -15)
    except zlib.error:
        return payload


def _iter_records(data: bytes) -> Iterator[Tuple[int, int, bytes]]:
    offset = 0
    n = len(data)
    while offset + 8 <= n:
        tag = struct.unpack_from("<H", data, offset)[0]
        level = struct.unpack_from("<H", data, offset + 2)[0]
        size = struct.unpack_from("<I", data, offset + 4)[0]
        offset += 8
        if offset + size > n:
            break
        yield tag, level, data[offset : offset + size]
        offset += size


def _decode_para_text(payload: bytes) -> str:
    if not payload:
        return ""
    chars: List[str] = []
    for i in range(0, len(payload) - 1, 2):
        code = struct.unpack_from("<H", payload, i)[0]
        if code == PARA_CONTROL_LINE_BREAK:
            chars.append("\n")
        elif code == PARA_CONTROL_TAB:
            chars.append("\t")
        elif code == PARA_CONTROL_SOFT_BREAK:
            chars.append(" ")
        elif code == PARA_CONTROL_FIELDBEGIN:
            chars.append(" ")
        elif code == PARA_CONTROL_FIELDEND:
            chars.append(" ")
        elif code == PARA_CONTROL_NEW:
            chars.append("")
        elif code == PARA_CONTROL_UNKNOWN_EXT:
            chars.append(" ")
        elif 0x0020 <= code <= 0xFFFD and code not in (0xFEFF, 0xFFFE, 0xFFFF):
            try:
                chars.append(chr(code))
            except (ValueError, OverflowError):
                chars.append(" ")
        else:
            chars.append("")
    return "".join(chars)


def _decode_para_char_shape(payload: bytes) -> Tuple[List[Tuple[int, int]], int]:
    """Return [(position_offset, char_shape_id), ...] and the para_shape_id."""
    if len(payload) < 4:
        return [], 0
    count = struct.unpack_from("<H", payload, 0)[0]
    slots: List[Tuple[int, int]] = []
    offset = 2
    for _ in range(count):
        if offset + 4 > len(payload):
            break
        pos, shape_id = struct.unpack_from("<HH", payload, offset)
        slots.append((pos, shape_id))
        offset += 4
    para_shape_id = 0
    if offset + 2 <= len(payload):
        para_shape_id = struct.unpack_from("<H", payload, offset)[0]
    return slots, para_shape_id


def _decode_table_dims(payload: bytes) -> Tuple[int, int]:
    """Extract (rows, cols) from a HWPTAG_TABLE record payload.

    The first 4 bytes are: page_break (u16) + rows (u16) + cols (u16)
    comes next. Returns (1, 1) if the payload is too short to read.
    """
    if len(payload) < 6:
        return 1, 1
    rows, cols = struct.unpack_from("<HH", payload, 2)
    return max(1, rows), max(1, cols)


def _parse_char_shape_payload(payload: bytes) -> CharShape:
    """Parse one HWPTAG_CHAR_SHAPE record payload into a CharShape.

    The format is version-dependent; the formatting flags live at
    fixed offsets for both 5.0 (34 bytes) and 5.1 (38 bytes).
    """
    bold = italic = underline = strikethrough = False
    if len(payload) >= DOCINFO_CHAR_SHAPE_SIZE_50:
        bold = payload[7] != 0
        italic = payload[8] != 0
        underline = payload[9] != 0
        strikethrough = payload[10] != 0
    return CharShape(
        bold=bold,
        italic=italic,
        underline=underline,
        strikethrough=strikethrough,
    )


def _read_char_shapes(ole, source: Path) -> Dict[int, CharShape]:
    """Read all HWPTAG_CHAR_SHAPE definitions from the DocInfo stream."""
    shapes: Dict[int, CharShape] = {}
    try:
        if not ole.exists("DocInfo"):
            return shapes
        with ole.openstream("DocInfo") as s:
            data = s.read()
    except (KeyError, OSError):
        return shapes
    decompressed = _decompress_section(data)
    for tag, _level, payload in _iter_records(decompressed):
        if tag == CHAR_SHAPE:
            shape = _parse_char_shape_payload(payload)
            shapes[len(shapes)] = shape
    return shapes


def _read_docinfo_records(ole, source: Path):
    """Yield (tag, level, payload) records from the decompressed DocInfo stream."""
    try:
        if not ole.exists("DocInfo"):
            return
        with ole.openstream("DocInfo") as s:
            data = s.read()
    except (KeyError, OSError):
        return
    decompressed = _decompress_section(data)
    yield from _iter_records(decompressed)


def _extract_metadata_hwp5(ole, source: Path) -> DocumentMetadata:
    """Read metadata from the DocInfo stream.

    The dates come from HWPTAG_DOCUMENT_PROPERTIES (the bit-packed
    ``(year << 16) | (month << 8) | day`` value sits at offset
    14 once the section/page/footnote/endnote/image/table
    counters are skipped). Author/title are best-effort — the
    HWP 5.x format does not store them in a fixed record, so we
    scan HWPTAG_IDENTITY_NAME for any non-empty UTF-16LE string.
    """
    meta = DocumentMetadata()
    found_creation = False
    found_last_mod = False
    for tag, _level, payload in _read_docinfo_records(ole, source):
        if tag == DOCUMENT_PROPERTIES and len(payload) >= 22:
            if not found_creation:
                created = _parse_packed_hwp_date(payload, 14)
                if created:
                    meta.date = created
                    found_creation = True
            if not found_last_mod:
                modified = _parse_packed_hwp_date(payload, 18)
                if modified:
                    meta.last_modified = modified
                    found_last_mod = True
            if len(payload) >= 38 and not meta.author:
                try:
                    candidate = payload[22:38].decode("utf-16-le", errors="ignore").strip("\x00 ")
                    if candidate:
                        meta.author = candidate
                except UnicodeDecodeError:
                    pass
        elif tag == IDENTITY_NAME and not meta.author:
            try:
                candidate = payload.decode("utf-16-le", errors="ignore").strip("\x00 ").strip()
                if candidate:
                    meta.author = candidate
            except UnicodeDecodeError:
                pass
    return meta


def _list_bindata_streams(ole) -> List[Tuple[str, bytes]]:
    """Extract all BinData/* stream contents (name, bytes)."""
    out: List[Tuple[str, bytes]] = []
    try:
        names = [
            n for n in ole.listdir(streams=True, storages=False)
            if n and n[0] == "BinData"
        ]
    except (OSError, ValueError):
        return out
    for name in names:
        try:
            with ole.openstream(name) as s:
                out.append((name[-1], s.read()))
        except (KeyError, OSError):
            continue
    return out


def _format_run(run: Hwp5Run) -> str:
    text = sanitize_inline(run.text)
    if not text:
        return ""
    parts = [text]
    if run.underline:
        parts = ["<u>", text, "</u>"]
    if run.strikethrough:
        parts = ["~~", *parts, "~~"]
    if run.italic:
        parts = ["*", *parts, "*"]
    if run.bold:
        parts = ["**", *parts, "**"]
    return "".join(parts) if isinstance(parts, list) else parts


def _split_para_text_into_runs(
    text: str, slots: List[Tuple[int, int]], char_shapes: Dict[int, CharShape]
) -> List[Hwp5Run]:
    """Cut a paragraph string into runs based on PARA_CHAR_SHAPE slots.

    A slot's ``position_offset`` is the 16-bit char count where its
    shape becomes effective (the slot list is sorted by offset). Char
    shapes whose flags are all false map to the default run, so we
    only emit runs when the shape actually changes something visible.
    """
    if not slots or not text:
        return [Hwp5Run(text=text)]
    sorted_slots = sorted(slots, key=lambda s: s[0])
    runs: List[Hwp5Run] = []
    cursor = 0
    current_shape: Optional[CharShape] = None
    for pos, shape_id in sorted_slots:
        if pos > cursor and pos <= len(text):
            chunk = text[cursor:pos]
            runs.append(Hwp5Run(text=chunk, **_shape_to_kwargs(current_shape)))
        cursor = pos
        current_shape = char_shapes.get(shape_id)
    if cursor < len(text):
        runs.append(Hwp5Run(text=text[cursor:], **_shape_to_kwargs(current_shape)))
    return runs


def _shape_to_kwargs(shape: Optional[CharShape]) -> dict:
    if shape is None:
        return {}
    return {
        "bold": shape.bold,
        "italic": shape.italic,
        "underline": shape.underline,
        "strikethrough": shape.strikethrough,
    }


class _SectionParser:
    def __init__(
        self,
        records: List[Tuple[int, int, bytes]],
        char_shapes: Dict[int, CharShape],
    ) -> None:
        self.records = records
        self.char_shapes = char_shapes

    def parse(self) -> List[Hwp5Paragraph]:
        out: List[Hwp5Paragraph] = []
        i = 0
        n = len(self.records)
        while i < n:
            tag, level, payload = self.records[i]
            if tag == TABLE:
                consumed, table_para = self._parse_table(i, level)
                if table_para is not None:
                    out.append(table_para)
                i += max(1, consumed)
            elif tag == PARA_HEADER and level == 0:
                consumed, para = self._parse_paragraph(i, level)
                if para is not None:
                    out.append(para)
                i += max(1, consumed)
            else:
                i += 1
        return out

    def _parse_table(self, start: int, _level: int) -> Tuple[int, Optional[Hwp5Paragraph]]:
        rows_count, cols_count = _decode_table_dims(self.records[start][2])
        rows: List[List[str]] = [[] for _ in range(rows_count)]
        i = start + 1
        n = len(self.records)
        cell_paragraphs: List[str] = []
        current_para_parts: List[str] = []
        current_para_slots: List[Tuple[int, int]] = []
        in_cell = False
        cell_index = 0

        def _flush_paragraph_into_cell() -> None:
            nonlocal current_para_parts, current_para_slots
            text = "".join(current_para_parts).strip()
            if not text and not current_para_slots:
                current_para_parts = []
                current_para_slots = []
                return
            if current_para_slots and self.char_shapes:
                runs = _split_para_text_into_runs(
                    text, current_para_slots, self.char_shapes
                )
            else:
                runs = [Hwp5Run(text=text)] if text else []
            cell_paragraphs.append(_format_paragraph_runs(runs))
            current_para_parts = []
            current_para_slots = []

        def _flush_cell() -> None:
            nonlocal cell_index, in_cell
            _flush_paragraph_into_cell()
            cell_text = "\n".join(p for p in cell_paragraphs if p)
            target_row = cell_index // cols_count if cols_count > 0 else 0
            while target_row >= len(rows):
                rows.append([])
            rows[target_row].append(cell_text)
            cell_index += 1
            cell_paragraphs.clear()
            in_cell = False

        while i < n:
            tag, level, payload = self.records[i]
            if tag == TABLE and level == _level:
                if in_cell:
                    _flush_cell()
                break
            if tag == TABLE_CELL:
                if in_cell:
                    _flush_cell()
                in_cell = True
                i += 1
                continue
            if not in_cell:
                i += 1
                continue
            if tag == PARA_HEADER:
                _flush_paragraph_into_cell()
                i += 1
                continue
            if tag == PARA_CHAR_SHAPE:
                slots, _ = _decode_para_char_shape(payload)
                current_para_slots = slots
                i += 1
                continue
            if tag == PARA_TEXT:
                current_para_parts.append(_decode_para_text(payload))
                i += 1
                continue
            i += 1
        if in_cell:
            _flush_cell()
        rows = [r for r in rows if any(c for c in r)]
        if not rows:
            return i - start, None
        return i - start, Hwp5Paragraph(table_rows=rows)

    def _parse_cell_paragraph(
        self, start: int, cell_level: int
    ) -> Tuple[int, Optional[List[Hwp5Run]]]:
        para_level = cell_level + 1
        i = start
        n = len(self.records)
        runs: List[Hwp5Run] = []
        slots: List[Tuple[int, int]] = []
        text_parts: List[str] = []
        if i < n and self.records[i][0] == PARA_HEADER and self.records[i][1] == para_level:
            i += 1
        while i < n:
            tag, level, payload = self.records[i]
            if level <= cell_level:
                break
            if tag == PARA_CHAR_SHAPE and level == para_level:
                slots, _ = _decode_para_char_shape(payload)
                i += 1
                continue
            if tag == PARA_TEXT and level == para_level:
                text_parts.append(_decode_para_text(payload))
                i += 1
                continue
            if level < para_level:
                break
            i += 1
        text = "".join(text_parts)
        if slots and self.char_shapes:
            runs = _split_para_text_into_runs(text, slots, self.char_shapes)
        elif text:
            runs = [Hwp5Run(text=text)]
        if not runs:
            return i - start, None
        return i - start, runs

    def _parse_paragraph(
        self, start: int, base_level: int
    ) -> Tuple[int, Optional[Hwp5Paragraph]]:
        i = start
        n = len(self.records)
        text_parts: List[str] = []
        slots: List[Tuple[int, int]] = []
        if i < n and self.records[i][0] == PARA_HEADER and self.records[i][1] == base_level:
            i += 1
        while i < n:
            tag, level, payload = self.records[i]
            if level < base_level:
                break
            if tag == PARA_CHAR_SHAPE and level == base_level:
                slots, _ = _decode_para_char_shape(payload)
                i += 1
                continue
            if tag == PARA_TEXT and level == base_level:
                text_parts.append(_decode_para_text(payload))
                i += 1
                continue
            if level <= base_level and tag not in (PARA_TEXT, PARA_CHAR_SHAPE):
                break
            i += 1
        text = "".join(text_parts).strip()
        if not text:
            return i - start, None
        if slots and self.char_shapes:
            runs = _split_para_text_into_runs(text, slots, self.char_shapes)
        else:
            runs = [Hwp5Run(text=text)]
        return i - start, Hwp5Paragraph(runs=runs)


def _format_paragraph_runs(runs: List[Hwp5Run]) -> str:
    parts = [_format_run(r) for r in runs if r.text]
    return "".join(parts).strip()


def _paragraph_to_markdown(para: Hwp5Paragraph) -> str:
    if para.is_table:
        return gfm_table(para.table_rows or [], header=True)
    return _format_paragraph_runs(para.runs)


def _extract_bindata(ole, image_dir: Path) -> List[Path]:
    """Copy BinData/* streams into ``image_dir`` and return the file paths."""
    image_dir.mkdir(parents=True, exist_ok=True)
    extracted: List[Path] = []
    for name, data in _list_bindata_streams(ole):
        out_path = image_dir / name
        out_path.write_bytes(data)
        extracted.append(out_path)
    return extracted


def convert_hwp5(
    source: Path,
    *,
    encoding: str = "utf-8",
    image_mode: str = "skip",
    image_dir: Optional[Path] = None,
    with_metadata: bool = True,
) -> str:
    """Convert a .hwp (HWP 5.x) file to markdown.

    Supports paragraphs, tables, character formatting (bold/italic/
    underline/strikethrough), and image extraction from BinData/*
    streams. HWP 5.x does not encode inline image positions in a
    recoverable way, so images are extracted up front and a single
    reference to the first image is appended at the end of the
    document.

    When ``with_metadata`` is true and DocInfo exposes
    HWPTAG_DOCUMENT_PROPERTIES (or HWPTAG_IDENTITY_NAME for the
    author), a YAML frontmatter block is prepended to the output.
    """
    del encoding
    if not source.is_file():
        raise FileNotFoundError(f"HWP file not found: {source}")
    if image_mode not in {"embed", "link", "skip"}:
        raise ConversionError(f"Invalid image_mode: {image_mode!r}")
    _check_encryption(source)
    olefile = _read_olefile()
    source_str = str(source)
    if not olefile.isOleFile(source_str):
        raise ConversionError(
            f"File is not an OLE compound document: {source.name}"
        )
    try:
        ole = olefile.OleFileIO(source_str)
    except (olefile.olefile.NotOleFileError, ValueError, OSError) as e:
        raise ConversionError(
            f"File is not a valid HWP 5.x OLE document: {source.name}"
        ) from e
    try:
        char_shapes = _read_char_shapes(ole, source)
        metadata = _extract_metadata_hwp5(ole, source) if with_metadata else DocumentMetadata()
        section_streams = sorted(
            name for name in ole.listdir(streams=True, storages=False)
            if name[0] == "BodyText" and name[-1].startswith("Section")
        )
        if not section_streams:
            raise ConversionError(
                f"No BodyText/Section* streams found in {source.name}"
            )
        all_paragraphs: List[Hwp5Paragraph] = []
        for stream_name in section_streams:
            with ole.openstream(stream_name) as s:
                raw = s.read()
            decompressed = _decompress_section(raw)
            records = list(_iter_records(decompressed))
            all_paragraphs.extend(_SectionParser(records, char_shapes).parse())
        bindata_files: List[Path] = []
        if image_mode == "link" and image_dir is not None:
            bindata_files = _extract_bindata(ole, image_dir)
    finally:
        ole.close()
    md_parts: List[str] = []
    for para in all_paragraphs:
        md = _paragraph_to_markdown(para)
        if md:
            md_parts.append(md)
    if image_mode == "link" and image_dir is not None and bindata_files:
        rel_dir = image_dir.name
        md_parts.append(f"![image]({rel_dir}/{bindata_files[0].name})")
    body = "\n\n".join(md_parts)
    if with_metadata and not metadata.is_empty():
        return prepend_frontmatter(body, metadata)
    return body


def extract_metadata_hwp5(source: Path) -> DocumentMetadata:
    """Read only the DocInfo metadata without rendering the body."""
    if not source.is_file():
        raise FileNotFoundError(f"HWP file not found: {source}")
    _check_encryption(source)
    olefile = _read_olefile()
    source_str = str(source)
    if not olefile.isOleFile(source_str):
        raise ConversionError(
            f"File is not an OLE compound document: {source.name}"
        )
    try:
        ole = olefile.OleFileIO(source_str)
    except (olefile.olefile.NotOleFileError, ValueError, OSError) as e:
        raise ConversionError(
            f"File is not a valid HWP 5.x OLE document: {source.name}"
        ) from e
    try:
        return _extract_metadata_hwp5(ole, source)
    finally:
        ole.close()
