# Changelog

All notable changes to hwp2md are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Footnotes, headers, footers, captions
- Metadata frontmatter (작성자/날짜/키워드)
- Streaming/chunked conversion for very large files
- Inline image position recovery for HWP 5.x (currently extracts
  BinData/* but cannot place images inside paragraphs)
- PyPI publication (currently `pip install git+...` only)

## [0.4.0] - 2026-06-08

### Added
- **GitHub Action** (`action.yml`) — composite action that wraps the
  hwp2md CLI. Six inputs (`input`, `output`, `encoding`,
  `image-mode`, `install-extras`, `working-directory`) and two
  outputs (`output-path`, `files-count`). Use as
  `sigco3111/hwp2md@v1` in any workflow.
- **CI workflow** (`.github/workflows/ci.yml`) — runs pytest on
  Python 3.9–3.13 across all push and pull_request events, plus
  yamllint and an `action.yml` schema check.
- **Release workflow** (`.github/workflows/release.yml`) —
  builds sdist + wheel on `v*` tag push and attaches them to a
  GitHub Release with auto-generated notes.
- **`.yamllint.yaml`** — local config (line-length 120, GitHub
  Actions friendliness for `on:` keys, document-start disabled).
- **README** — new "GitHub Action" section with input/output
  tables and usage examples.

### Notes
- The release workflow uses `softprops/action-gh-release@v2` and
  `actions/setup-python@v5`; both are pinned to a major version.
  PyPI publish is not wired in this release — see Unreleased.

## [0.3.0] - 2026-06-08

### Added
- **HWP 5.x table extraction** — HWPTAG_TABLE records now produce
  GFM tables, with cells laid out by row/column count read from
  the table record header. Multi-paragraph cells are joined with
  newlines.
- **HWP 5.x character formatting** — HWPTAG_PARA_CHAR_SHAPE
  position slots are joined with HWPTAG_CHAR_SHAPE definitions
  (read from the DocInfo stream) to apply bold, italic,
  underline, and strikethrough as inline markdown. Works at both
  paragraph and table-cell level.
- **HWP 5.x image extraction** — BinData/* streams are extracted
  to the ``image_dir`` when ``image_mode="link"`` and a reference
  to the first image is appended to the markdown output. Inline
  position recovery remains a known gap (see Unreleased).
- New ``CharShape``, ``Hwp5Run``, ``Hwp5Paragraph`` dataclasses
  in the HWP 5.x backend to model the level-based record tree.

### Changed
- HWP 5.x parser refactored from a flat record walker to a
  level-based section parser (``_SectionParser``) so that
  control records (tables, inline marks) and their children can
  be grouped correctly.

### Notes
- Bold/italic detection depends on the HWP 5.x version's CHAR_SHAPE
  payload layout (offsets 7/8/9/10). Versions that diverge from
  the 5.0 (34-byte) / 5.1 (38-byte) layout will be parsed as
  unstyled.
- Tests: 51 passing (15 HWPX + 28 HWP 5.x + 6 CLI smoke + 2 misc)

## [0.2.0] - 2026-06-08

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
