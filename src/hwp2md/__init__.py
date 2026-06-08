"""hwp2md - Convert Korean HWP (한글) files to clean Markdown.

Offline-first, LLM RAG-friendly, zero-dependency core.
"""

from hwp2md.core import ImageMode, batch_convert, convert
from hwp2md.exceptions import ConversionError, Hwp2mdError, UnsupportedFormatError

__version__ = "0.4.0"
__all__ = [
    "convert",
    "batch_convert",
    "Hwp2mdError",
    "UnsupportedFormatError",
    "ConversionError",
    "ImageMode",
    "__version__",
]
