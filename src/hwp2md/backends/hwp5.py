"""HWP 5.x (legacy OLE container) conversion backend.

HWP 5.x stores content in an OLE Compound Document with one
``BodyText/SectionN`` stream per section. Each stream is a
sequence of records, optionally zlib-compressed.

For 0.2.0 we extract paragraph text and basic structural cues.
Character formatting, tables, and images are deferred to 0.3.0.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Iterator, List, Tuple

from hwp2md._markdown import sanitize_inline
from hwp2md.exceptions import ConversionError, EncryptedDocumentError

HWP5_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")

PARA_HEADER = 66
PARA_TEXT = 67
TABLE_CELL = 69
LIST_HEADER = 73
SHAPE_COMPONENT = 81

PARA_CONTROL_NEW = 0x0000
PARA_CONTROL_LINE_BREAK = 0x000A
PARA_CONTROL_SOFT_BREAK = 0x000B
PARA_CONTROL_TAB = 0x0009
PARA_CONTROL_FIELDBEGIN = 0x0002
PARA_CONTROL_FIELDEND = 0x0003
PARA_CONTROL_UNKNOWN_EXT = 0x000C


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
    """Decompress a section stream if it has the compression flag set."""
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
    """Decode a HWPTAG_PARA_TEXT record body to a string.

    Text in 5.0+ is stored as UTF-16LE with inline 16-bit control
    characters (line breaks, tabs, field markers, etc.).
    """
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
            if i + 4 <= len(payload):
                chars.append(" ")
                continue
            chars.append(" ")
        elif 0x0020 <= code <= 0xFFFD and code not in (0xFEFF, 0xFFFE, 0xFFFF):
            try:
                chars.append(chr(code))
            except (ValueError, OverflowError):
                chars.append(" ")
        else:
            chars.append("")
    return "".join(chars)


def _paragraphs_from_section(data: bytes) -> List[str]:
    paragraphs: List[str] = []
    current: List[str] = []
    for tag, _level, payload in _iter_records(data):
        if tag == PARA_HEADER:
            if current:
                merged = "".join(current).strip()
                if merged:
                    paragraphs.append(sanitize_inline(merged))
                current = []
        elif tag == PARA_TEXT:
            current.append(_decode_para_text(payload))
    if current:
        merged = "".join(current).strip()
        if merged:
            paragraphs.append(sanitize_inline(merged))
    return paragraphs


def convert_hwp5(
    source: Path,
    *,
    encoding: str = "utf-8",
    image_mode: str = "skip",
    image_dir=None,
) -> str:
    """Convert a .hwp (HWP 5.x) file to markdown.

    For 0.2.0 the output is plain text paragraphs separated by blank
    lines. Image handling is a no-op for HWP 5.x and will be added
    in 0.3.0 alongside proper character formatting and tables.
    """
    del image_mode, image_dir
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
        section_streams = sorted(
            name for name in ole.listdir(streams=True, storages=False)
            if name[0] == "BodyText" and name[-1].startswith("Section")
        )
        if not section_streams:
            raise ConversionError(
                f"No BodyText/Section* streams found in {source.name}"
            )
        all_paragraphs: List[str] = []
        for stream_name in section_streams:
            with ole.openstream(stream_name) as s:
                raw = s.read()
            decompressed = _decompress_section(raw)
            all_paragraphs.extend(_paragraphs_from_section(decompressed))
    finally:
        ole.close()
    if not all_paragraphs:
        return ""
    return "\n\n".join(all_paragraphs)
