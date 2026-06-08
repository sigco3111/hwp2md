"""Core conversion logic for hwp2md.

This module provides the public API for converting HWP/HWPX files to Markdown.
The actual parsing is delegated to format-specific backends.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator, Literal, Optional, Union

from hwp2md.exceptions import (
    ConversionError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)

PathLike = Union[str, Path]
ImageMode = Literal["embed", "link", "skip"]


def convert(
    source: PathLike,
    *,
    encoding: str = "utf-8",
    image_mode: ImageMode = "link",
    image_dir: Optional[PathLike] = None,
) -> str:
    """Convert a single HWP/HWPX file to a Markdown string.

    Args:
        source: Path to the .hwp or .hwpx file.
        encoding: Output encoding for the markdown text (default: utf-8).
        image_mode:
            - ``"link"`` (default): extract embedded images to a sidecar
              directory and emit ``![alt](relative/path)`` references.
            - ``"embed"``: inline images as base64 ``data:`` URIs.
            - ``"skip"``: omit images entirely.
        image_dir:
            Directory used for image extraction when ``image_mode="link"``.
            If ``None`` (default), a sibling directory ``<stem>_images`` is
            created next to the markdown output.

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

        return convert_hwpx(
            src,
            encoding=encoding,
            image_mode=image_mode,
            image_dir=Path(image_dir) if image_dir is not None else None,
        )
    elif suffix == ".hwp":
        from hwp2md.backends.hwp5 import convert_hwp5

        return convert_hwp5(
            src,
            encoding=encoding,
            image_mode=image_mode,
            image_dir=Path(image_dir) if image_dir is not None else None,
        )
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
    image_mode: ImageMode = "link",
) -> Iterator[tuple[Path, Path]]:
    """Recursively convert all HWP/HWPX files in a directory.

    Args:
        source_dir: Root directory containing HWP files.
        output_dir: Destination directory for markdown files.
        encoding: Output encoding (default: utf-8).
        recursive: Whether to walk subdirectories (default: True).
        image_mode: How to handle embedded images (see :func:`convert`).

    Yields:
        Tuples of (source_path, output_path) for each converted file.
        Note: if a file fails to convert, the underlying exception
        (a subclass of :class:`Hwp2mdError`) is propagated to the caller.
        For library users, wrap the call in ``try/except`` if partial
        success is acceptable.

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
        image_dir = dst_path.parent / f"{dst_path.stem}_images"
        md_text = convert(
            src_path,
            encoding=encoding,
            image_mode=image_mode,
            image_dir=image_dir,
        )
        dst_path.write_text(md_text, encoding=encoding)
        yield src_path, dst_path
