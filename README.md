# cpfetch

Easily fetch competitive programming problem statements and sample tests, right from your terminal.

For each problem, cpfetch saves a formatted `problem.md` (with LaTeX math restored), a `tests/` directory with numbered `.in`/`.out` sample files, and a `meta.json` for re-fetching. No browser extension required, everything runs from the command line.

- **Multi-platform**: Codeforces, AtCoder, CodeChef, CSES, SPOJ
- **Problem body + samples**: the full problem statement alongside ready-to-use test files
- **Math rendering**: correctly extracts inline math / math blocks from all of the supported platforms

Requires [Patchright](https://github.com/Kaliiiiiiiiii-Vinyzu/patchright) in order to bypass Cloudflare and process sites with dynamic content (e.g. CodeChef, SPOJ).

## Build + Setup

```sh
uv sync
uv run cpfetch setup
```

> [!NOTE]
> `cpfetch setup` installs Patchright's Chromium browser (without system dependencies).
> If system libraries are missing, install them manually or run `uv run patchright install --with-deps chromium` once as root.
> If you wish to remove the browser later, run `uv run patchright uninstall chromium`.

## Usage

```sh
# Fetch a problem
uv run cpfetch fetch https://cses.fi/problemset/task/1083

# Fetch into a specific directory
uv run cpfetch fetch https://codeforces.com/problemset/problem/1/A --out-dir problems

# Fetch multiple problems at once (requires --nest to avoid overwriting)
uv run cpfetch fetch https://cses.fi/problemset/task/1083 \
                     https://atcoder.jp/contests/abc233/tasks/abc233_a \
                     --out-dir problems --nest

# Create {site}/{slug} subdirectory under --out-dir
uv run cpfetch fetch https://atcoder.jp/contests/abc233/tasks/abc233_a --out-dir problems --nest

# Batch re-fetch all problems with meta.json under a directory
uv run cpfetch refetch --problems-dir problems
```

> [!NOTE]
> Some sites may be behind Cloudflare Turnstile. For these sites, the first fetch in a session opens a headed browser window to obtain a clearance cookie; subsequent fetches reuse it without a visible window.
> On a headless server, wrap with `xvfb-run`:
>
> ```sh
> xvfb-run uv run cpfetch fetch https://www.spoj.com/problems/TEST/
> ```

## Output

Each problem directory contains `problem.md`, `tests/` (numbered `.in`/`.out` files), and `meta.json`.

`meta.json` stores structured problem metadata:

```json
{
  "url": "https://codeforces.com/problemset/problem/4/A",
  "name": "Watermelon",
  "site": "codeforces",
  "platform": "Codeforces",
  "time_limit": 1000.0,
  "memory_limit": 256
}
```

## License

[AGPLv3 or later](LICENSE).
