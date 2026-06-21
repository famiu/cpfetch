# cpfetch

Easily fetch competitive programming problem statements and sample tests, right from your terminal.

For each problem, cpfetch saves a formatted `problem.md` (with LaTeX math restored), a `tests/` directory with numbered `.in`/`.out` sample files, and a `meta.json` for re-fetching. No browser extension required, everything runs from the command line.

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

# Batch re-fetch all problems with meta.json under a directory
uv run cpfetch --all --problems-dir problems
```

## Output

Each problem directory contains `problem.md`, `tests/` (numbered `.in`/`.out`
files), and `meta.json`.

`meta.json` stores structured problem metadata:

```json
{
  "version": 1,
  "url": "https://codeforces.com/problemset/problem/4/A",
  "name": "Watermelon",
  "site": "codeforces",
  "platform": "Codeforces",
  "time_limit": 1000.0,
  "memory_limit": 256
}
```

## Test

```sh
uv run pytest tests/
uv run pytest -m integration tests/
```

## License

[AGPLv3 or later](LICENSE).
