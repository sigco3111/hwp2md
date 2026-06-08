# hwp2md Public API Contract

This document defines the **stable public API** of hwp2md as of v1.0.0.
Anything not listed here is **internal** and may change in any release.

## Stability promise

Starting with v1.0.0, the public API follows [Semantic Versioning](https://semver.org/):

- **Patch releases (1.0.x)**: only bug fixes, performance, and
  documentation. No signature changes. No new required parameters.
- **Minor releases (1.x.0)**: additive changes only. New optional
  parameters, new functions, new exception subclasses.
- **Major releases (2.0.0)**: breaking changes allowed, with a
  deprecation period in the previous major.

Deprecated APIs go through at least one minor release with a
`DeprecationWarning` before removal.

## Stable surface (v1.0.0)

### Top-level (`hwp2md`)

| Symbol | Kind | Since | Notes |
|---|---|---|---|
| `convert` | function | 0.1.0 | Single file → markdown string |
| `batch_convert` | function | 0.1.0 | Generator yielding `(src, dst)` |
| `ImageMode` | type alias | 0.2.0 | `"embed" \| "link" \| "skip"` |
| `Hwp2mdError` | exception | 0.1.0 | Base class |
| `UnsupportedFormatError` | exception | 0.1.0 | Subclass of `Hwp2mdError` |
| `ConversionError` | exception | 0.1.0 | Subclass of `Hwp2mdError` |
| `EncryptedDocumentError` | exception | 0.1.0 | Subclass of `ConversionError` |
| `__version__` | string | 0.1.0 | PEP 440 version string |

### Stable per-backend entry points

These are documented in their module docstrings and considered
public for advanced users. They will not change signatures in
1.x without a deprecation cycle.

| Symbol | Module | Notes |
|---|---|---|
| `convert_hwpx` | `hwp2md.backends.hwpx` | Single HWPX file → markdown |
| `extract_metadata_hwpx` | `hwp2md.backends.hwpx` | Read-only metadata access |
| `convert_hwp5` | `hwp2md.backends.hwp5` | Single HWP 5.x file → markdown |
| `extract_metadata_hwp5` | `hwp2md.backends.hwp5` | Read-only metadata access |

## Internal surface (no stability guarantee)

The following are implementation details and may change without
notice:

- `hwp2md._markdown` — internal GFM table builder, image helper,
  inline-text sanitizer. The behavior (output format) is stable,
  but the function signatures and module structure are not.
- `hwp2md.metadata` — `DocumentMetadata` dataclass and the
  `render_frontmatter` / `prepend_frontmatter` helpers. The
  *output format* (YAML frontmatter shape) is stable; the
  internal API may change.
- `hwp2md.backends.hwpx._HwpxParser`, `hwp2md.backends.hwp5._SectionParser`
  and friends — internal record walkers, not part of the
  public API.
- Anything prefixed with `_`.

## Versioning policy

The project follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
strictly from v1.0.0 onward. The pre-1.0 versions (0.1.0 through
0.5.0) were considered "alpha" and not held to the same contract
in retrospect.

A `1.0.0` release is also a freeze on Python support: the
minimum supported version is **Python 3.9** (set in
`pyproject.toml`). Older Python versions are not supported.

## Adding new public API

New public symbols must be:

1. Listed in `hwp2md.__all__` (or their module's `__all__`).
2. Covered by a docstring that includes Args/Returns/Raises (as
   relevant).
3. Covered by a test in `tests/`.
4. Documented here, in this file.
5. Added to the [CHANGELOG](../CHANGELOG.md) under "Added".

A PR that adds a new public symbol without these steps will be
asked to update them before merge.

## Deprecating existing public API

1. Add a `DeprecationWarning` at every call site in the public
   surface (e.g. a `warnings.warn` at the function entry).
2. Document the deprecation in the docstring with a
   ".. deprecated::" note.
3. Add a "Deprecated" entry to the [CHANGELOG](../CHANGELOG.md).
4. The function stays for at least one minor release (3 months
   minimum) before removal in the next major.

## Exceptions

The exception hierarchy is part of the stable surface because
callers are expected to catch them. New subclasses may be added
in minor releases. The base class of an existing exception is
**not** allowed to change in a minor release.

```text
Hwp2mdError
├── UnsupportedFormatError
└── ConversionError
    └── EncryptedDocumentError
```

`EncryptedDocumentError` is a subclass of `ConversionError` for
historical reasons; callers that catch `ConversionError` already
catch it. Code that needs to specifically detect encrypted input
should catch `EncryptedDocumentError` first.
