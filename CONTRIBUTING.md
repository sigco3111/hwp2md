# Contributing to hwp2md

Thanks for your interest. hwp2md is a small project, so the
process is light, but we do have a few conventions.

## Quick rules

1. **One feature per branch** — keep PRs focused.
2. **Tests are required** for new functionality. The bar is
   "if the test passes, you can be reasonably confident the
   feature works on real-world input."
3. **No new runtime dependencies** without a discussion. The
   zero-deps posture is intentional.
4. **Public API changes** require updating [`docs/API.md`](docs/API.md)
   in the same PR.
5. **Changelog** every user-visible change in [`CHANGELOG.md`](CHANGELOG.md)
   under the `## [Unreleased]` section.

## Development setup

```bash
git clone https://github.com/sigco3111/hwp2md
cd hwp2md
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all,dev]"
pytest
```

Optional but recommended:

```bash
pip install yamllint
yamllint action.yml .github/workflows/ .yamllint.yaml
python scripts/benchmark.py
```

The CI pipeline runs all of the above.

## Test layout

- `tests/test_cli.py` — CLI and public API smoke tests
- `tests/test_hwpx.py` — HWPX parser (in-memory ZIP + XML)
- `tests/test_hwp5.py` — HWP 5.x record walker, char shapes,
  table recognition, metadata extraction
- `tests/test_metadata.py` — Frontmatter rendering and HWPX
  header parsing
- `tests/fixtures/hwpx_builder.py` — Synthetic HWPX builder
  used by tests and the benchmark

When adding a new test, prefer building a synthetic input over
shipping a real HWP/HWPX file. Real files raise licence and
privacy concerns; synthetic inputs are deterministic and easy
to read.

## Code style

- Line length 100 (enforced by `ruff` config; run
  `ruff check` if you have it).
- Type hints on every public function. `mypy --strict` passes
  on the public modules.
- `from __future__ import annotations` at the top of new
  modules.
- Module docstrings on every public module. Function
  docstrings on every public function. No narrative comments
  inside function bodies — keep code self-explanatory.

## Commit messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: short summary (vX.Y.Z)
fix: short summary
docs: short summary
test: short summary
chore: short summary
```

For release commits, include the version in parentheses:
`feat: HWP 5.x tables (v0.3.0)`.

## Pull request checklist

- [ ] `pytest` passes locally with 100% of the affected test
      file passing.
- [ ] `yamllint` is clean.
- [ ] `scripts/benchmark.py` exits 0.
- [ ] `CHANGELOG.md` `## [Unreleased]` has an entry.
- [ ] If the public API changed, `docs/API.md` is updated
      in the same PR.
- [ ] If new runtime dependencies were added, an explanation
      is in the PR description (we want to stay zero-deps for
      the core).

## Sending sample HWP files

We **cannot** accept real-world HWP files containing personal,
classified, or otherwise restricted content. For test
corpus contributions, please either:

1. Anonymise / strip the document before sending.
2. Hand-write a small synthetic HWP in Hancom Office and
   send that.
3. Open an issue describing the failure mode (with the
   rendered output) and we'll try to reproduce it on our own
   synthetic corpus.

For licence, all contributions are accepted under the project's
MIT licence.

## Reporting bugs

Open an issue at
[github.com/sigco3111/hwp2md/issues](https://github.com/sigco3111/hwp2md/issues)
with:

- The command you ran (CLI form) or Python snippet (API form).
- The error message, if any.
- A description of what you expected vs. what you got.
- If possible: a stripped / synthetic reproducer.
