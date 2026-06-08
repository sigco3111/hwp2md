"""Synthetic-corpus accuracy benchmark for hwp2md.

Builds a small corpus of HWPX and HWP 5.x inputs (synthesised in
memory from the test fixtures) and compares the rendered markdown
to a hand-curated expected output. Prints a per-case pass/fail
table and exits non-zero if any case fails.

This is a self-test, not a real-world benchmark — a public HWP
corpus is still needed for that. See ``docs/ACCURACY.md`` for
the methodology and known limitations.
"""

from __future__ import annotations

import io
import struct
import sys
import tempfile
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from hwp2md import convert  # noqa: E402
from tests.fixtures.hwpx_builder import HwpxDocument, build_hwpx_bytes  # noqa: E402


@dataclass
class HwpCase:
    name: str
    build: Callable[[], bytes]
    expected_contains: List[str]
    expected_not_contains: List[str] = None  # type: ignore[assignment]


@dataclass
class Result:
    name: str
    passed: bool
    missing: List[str]
    unexpected: List[str]


def _expect_contains(actual: str, needles: List[str]) -> List[str]:
    return [n for n in needles if n not in actual]


def _expect_not_contains(actual: str, needles: List[str]) -> List[str]:
    return [n for n in needles if n in actual]


def build_corpus() -> List[HwpCase]:
    cases: List[HwpCase] = []

    def _simple_paragraph() -> bytes:
        doc = HwpxDocument()
        doc.add_para("안녕하세요")
        return build_hwpx_bytes(doc)

    cases.append(HwpCase(
        name="hwpx/simple_paragraph",
        build=_simple_paragraph,
        expected_contains=["안녕하세요"],
    ))

    def _headings() -> bytes:
        doc = HwpxDocument()
        doc.add_para("제목", outline=1)
        doc.add_para("소제목", outline=2)
        doc.add_para("본문")
        return build_hwpx_bytes(doc)

    cases.append(HwpCase(
        name="hwpx/headings",
        build=_headings,
        expected_contains=["# 제목", "## 소제목", "본문"],
    ))

    def _bold_italic() -> bytes:
        doc = HwpxDocument()
        doc.add_para("굵게", bold=True)
        doc.add_para("기울임", italic=True)
        doc.add_para("둘 다", bold=True, italic=True)
        return build_hwpx_bytes(doc)

    cases.append(HwpCase(
        name="hwpx/bold_italic",
        build=_bold_italic,
        expected_contains=["**굵게**", "*기울임*", "***둘 다***"],
    ))

    def _table() -> bytes:
        doc = HwpxDocument()
        doc.add_table([
            ["이름", "나이"],
            ["홍길동", "30"],
            ["김철수", "25"],
        ])
        return build_hwpx_bytes(doc)

    cases.append(HwpCase(
        name="hwpx/table",
        build=_table,
        expected_contains=[
            "| 이름 | 나이 |",
            "| --- | --- |",
            "| 홍길동 | 30 |",
            "| 김철수 | 25 |",
        ],
    ))

    PNG = bytes.fromhex(
        "89504E470D0A1A0A0000000D49484452000000010000000108060000"
        "001F15C4890000000A49444154789C6300010000000500010D0A2DB4"
        "0000000049454E44AE426082"
    )

    def _image_link() -> bytes:
        doc = HwpxDocument()
        doc.add_image("figure1.png", PNG)
        doc.add_para(
            "본문",
            images=[("img001", "BinData/figure1.png")],
        )
        return build_hwpx_bytes(doc)

    def _image_embed() -> bytes:
        return _image_link()

    cases.append(HwpCase(
        name="hwpx/image_link",
        build=_image_link,
        expected_contains=[".png"],
        expected_not_contains=["data:image/png;base64"],
    ))
    cases.append(HwpCase(
        name="hwpx/image_embed",
        build=_image_embed,
        expected_contains=["data:image/png;base64"],
    ))
    cases.append(HwpCase(
        name="hwpx/image_skip",
        build=_image_link,
        expected_contains=["본문"],
        expected_not_contains=[".png", "data:image/png"],
    ))

    def _frontmatter() -> bytes:
        doc = HwpxDocument()
        doc.set_metadata(
            title="2025년 동향",
            author="홍길동",
            date="2025-01-15",
            keywords=["AI", "산업"],
        )
        doc.add_para("본문", outline=1)
        return build_hwpx_bytes(doc)

    cases.append(HwpCase(
        name="hwpx/frontmatter",
        build=_frontmatter,
        expected_contains=[
            "---",
            "title: 2025년 동향",
            "author: 홍길동",
            "date: 2025-01-15",
            "  - AI",
            "  - 산업",
            "# 본문",
        ],
    ))

    def _no_frontmatter() -> bytes:
        return _frontmatter()

    cases.append(HwpCase(
        name="hwpx/no_frontmatter",
        build=_no_frontmatter,
        expected_contains=["# 본문"],
        expected_not_contains=["title:", "author:"],
    ))

    return cases


def run_case(case: HwpCase, mode_kwargs: Optional[dict] = None) -> Result:
    mode_kwargs = mode_kwargs or {}
    with tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False) as f:
        f.write(case.build())
        path = Path(f.name)
    try:
        actual = convert(path, **mode_kwargs)
    finally:
        path.unlink()
    missing = _expect_contains(actual, case.expected_contains)
    unexpected = (
        _expect_not_contains(actual, case.expected_not_contains)
        if case.expected_not_contains else []
    )
    return Result(
        name=case.name,
        passed=not missing and not unexpected,
        missing=missing,
        unexpected=unexpected,
    )


def main() -> int:
    cases = build_corpus()
    skip_in_embed: List[str] = []
    skip_in_link: List[str] = []
    skip_in_skip: List[str] = []

    override = {
        "hwpx/image_embed": {"image_mode": "embed"},
        "hwpx/image_skip": {"image_mode": "skip"},
        "hwpx/no_frontmatter": {"with_metadata": False},
    }

    results: List[Result] = []
    for case in cases:
        kwargs = override.get(case.name, {})
        results.append(run_case(case, kwargs))

    width = max(len(r.name) for r in results) if results else 20
    print(f"{'CASE':<{width}}  STATUS")
    print("-" * (width + 10))
    passed = 0
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"{r.name:<{width}}  {status}")
        if r.missing:
            print(f"  missing: {r.missing}")
        if r.unexpected:
            print(f"  unexpected: {r.unexpected}")
        if r.passed:
            passed += 1

    total = len(results)
    pct = (100 * passed / total) if total else 0
    print("-" * (width + 10))
    print(f"Result: {passed}/{total} ({pct:.1f}%)")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
