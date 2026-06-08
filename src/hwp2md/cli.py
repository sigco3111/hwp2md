"""Command-line interface for hwp2md.

Entry point: `hwp2md` (registered in pyproject.toml [project.scripts]).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from hwp2md import __version__, batch_convert, convert
from hwp2md.exceptions import Hwp2mdError


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hwp2md",
        description="Convert Korean HWP/HWPX files to clean Markdown.",
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Input file or directory (.hwp, .hwpx)",
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output file or directory. Defaults to <input>.md alongside the source.",
    )
    parser.add_argument(
        "--encoding",
        default="utf-8",
        help="Output encoding (default: utf-8)",
    )
    parser.add_argument(
        "--images",
        choices=["embed", "link", "skip"],
        default="link",
        help="How to handle images (default: link)",
    )
    parser.add_argument(
        "--no-recursive",
        action="store_true",
        help="Disable recursive directory traversal",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=f"hwp2md {__version__}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        if args.input.is_dir():
            output_dir = args.output or (args.input / "markdown_output")
            count = 0
            for src, dst in batch_convert(
                args.input,
                output_dir,
                encoding=args.encoding,
                recursive=not args.no_recursive,
            ):
                print(f"✅ {src} → {dst}")
                count += 1
            print(f"\nConverted {count} file(s).")
            return 0
        else:
            md_text = convert(args.input, encoding=args.encoding)
            output = args.output or args.input.with_suffix(".md")
            output.write_text(md_text, encoding=args.encoding)
            print(f"✅ {args.input} → {output}")
            return 0
    except Hwp2mdError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1
    except FileNotFoundError as e:
        print(f"❌ {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
