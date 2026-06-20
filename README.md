# cpfetch

Fetch competitive programming problem statements, samples, and metadata
from Codeforces, AtCoder, CodeChef, and CSES.

## Install

```sh
uv sync
uv run cpfetch setup
```

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

AGPLv3 or later.
