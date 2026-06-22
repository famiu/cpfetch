# cpfetch

Fetch competitive programming problem statements, samples, and metadata from Codeforces, AtCoder, CodeChef, and CSES.

## Layout

- `src/cpfetch/` — package root
  - `cp_metadata.py` — data types (`ProblemData`, `SampleCase`, `MathExtractor`), `site_from_url`, meta I/O, helpers
  - `fetch_problem.py` — CLI entry point (`main()`, `setup()`)
  - `cpparse/` — per-judge parsers
    - `__init__.py` — `get_parser()` URL-dispatch factory
    - `lib.py` — `BaseParser`, `render_markdown()`, helpers
    - `fetch.py` — `PlaywrightFetch` context manager
    - `platforms/` — `atcoder.py`, `codechef.py`, `codeforces.py`, `cses.py`
- `tests/` — pytest suite
  - `test_metadata.py` — unit tests (helpers + parser internals)
  - `test_workflow.py` — workflow tests (file I/O + markdown render)
  - `test_live.py` — parametrized over 4 sites (gated: `pytest -m integration`)

## Pipeline

`get_parser(url)` → `parser.parse(url)` → `ProblemData` → `render_markdown(data)` → writes `problem.md`, `tests/*.in`/`*.out`, `meta.json`.

To add a platform: subclass `BaseParser` in `cpparse/platforms/`, register it in `cpparse/__init__.py` (`_PARSERS`), and add the host to `_HOST_SITES` in `cp_metadata.py`.

## Commands

- `uv run pytest tests/` — run offline tests
- `uv run pytest tests/ -m integration` — run integration tests
- `uv run ruff check src/ tests/` — lint
- `uv run ruff format --check src/ tests/` — format check
- `uv run ty check` — typecheck

## Rules

- When features or CLI usage change, update README.md accordingly.
- When fixing a bug, always add a test that checks for regression.
- Keep AGENTS.md in sync with the repo: update it when the software layout, core paradigms, or documented commands change.
  Do not log every minor change or implementation detail here. This is a high-level map, not a changelog.
