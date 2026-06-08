"""Document metadata extraction and YAML frontmatter rendering.

HWP and HWPX documents carry header information (title, author,
dates, keywords) that is useful for RAG indexing and search. This
module defines a common :class:`DocumentMetadata` shape and
renders it as a Jekyll/Hugo-compatible YAML frontmatter block.

Rendering uses a small hand-rolled serializer rather than a
YAML dependency so the project keeps its zero-deps posture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional


@dataclass
class DocumentMetadata:
    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    date: Optional[date] = None
    last_modified: Optional[date] = None
    keywords: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any([
            self.title, self.author, self.subject,
            self.date, self.last_modified, self.keywords,
        ])

    def to_pairs(self) -> List[tuple]:
        pairs: List[tuple] = []
        if self.title:
            pairs.append(("title", self.title))
        if self.author:
            pairs.append(("author", self.author))
        if self.subject:
            pairs.append(("subject", self.subject))
        if self.date:
            pairs.append(("date", self.date.isoformat()))
        if self.last_modified:
            pairs.append(("last_modified", self.last_modified.isoformat()))
        if self.keywords:
            pairs.append(("keywords", list(self.keywords)))
        return pairs


def _yaml_escape(value: str) -> str:
    """Quote a string only when YAML would otherwise misinterpret it."""
    if value == "":
        return '""'
    safe = all(ch.isalnum() or ch in " _-./" for ch in value)
    if not safe or value.lower() in {"yes", "no", "true", "false", "null", "~"}:
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def render_frontmatter(metadata: DocumentMetadata) -> str:
    """Return a YAML frontmatter block, or empty string if no fields set."""
    pairs = metadata.to_pairs()
    if not pairs:
        return ""
    lines = ["---"]
    for key, value in pairs:
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_yaml_escape(item)}")
        else:
            lines.append(f"{key}: {_yaml_escape(str(value))}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines) + "\n"


def prepend_frontmatter(markdown: str, metadata: DocumentMetadata) -> str:
    fm = render_frontmatter(metadata)
    if not fm:
        return markdown
    return fm + markdown


def parse_iso_date(value: str) -> Optional[date]:
    """Best-effort ISO 8601 date parser for header dates."""
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parse_packed_hwp_date(payload: bytes, offset: int) -> Optional[date]:
    """Decode the 4-byte HWP 5.x date layout at ``payload[offset:]``.

    The bit layout is: bits 0-7 day, bits 8-15 month, bits 16-31
    year (offset from 1900). Some writers use the year directly
    (no offset); we accept both by clamping to a sane range.
    """
    if len(payload) < offset + 4:
        return None
    value = int.from_bytes(payload[offset : offset + 4], "little")
    day = value & 0xFF
    month = (value >> 8) & 0xFF
    year_field = (value >> 16) & 0xFFFF
    if year_field < 1900:
        year = 1900 + year_field
    else:
        year = year_field
    if not (1900 <= year <= 2999 and 1 <= month <= 12 and 1 <= day <= 31):
        return None
    try:
        return date(year, month, day)
    except ValueError:
        return None
