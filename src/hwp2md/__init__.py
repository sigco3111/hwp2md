"""hwp2md - Convert Korean HWP (한글) files to clean Markdown.

Offline-first, LLM RAG-friendly, zero-dependency core.
"""

from hwp2md.core import convert, batch_convert
from hwp2md.exceptions import Hwp2mdError, UnsupportedFormatError, ConversionError

__version__ = "0.1.0"
__all__ = [
    "convert",
    "batch_convert",
    "Hwp2mdError",
    "UnsupportedFormatError",
    "ConversionError",
    "__version__",
]
