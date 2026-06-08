"""HWP 5.x (legacy OLE container) conversion backend.

This is a stub for 0.1.0. The full implementation will:
- Open the file as an OLE compound document (via `olefile`)
- Locate the `BodyText/Section0` stream
- Parse the binary record tree (HWP tag-based format)
- Walk paragraphs/tables, emitting GFM
- Extract BinData images to sidecar directory

Requires the optional `olefile` dependency (`pip install hwp2md[olefile]`).
"""

from __future__ import annotations

from pathlib import Path

from hwp2md.exceptions import ConversionError, UnsupportedFormatError


def convert_hwp5(source: Path, *, encoding: str = "utf-8") -> str:
    """Convert a .hwp (HWP 5.x) file to markdown.

    Args:
        source: Path to the .hwp file.
        encoding: Output text encoding (default: utf-8).

    Returns:
        Markdown text.

    Raises:
        ConversionError: If parsing fails or the optional `olefile` dep is missing.
    """
    if not source.is_file():
        raise FileNotFoundError(f"HWP file not found: {source}")

    try:
        import olefile  # type: ignore  # noqa: F401
    except ImportError as e:
        raise ConversionError(
            "HWP 5.x parsing requires the `olefile` optional dependency. "
            "Install with: pip install \"hwp2md[olefile]\""
        ) from e

    # TODO(0.2.0): implement OLE walker and binary record parser.
    raise ConversionError(
        f"HWP 5.x parser not yet implemented (planned for 0.2.0). "
        f"File: {source.name}"
    )
