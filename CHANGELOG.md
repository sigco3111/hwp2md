# Changelog

All notable changes to hwp2md are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- HWPX (XML) parser implementation
- HWP 5.x (OLE) parser implementation
- Image extraction (embed/link/skip modes)
- Table conversion to GFM
- GitHub Action wrapper

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
