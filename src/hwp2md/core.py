"""Core conversion logic for hwp2md.

This module provides the public API for converting HWP/HWPX files to Markdown.
The actual parsing is delegated to format-specific backends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Union

from hwp2md.exceptions import (
    ConversionError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)

PathLike = Union[str, Path]


def convert(source: PathLike, *, encoding: str = "utf-8") -> str:
    """Convert a single HWP/HWPX file to a Markdown string.

    Args:
        source: Path to the .hwp or .hwpx file.
        encoding: Output encoding for the markdown text (default: utf-8).

    Returns:
        Markdown text representation of the document.

    Raises:
        FileNotFoundError: If the source file does not exist.
        UnsupportedFormatError: If the file extension is not recognized.
        EncryptedDocumentError: If the document is password-protected.
        ConversionError: For any other conversion failure.
    """
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(f"Input file not found: {src}")

    suffix = src.suffix.lower()
    if suffix == ".hwpx":
        from hwp2md.backends.hwpx import convert_hwpx
        return convert_hwpx(src, encoding=encoding)
    elif suffix == ".hwp":
        from hwp2md.backends.hwp5 import convert_hwp5
        return convert_hwp5(src, encoding=encoding)
    else:
        raise UnsupportedFormatError(
            f"Unsupported file extension '{suffix}'. "
            "Supported: .hwp (HWP 5.x), .hwpx (HWPX)"
        )


def batch_convert(
    source_dir: PathLike,
    output_dir: PathLike,
    *,
    encoding: str = "utf-8",
    recursive: bool = True,
) -> Iterator[tuple[Path, Path]]:
    """Recursively convert all HWP/HWPX files in a directory.

    Args:
        source_dir: Root directory containing HWP files.
        output_dir: Destination directory for markdown files.
        encoding: Output encoding (default: utf-8).
        recursive: Whether to walk subdirectories (default: True).

    Yields:
        Tuples of (source_path, output_path) for each converted file.

    Example:
        >>> for src, dst in batch_convert("./docs/", "./out/"):
        ...     print(f"{src.name} -> {dst}")
    """
    src_root = Path(source_dir)
    dst_root = Path(output_dir)
    dst_root.mkdir(parents=True, exist_ok=True)

    pattern = "**/*" if recursive else "*"
    for src_path in sorted(src_root.glob(pattern)):
        if not src_path.is_file():
            continue
        if src_path.suffix.lower() not in {".hwp", ".hwpx"}:
            continue
        rel = src_path.relative_to(src_root)
        dst_path = dst_root / rel.with_suffix(".md")
        dst_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            md_text = convert(src_path, encoding=encoding)
            dst_path.write_text(md_text, encoding=encoding)
            yield src_path, dst_path
        except (ConversionError, UnsupportedFormatError, EncryptedDocumentError) as e:
            # Log to stderr in CLI; for library users, propagate via yield with None
            # TODO: consider returning a Result tuple in 1.0
            raise
