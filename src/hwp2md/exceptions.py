"""Custom exceptions for hwp2md."""


class Hwp2mdError(Exception):
    """Base exception for all hwp2md errors."""


class UnsupportedFormatError(Hwp2mdError):
    """Raised when the input file format is not supported."""


class ConversionError(Hwp2mdError):
    """Raised when conversion fails for any reason."""


class EncryptedDocumentError(ConversionError):
    """Raised when the document is password-protected."""
