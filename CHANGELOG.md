# Changelog

All notable changes to hwp2md are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Character formatting fidelity (bold/italic/color preserved as inline markdown in HWP 5.x)
- HWP 5.x table and image extraction (currently text-only)
- Footnotes, headers, footers, captions
- GitHub Action wrapper (`uses: sigco3111/hwp2md@v1`)
- Metadata frontmatter (작성자/날짜/키워드)
- Streaming/chunked conversion for very large files

## [0.2.0] - 2026-06-08

### Added
- **HWPX parser** — full implementation using stdlib `zipfile` + `xml.etree`.
  - Paragraphs, headings (outline levels clamped to 1-6), bold/italic runs
  - GFM tables (rows / cells, with header row inferred)
  - Image handling with three modes:
    - `link` (default) — extracts `BinData/*` to a sidecar directory and emits
      `![alt](image_dir/filename)` references
    - `embed` — inlines images as `data:` URIs
    - `skip` — omits images
  - Encryption detection: raises `EncryptedDocumentError` when the root
    `mimetype` does not match `application/hwp+zip`
- **HWP 5.x parser** — basic text extraction.
  - Opens OLE compound document via `olefile` (optional dep)
  - Detects encrypted files (WIRE / `0xC2BC6B9B` signatures) and raises
    `EncryptedDocumentError`
  - Decompresses zlib-wrapped section streams
  - Walks tag-based record structure, extracts `HWPTAG_PARA_TEXT` (UTF-16LE)
  - Preserves line breaks, tabs; strips control characters
- **Public API extension**: `convert()` and `batch_convert()` now accept
  `image_mode` (`"embed"` / `"link"` / `"skip"`) and `image_dir` parameters
- **CLI**: `--images {embed,link,skip}` flag wired through to the API
- **Synthetic HWPX fixture builder** for tests (`tests/fixtures/hwpx_builder.py`)
- **40 tests** across CLI, HWPX, and HWP 5.x (up from 6)

### Notes
- HWP 5.x still lacks image and table extraction (deferred to 0.3.0)
- HWPX namespace coverage is the HWPML 2011/2016 set; older variants may
  need namespace shims

## [0.1.0] - 2026-06-08

### Added
- Project skeleton (package layout, pyproject.toml, CLI entry point)
- Public Python API: `convert()`, `batch_convert()`
- CLI: `hwp2md input.hwp -o output.md` and directory mode
- Exception hierarchy: `Hwp2mdError`, `UnsupportedFormatError`, `ConversionError`, `EncryptedDocumentError`
- Backend stubs for HWPX and HWP 5.x (raise `NotImplementedError`-style `ConversionError` until 0.2.0)
- Smoke tests covering version, missing files, unsupported extensions, batch skip behavior
- README with installation, quickstart, supported formats, roadmap, contributing
- MIT License
- `.gitignore` for Python + project artifacts
