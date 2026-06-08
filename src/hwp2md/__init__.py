"""hwp2md - Convert Korean HWP (한글) files to clean Markdown.

Offline-first, LLM RAG-friendly, zero-dependency core.

The public, stable API (see ``docs/API.md`` for the contract):

- :func:`convert` — single file → markdown string
- :func:`batch_convert` — directory walker that yields ``(src, dst)``
- :class:`ImageMode` — typing alias for ``"embed" | "link" | "skip"``
- :class:`Hwp2mdError` (and subclasses) — exception hierarchy
- :data:`__version__` — package version string

Anything not listed in ``__all__`` (including ``hwp2md._markdown``,
``hwp2md.metadata``, ``hwp2md.backends.*``) is internal and may
change in a patch release. The two ``extract_metadata_*``
functions in the backends are documented as "public" via
``docs/API.md`` and will keep their signatures across 1.x.
"""

from hwp2md.core import ImageMode, batch_convert, convert
from hwp2md.exceptions import (
    ConversionError,
    EncryptedDocumentError,
    Hwp2mdError,
    UnsupportedFormatError,
)

__version__ = "1.0.0"
__all__ = [
    "convert",
    "batch_convert",
    "ImageMode",
    "Hwp2mdError",
    "UnsupportedFormatError",
    "ConversionError",
    "EncryptedDocumentError",
    "__version__",
]
