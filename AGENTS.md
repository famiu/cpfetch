# cpfetch

Fetch competitive programming problem statements, samples, and metadata
from Codeforces, AtCoder, CodeChef, and CSES using Playwright.

## Layout

- `src/cpfetch/` — package root
  - `cp_metadata.py` — data types (`ProblemData`, `SampleCase`, `MathExtractor`), URL dispatch, helpers
  - `fetch_problem.py` — CLI entry point (`main()`, `setup()`)
  - `cpparse/` — per-judge parsers
    - `lib.py` — `BaseParser`, `render_markdown()`, helpers
    - `fetch.py` — `PlaywrightFetch` context manager
    - `platforms/` — `atcoder.py`, `codechef.py`, `codeforces.py`, `cses.py`
- `tests/` — pytest suite
  - `test_metadata.py` — unit tests (helpers)
  - `test_workflow.py` — 4 workflow tests (file I/O)
  - `test_live.py` — 4 integration tests (gated: `pytest -m integration`)

## Commands

- `uv run cpfetch --url <URL>` — fetch a problem
- `uv run cpfetch --url <URL1> --url <URL2> --nest` — fetch multiple problems
- `uv run cpfetch --all --problems-dir <DIR>` — batch refetch
- `uv run cpfetch setup` — install Playwright Chromium
- `uv run pytest tests/` — run offline tests

## Rules

- When features or CLI usage change, update README.md accordingly.
