# Accuracy and Benchmarking

## Scope

hwp2md's accuracy claim is qualified: **on a synthetic, in-tree
corpus we measure 100% pass rate across 9 representative cases.**
We do **not** claim this on a public HWP corpus — such a corpus
does not yet exist in a reusable form, and the HWP 5.x format is
proprietary and not fully reverse-engineered by us.

## Methodology

The benchmark script [`scripts/benchmark.py`](../scripts/benchmark.py)
builds a corpus of HWPX files in memory from
[`tests/fixtures/hwpx_builder.py`](../tests/fixtures/hwpx_builder.py).
For each case it:

1. Builds a synthetic `.hwpx` (ZIP + XML) on disk.
2. Calls `hwp2md.convert()` with mode-appropriate flags.
3. Asserts that the rendered markdown **contains** certain
   expected substrings and **does not contain** others.
4. Reports `PASS`/`FAIL` per case and an overall percentage.

The test cases are intentionally hand-curated, not random
fuzz inputs, so a regression signals a real parser change
rather than a fragile assertion.

## Cases (as of v1.0.0)

| Case | Input | What it checks |
|---|---|---|
| `hwpx/simple_paragraph` | Plain text body | UTF-8 round-trip |
| `hwpx/headings` | Outline levels 1, 2, 0 | Heading depth from outline |
| `hwpx/bold_italic` | Three runs with mixed bold/italic | Inline markdown formatting |
| `hwpx/table` | 3-row, 2-col table | GFM table output |
| `hwpx/image_link` | Body with `<hp:pic>` | Sidecar extraction + relative path |
| `hwpx/image_embed` | Same as above | Inline `data:` URI |
| `hwpx/image_skip` | Same as above | Image omitted from output |
| `hwpx/frontmatter` | Full metadata + body | YAML frontmatter rendering |
| `hwpx/no_frontmatter` | Same as above with `with_metadata=False` | Frontmatter suppressed |

## Results

```
CASE                   STATUS
-------------------------------
hwpx/simple_paragraph  PASS
hwpx/headings          PASS
hwpx/bold_italic       PASS
hwpx/table             PASS
hwpx/image_link        PASS
hwpx/image_embed       PASS
hwpx/image_skip        PASS
hwpx/frontmatter       PASS
hwpx/no_frontmatter    PASS
-------------------------------
Result: 9/9 (100.0%)
```

Run locally with:

```bash
python scripts/benchmark.py
```

The script exits non-zero on any failure, so it is suitable for
CI gating.

## HWP 5.x coverage

HWP 5.x accuracy is exercised through the 32 unit tests in
`tests/test_hwp5.py` (record walker, decompression, text
decoding, char shape parsing, table recognition, metadata
extraction). The benchmark script does **not** include HWP 5.x
cases because we cannot synthesise a valid OLE compound document
without adding a write-capable OLE library to the dev
dependencies — see the [Unreleased](../CHANGELOG.md#unreleased)
notes for `compoundfiles` as a possible future addition.

A 100% pass rate on the unit tests gives high confidence in the
record walker, decompression, and text decoding primitives, but
does not validate the full OLE stack against real-world HWP 5.x
files. **If you have a non-sensitive HWP 5.x file that fails
to convert correctly, please open an issue with the document
attached.**

## Public corpus goal

The roadmap entry for 1.0.0 included "90%+ document accuracy
benchmark". The honest 1.0.0 statement is:

- On the synthetic in-tree corpus: **100%**.
- On real-world HWPX files: **untested** in the absence of a
  public corpus; in-tree fixture validation + 16 HWPX unit
  tests give a reasonable proxy.
- On real-world HWP 5.x files: **partially covered** by 32
  unit tests targeting the record walker and DocInfo parsing
  primitives, but not end-to-end through a real OLE container.

We welcome contributions of:
- A public-domain HWPX sample corpus with hand-verified
  expected outputs.
- A real-world HWP 5.x test corpus (with permission to
  distribute — even 1–2 documents would be useful).
- A write-capable OLE library integration so we can run
  end-to-end HWP 5.x benchmarks in CI.

See [`CONTRIBUTING.md`](../CONTRIBUTING.md) for how to send
sample files.
