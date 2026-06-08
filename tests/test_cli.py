"""Smoke tests for the public API + CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from hwp2md import __version__, batch_convert, convert
from hwp2md.exceptions import (
    ConversionError,
    EncryptedDocumentError,
    UnsupportedFormatError,
)


def test_version_is_string() -> None:
    assert isinstance(__version__, str)
    assert __version__.count(".") >= 1


def test_convert_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        convert(tmp_path / "nope.hwp")


def test_convert_unsupported_extension(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello")
    with pytest.raises(UnsupportedFormatError):
        convert(f)


def test_convert_hwpx_not_implemented(tmp_path: Path) -> None:
    f = tmp_path / "test.hwpx"
    f.write_bytes(b"PK\x03\x04")  # ZIP magic, but empty
    with pytest.raises(ConversionError):
        convert(f)


def test_batch_convert_skips_non_hwp_files(tmp_path: Path) -> None:
    (tmp_path / "a.hwpx").write_bytes(b"x")
    (tmp_path / "b.txt").write_text("ignore me")
    out = tmp_path / "out"
    # batch_convert should yield a for a.hwpx then raise ConversionError
    # because the HWPX parser is not yet implemented. That's expected.
    gen = batch_convert(tmp_path, out)
    with pytest.raises(ConversionError):
        next(gen)


def test_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "hwp2md.cli", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Convert Korean HWP" in result.stdout
