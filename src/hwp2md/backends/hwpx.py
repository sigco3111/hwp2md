"""HWPX (XML-based, Hancom Office 2014+) conversion backend.

HWPX is a ZIP container with sections stored as XML. We extract
``Contents/section*.xml`` in order and walk paragraphs, emitting
GitHub-Flavored Markdown.

This implementation targets the HWPML 2011/2016 namespace set used
by mainstream HWPX producers (Hancom Office 2014+). It is intentionally
narrow: paragraphs, headings, basic tables, and images only. Headers,
footers, footnotes, and shape effects are deferred to a later release.
"""

from __future__ import annotations

import base64
import mimetypes
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from hwp2md._markdown import (
    gfm_table,
    sanitize_inline,
    slugify_alt_text,
)
from hwp2md.exceptions import ConversionError, EncryptedDocumentError

HWPX_MIMETYPE = "application/hwp+zip"


def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_direct(parent: ET.Element, name: str) -> Optional[ET.Element]:
    for child in list(parent):
        if _local(child.tag) == name:
            return child
    return None


def _find_all_direct(parent: ET.Element, name: str) -> List[ET.Element]:
    return [c for c in list(parent) if _local(c.tag) == name]


def _iter_sections(zf: zipfile.ZipFile) -> List[str]:
    names = [
        n for n in zf.namelist()
        if n.startswith("Contents/section") and n.endswith(".xml")
    ]
    names.sort(key=lambda n: int(_section_index(n)))
    return names


def _section_index(name: str) -> str:
    base = name.rsplit("/", 1)[-1]
    digits = "".join(ch for ch in base if ch.isdigit())
    return digits or "0"


def _detect_encryption(zf: zipfile.ZipFile) -> None:
    try:
        mimetype = zf.read("mimetype").decode("ascii", errors="replace").strip()
    except KeyError as e:
        raise ConversionError("Invalid HWPX: missing root 'mimetype' file") from e
    if mimetype != HWPX_MIMETYPE:
        raise EncryptedDocumentError(
            f"Document does not declare HWPX mimetype (got {mimetype!r}). "
            "It may be encrypted or corrupt."
        )


class _HwpxParser:
    def __init__(
        self,
        source: Path,
        *,
        encoding: str,
        image_mode: str,
        image_dir: Optional[Path],
    ) -> None:
        self.source = source
        self.encoding = encoding
        self.image_mode = image_mode
        self.image_dir = image_dir
        self._image_refs: List[Tuple[str, str, str]] = []
        self._seen_arc_paths: Dict[str, str] = {}
        self._extracted: Dict[str, Path] = {}

    def convert(self) -> str:
        try:
            zf = zipfile.ZipFile(self.source, "r")
        except zipfile.BadZipFile as e:
            raise ConversionError(
                f"Not a valid HWPX archive: {self.source.name} ({e})"
            ) from e
        with zf:
            _detect_encryption(zf)
            section_names = _iter_sections(zf)
            if not section_names:
                raise ConversionError("HWPX has no Contents/section*.xml")
            md_parts: List[str] = []
            for name in section_names:
                xml_bytes = zf.read(name)
                try:
                    root = ET.fromstring(xml_bytes)
                except ET.ParseError as e:
                    raise ConversionError(
                        f"Malformed XML in {name}: {e}"
                    ) from e
                md_parts.append(self._render_section(root, zf))
            self._extracted = self._resolve_image_refs(zf)
        md_text = "\n\n".join(p for p in md_parts if p.strip())
        if self.image_mode == "link" and self._extracted:
            md_text = self._substitute_link_placeholders(md_text)
        return md_text

    def _resolve_image_refs(
        self, zf: zipfile.ZipFile
    ) -> Dict[str, Path]:
        if self.image_mode == "skip" or not self._image_refs:
            return {}
        if self.image_dir is None:
            self.image_dir = self.source.with_suffix("").parent / (
                self.source.stem + "_images"
            )
        self.image_dir.mkdir(parents=True, exist_ok=True)
        out: Dict[str, Path] = {}
        for placeholder, arc_path, _alt in self._image_refs:
            if placeholder in out:
                continue
            try:
                data = zf.read(arc_path)
            except KeyError:
                continue
            ext = Path(arc_path).suffix.lstrip(".").lower() or "bin"
            out_path = self.image_dir / f"{placeholder}.{ext}"
            out_path.write_bytes(data)
            out[placeholder] = out_path
        return out

    def _record_image_ref(self, arc_path: str) -> Tuple[str, str]:
        if arc_path in self._seen_arc_paths:
            return self._seen_arc_paths[arc_path], arc_path
        placeholder = f"img{len(self._image_refs) + 1:03d}"
        self._seen_arc_paths[arc_path] = placeholder
        self._image_refs.append((placeholder, arc_path, ""))
        return placeholder, arc_path

    def _substitute_link_placeholders(self, md_text: str) -> str:
        pattern = re.compile(r"!\[[^\]]*\]\((img\d{3,})\)")
        image_dir = self.image_dir
        if image_dir is None:
            return md_text
        dir_name = image_dir.name

        def _replace(match: re.Match) -> str:
            placeholder = match.group(1)
            file_path = self._extracted.get(placeholder)
            if file_path is None:
                return match.group(0)
            return f"![{file_path.stem}]({dir_name}/{file_path.name})"

        return pattern.sub(_replace, md_text)

    def _render_section(
        self, root: ET.Element, zf: zipfile.ZipFile
    ) -> str:
        if _local(root.tag) == "sec":
            body = _find_direct(root, "body")
        else:
            body = root
        if body is None:
            return ""
        out: List[str] = []
        for child in list(body):
            lname = _local(child.tag)
            if lname == "p":
                rendered = self._render_paragraph(child, zf)
                if rendered:
                    out.append(rendered)
            elif lname in {"tbl", "table"}:
                rendered = self._render_table(child, zf)
                if rendered:
                    out.append(rendered)
        return "\n\n".join(out)

    def _render_paragraph(
        self, p: ET.Element, zf: zipfile.ZipFile
    ) -> str:
        ppr = _find_direct(p, "pPr")
        outline_level = 0
        if ppr is not None:
            ol = _find_direct(ppr, "outline")
            if ol is not None:
                try:
                    outline_level = int(ol.attrib.get("level", "0"))
                except ValueError:
                    outline_level = 0
        runs_text: List[str] = []
        for child in list(p):
            lname = _local(child.tag)
            if lname == "run":
                runs_text.append(self._render_run(child, zf))
            elif lname == "ctrl":
                ctrl_md = self._render_inline_ctrl(child, zf)
                if ctrl_md:
                    runs_text.append(ctrl_md)
        text = "".join(runs_text).strip()
        if not text:
            return ""
        if outline_level > 0:
            level = min(outline_level, 6)
            return ("#" * level) + " " + text
        return text

    def _render_run(self, run: ET.Element, zf: zipfile.ZipFile) -> str:
        rpr = _find_direct(run, "rPr")
        bold = rpr is not None and _find_direct(rpr, "bold") is not None
        italic = rpr is not None and _find_direct(rpr, "italic") is not None
        t = _find_direct(run, "t")
        text = sanitize_inline(t.text) if (t is not None and t.text) else ""
        if not text:
            return ""
        if bold and italic:
            return f"***{text}***"
        if bold:
            return f"**{text}**"
        if italic:
            return f"*{text}*"
        return text

    def _render_inline_ctrl(
        self, ctrl: ET.Element, zf: zipfile.ZipFile
    ) -> str:
        for child in list(ctrl):
            lname = _local(child.tag)
            if lname == "pic":
                return self._render_picture(child, zf)
            if lname in {"tbl", "table"}:
                return self._render_table(child, zf)
        return ""

    def _render_picture(self, pic: ET.Element, zf: zipfile.ZipFile) -> str:
        if self.image_mode == "skip":
            return ""
        bin = _find_direct(pic, "binData")
        if bin is None:
            return ""
        arc_path = (
            bin.attrib.get("binaryItemIDRef")
            or bin.attrib.get("path", "")
        )
        if not arc_path:
            return ""
        alt = slugify_alt_text(arc_path)
        if self.image_mode == "embed":
            try:
                data = zf.read(arc_path)
            except KeyError:
                return ""
            mime, _ = mimetypes.guess_type(arc_path)
            mime = mime or "application/octet-stream"
            b64 = base64.b64encode(data).decode("ascii")
            return f"![{alt}](data:{mime};base64,{b64})"
        placeholder, _ = self._record_image_ref(arc_path)
        return f"![{alt}]({placeholder})"

    def _render_table(self, tbl: ET.Element, zf: zipfile.ZipFile) -> str:
        rows: List[List[str]] = []
        for tr in _find_all_direct(tbl, "tr"):
            row: List[str] = []
            for tc in _find_all_direct(tr, "tc"):
                cell_parts: List[str] = []
                for sub in _find_all_direct(tc, "p"):
                    cell_parts.append(self._render_paragraph(sub, zf))
                for sub in _find_all_direct(tc, "tbl"):
                    cell_parts.append(self._render_table(sub, zf))
                row.append(" ".join(p for p in cell_parts if p).strip())
            if any(c for c in row):
                rows.append(row)
        return gfm_table(rows, header=True)


def convert_hwpx(
    source: Path,
    *,
    encoding: str = "utf-8",
    image_mode: str = "link",
    image_dir: Optional[Path] = None,
) -> str:
    """Convert a .hwpx file to markdown."""
    if not source.is_file():
        raise FileNotFoundError(f"HWPX file not found: {source}")
    if image_mode not in {"embed", "link", "skip"}:
        raise ConversionError(f"Invalid image_mode: {image_mode!r}")
    parser = _HwpxParser(
        source,
        encoding=encoding,
        image_mode=image_mode,
        image_dir=image_dir,
    )
    return parser.convert()
