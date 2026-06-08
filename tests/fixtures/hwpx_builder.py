"""Synthetic HWPX fixture builder for tests.

Builds a minimal-but-valid HWPX archive in-memory from high-level
declarations. The output mimics what Hancom Office emits, using
the HWPML 2011 paragraph namespace set, so the parser can be
exercised without external sample files.
"""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

NS_HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
NS_HS = "http://www.hancom.co.kr/hwpml/2011/section"
NS_HC = "http://www.hancom.co.kr/hwpml/2010/common"

XML_DECL = '<?xml version="1.0" encoding="UTF-8"?>'

ROOT_OPEN = (
    f'{XML_DECL}\n'
    f'<hs:sec xmlns:hs="{NS_HS}" '
    f'xmlns:hp="{NS_HP}" '
    f'xmlns:hc="{NS_HC}">'
)
ROOT_CLOSE = "</hs:sec>"


@dataclass
class Run:
    text: str
    bold: bool = False
    italic: bool = False


@dataclass
class Paragraph:
    runs: List[Run] = field(default_factory=list)
    outline: int = 0
    images: List[Tuple[str, str]] = field(default_factory=list)


@dataclass
class Table:
    rows: List[List[str]] = field(default_factory=list)


@dataclass
class HwpxDocument:
    paragraphs: List[Paragraph] = field(default_factory=list)
    tables: List[Table] = field(default_factory=list)
    bindata: Dict[str, bytes] = field(default_factory=dict)

    def add_para(
        self,
        text: str = "",
        *,
        bold: bool = False,
        italic: bool = False,
        outline: int = 0,
        images: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        runs: List[Run] = []
        if text:
            runs.append(Run(text=text, bold=bold, italic=italic))
        self.paragraphs.append(
            Paragraph(
                runs=runs,
                outline=outline,
                images=images or [],
            )
        )

    def add_table(self, rows: List[List[str]]) -> None:
        self.tables.append(Table(rows=rows))

    def add_image(self, logical_name: str, png_bytes: bytes) -> None:
        self.bindata[logical_name] = png_bytes


def _render_paragraph(p: Paragraph) -> str:
    parts: List[str] = ["<hp:p>"]
    if p.outline > 0 or any(p.images):
        parts.append("<hp:pPr>")
        if p.outline > 0:
            parts.append(
                f'<hp:outline level="{min(p.outline, 6)}"/>'
            )
        parts.append("</hp:pPr>")
    for run in p.runs:
        rpr_inner = ""
        if run.bold or run.italic:
            rpr_inner += "<hp:rPr>"
            if run.bold:
                rpr_inner += "<hp:bold/>"
            if run.italic:
                rpr_inner += "<hp:italic/>"
            rpr_inner += "</hp:rPr>"
        body = _xml_escape(run.text)
        parts.append(
            f"<hp:run>{rpr_inner}<hp:t>{body}</hp:t></hp:run>"
        )
    for logical_id, arc_path in p.images:
        parts.append(
            "<hp:ctrl>"
            "<hp:pic>"
            f'<hp:binData binaryItemIDRef="{_xml_escape(arc_path)}"/>'
            "</hp:pic>"
            "</hp:ctrl>"
        )
    parts.append("</hp:p>")
    return "".join(parts)


def _render_table(t: Table) -> str:
    parts: List[str] = ["<hp:tbl>"]
    for row in t.rows:
        parts.append("<hp:tr>")
        for cell in row:
            parts.append(
                "<hp:tc>"
                "<hp:p>"
                f"<hp:run><hp:t>{_xml_escape(cell)}</hp:t></hp:run>"
                "</hp:p>"
                "</hp:tc>"
            )
        parts.append("</hp:tr>")
    parts.append("</hp:tbl>")
    return "".join(parts)


def _xml_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def render_section_xml(doc: HwpxDocument) -> str:
    body_parts: List[str] = []
    for p in doc.paragraphs:
        body_parts.append(_render_paragraph(p))
    for t in doc.tables:
        body_parts.append(_render_table(t))
    body = "".join(body_parts)
    return f"{ROOT_OPEN}<hs:body>{body}</hs:body>{ROOT_CLOSE}"


def render_header_xml() -> str:
    return (
        f"{XML_DECL}\n"
        f'<hc:header xmlns:hc="{NS_HC}">'
        "<hc:docInfo>"
        "<hc:title>Test</hc:title>"
        "</hc:docInfo>"
        "</hc:header>"
    )


def build_hwpx_bytes(
    doc: HwpxDocument,
    *,
    mimetype: str = "application/hwp+zip",
) -> bytes:
    """Serialize the document into a complete HWPX archive (bytes)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        info = zipfile.ZipInfo("mimetype")
        info.compress_type = zipfile.ZIP_STORED
        zf.writestr(info, mimetype.encode("ascii"))
        zf.writestr("Contents/header.xml", render_header_xml())
        zf.writestr("Contents/section0.xml", render_section_xml(doc))
        for name, data in doc.bindata.items():
            zf.writestr(f"BinData/{name}", data)
    return buf.getvalue()
