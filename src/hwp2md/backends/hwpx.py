"""HWPX (XML-based, Hancom Office 2014+) conversion backend.

This is a stub for 0.1.0. The full implementation will:
- Unzip the HWPX (which is a ZIP container)
- Parse section0.xml, header.xml, etc.
- Walk the body tree, emitting GFM
- Extract embedded images to a sidecar directory

For 0.1.0 we provide only the dispatch + clear NotImplementedError so the
project skeleton is importable and the CLI exits gracefully.
"""

from __future__ import annotations

from pathlib import Path

from hwp2md.exceptions import ConversionError, UnsupportedFormatError


def convert_hwpx(source: Path, *, encoding: str = "utf-8") -> str:
    """Convert a .hwpx file to markdown.

    Args:
        source: Path to the .hwpx file.
        encoding: Output text encoding (default: utf-8).

    Returns:
        Markdown text.

    Raises:
        ConversionError: If the file cannot be parsed.
        UnsupportedFormatError: If the file is not a valid HWPX archive.
    """
    if not source.is_file():
        raise FileNotFoundError(f"HWPX file not found: {source}")

    # TODO(0.1.0 → 0.2.0): implement XML walker.
    # Skeleton intentionally raises to make the unimplemented path explicit
    # during early development. Will be replaced by a real parser.
    raise ConversionError(
        f"HWPX parser not yet implemented (planned for 0.2.0). "
        f"File: {source.name}"
    )
