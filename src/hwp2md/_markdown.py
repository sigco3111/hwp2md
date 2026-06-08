"""Shared markdown conversion helpers for hwp2md backends."""

from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from typing import List, Optional

from hwp2md.exceptions import ConversionError

_INLINE_INVALID = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]")


def sanitize_inline(text: str) -> str:
    return _INLINE_INVALID.sub("", text)


def slugify_alt_text(text: str, max_len: int = 64) -> str:
    cleaned = sanitize_inline(text).strip()
    if not cleaned:
        return "image"
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:max_len]


def image_markdown_for_link(image_path: Path, rel_to: Path, alt: str) -> str:
    try:
        if rel_to.is_absolute():
            rel = Path(image_path).resolve().relative_to(Path(rel_to).resolve())
        else:
            rel = image_path
    except ValueError:
        rel = Path(image_path.name)
    return f"![{alt}]({Path(rel).as_posix()})"


def image_markdown_for_embed(image_path: Path, alt: str) -> str:
    mime, _ = mimetypes.guess_type(image_path.name)
    mime = mime or "application/octet-stream"
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"![{alt}](data:{mime};base64,{data})"


def gfm_table(rows: List[List[str]], header: bool = True) -> str:
    """Format a 2D list of strings as a GFM table.

    Empty rows are dropped, missing cells are padded with empty strings,
    and pipes/newlines inside cells are escaped/sanitized to keep the
    table well-formed.
    """
    rows = [r for r in rows if r]
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]

    def _cell(v: str) -> str:
        v = sanitize_inline(v)
        v = v.replace("|", "\\|")
        v = v.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
        return v.strip()

    out: List[str] = []
    out.append("| " + " | ".join(_cell(c) for c in rows[0]) + " |")
    out.append("| " + " | ".join(["---"] * ncols) + " |")
    body = rows[1:] if header and len(rows) > 1 else rows
    for r in body:
        out.append("| " + " | ".join(_cell(c) for c in r) + " |")
    return "\n".join(out)


def normalize_image_path(raw: str, base: Path) -> Path:
    p = (base / raw).resolve()
    if not p.exists():
        raise ConversionError(f"Image referenced but not found in archive: {raw}")
    return p


def resolve_image_dir(
    image_dir: Optional[Path],
    fallback: Path,
) -> Path:
    if image_dir is None:
        return fallback
    return Path(image_dir)
