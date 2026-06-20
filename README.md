# cpfetch

Easily fetch competitive programming problem statements and sample tests, right from your terminal.

For each problem, cpfetch saves a formatted `problem.md` (with LaTeX math restored), a `tests/` directory with numbered `.in`/`.out` sample files, and a `.meta.json` for re-fetching. No browser extension required, everything runs from the command line.

- **Multi-platform**: Codeforces, AtCoder, CodeChef, CSES
- **Problem body + samples**: the full problem statement alongside ready-to-use test files
- **Math rendering**: correctly extracts inline math / math blocks from all of the supported platforms

Requires [Playwright](https://github.com/microsoft/playwright) in order to bypass Cloudflare and process sites with dynamic content (e.g. CodeChef).

## Build + Setup

```sh
uv sync
uv run cpfetch setup
```

> [!NOTE]
> `cpfetch setup` installs Playwright's headless Chromium browser.
> If you wish to remove it later, you have to run `uv run playwright uninstall chromium`.

## Usage

```sh
# Fetch a problem
uv run cpfetch --url https://cses.fi/problemset/task/1083

# Fetch into a specific directory
uv run cpfetch --url https://codeforces.com/problemset/problem/1/A --out-dir problems

# Fetch multiple problems at once (requires --nest to avoid overwriting)
uv run cpfetch --url https://cses.fi/problemset/task/1083 \
               --url https://atcoder.jp/contests/abc233/tasks/abc233_a \
               --out-dir problems --nest

# Create {site}/{slug} subdirectory under --out-dir
uv run cpfetch --url https://atcoder.jp/contests/abc233/tasks/abc233_a --out-dir problems --nest

# Batch re-fetch all problems with .meta.json under a directory
uv run cpfetch --all --problems-dir problems
```

## Test

```sh
uv run pytest tests/
uv run pytest -m integration tests/
```

## License

[AGPLv3 or later](LICENSE).
