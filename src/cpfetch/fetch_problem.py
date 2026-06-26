#!/usr/bin/env python3
"""CLI entry point for fetching problem data and rendering problem.md.

Single-fetch:  cpfetch --url <url> [--out-dir <dir>] [--nest]
Multi-fetch:   cpfetch --url <url1> --url <url2> [--out-dir <dir>] [--nest]
Batch refetch: cpfetch --all
"""

import argparse
import subprocess
import sys
from pathlib import Path

from cpfetch.cp_metadata import (
    SampleCase,
    load_meta_url,
    save_meta_json,
    slugify,
)
from cpfetch.cpparse import get_parser, render_markdown


def write_samples(tests_dir: Path, samples: list[SampleCase]) -> None:
    """Write sample test cases as .in / .out files under *tests_dir*."""
    tests_dir.mkdir(parents=True, exist_ok=True)

    for p in tests_dir.iterdir():
        if p.suffix in (".in", ".out") and p.stem.isdigit():
            p.unlink()

    for i, sample in enumerate(samples, 1):
        _ = (tests_dir / f"{i:02d}.in").write_text(sample.input, encoding="utf-8")
        _ = (tests_dir / f"{i:02d}.out").write_text(sample.output, encoding="utf-8")


def process_url(url: str, out_dir: Path, nest: bool) -> str | None:
    """Fetch problem, render markdown, write artifacts. Returns output dir path or None."""
    parser = get_parser(url)
    if parser is None:
        print(
            f"error: unsupported platform for URL: {url}",
            file=sys.stderr,
            flush=True,
        )
        return None

    data = parser.parse(url)
    if data is None:
        print(
            f"error: failed to fetch: {url}",
            file=sys.stderr,
            flush=True,
        )
        return None

    if nest:
        slug = slugify(data.name)
        output_dir = out_dir / data.site / slug
    else:
        output_dir = out_dir

    output_dir.mkdir(parents=True, exist_ok=True)

    write_samples(output_dir / "tests", data.samples)

    md_content = render_markdown(data)
    _ = (output_dir / "problem.md").write_text(md_content, encoding="utf-8")

    save_meta_json(output_dir, data)

    print(f"saved: {output_dir}", file=sys.stderr, flush=True)
    return str(output_dir)


def setup() -> None:
    """Install Patchright Chromium browser."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "patchright", "install", "--with-deps", "chromium"],
        )
    except subprocess.CalledProcessError as exc:
        print(f"error: patchright install failed: {exc}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Entry point: parse CLI arguments and dispatch to the appropriate action."""
    parser = argparse.ArgumentParser(description="Fetch problem data and render problem.md")
    subparsers = parser.add_subparsers(dest="command")
    _ = subparsers.add_parser("setup", help="install Patchright Chromium browser")

    _ = parser.add_argument(
        "--url",
        type=str,
        action="append",
        default=None,
        help="problem URL to fetch (repeatable)",
    )
    _ = parser.add_argument(
        "--out-dir",
        type=str,
        default=".",
        help="output directory (default: current directory)",
    )
    _ = parser.add_argument(
        "--nest",
        action="store_true",
        help="create {site}/{slug} subdirectory under --out-dir",
    )
    _ = parser.add_argument(
        "--all",
        action="store_true",
        help="re-fetch all problems using meta.json under --problems-dir",
    )
    _ = parser.add_argument(
        "--problems-dir",
        type=str,
        default=".",
        help="directory to walk for meta.json files (default: current directory)",
    )
    args = parser.parse_args()

    if args.command == "setup":
        setup()
        return

    if args.all and args.url:
        print("error: --all and --url are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    if args.all:
        root = Path(args.problems_dir).resolve()
        if not root.is_dir():
            print(f"error: problems root not found: {root}", file=sys.stderr)
            sys.exit(1)
        failures = 0
        meta_paths = sorted(root.glob("**/meta.json"))
        total = len(meta_paths)
        for i, meta_path in enumerate(meta_paths, 1):
            print(
                f"({i}/{total}) processing {meta_path.parent}",
                file=sys.stderr,
                flush=True,
            )
            url = load_meta_url(meta_path.parent)
            if url is None:
                print(
                    f"error: invalid meta.json in {meta_path.parent}",
                    file=sys.stderr,
                )
                failures += 1
                continue
            result = process_url(url, meta_path.parent, nest=False)
            if result is None:
                failures += 1
        if failures:
            print(
                f"error: {failures} problem(s) failed",
                file=sys.stderr,
                flush=True,
            )
            sys.exit(1)
        return

    if not args.url:
        print("error: specify --url or --all", file=sys.stderr)
        sys.exit(1)

    urls: list[str] = args.url
    if len(urls) > 1 and not args.nest:
        print("error: multiple --url requires --nest", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.out_dir).resolve()
    failures = 0
    results: list[str] = []
    for url in urls:
        result = process_url(url, out_dir, args.nest)
        if result is None:
            failures += 1
        else:
            results.append(result)
    if results:
        for path in results:
            print(path)
    if failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
