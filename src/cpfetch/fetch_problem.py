#!/usr/bin/env python3
"""CLI entry point for fetching problem data and rendering problem.md.

Single-fetch:  cpfetch --url <url> [--out-dir <dir>] [--nest]
Multi-fetch:   cpfetch --url <url1> --url <url2> [--out-dir <dir>] [--nest]
Batch refetch: cpfetch --all
"""

import argparse
import logging
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
from cpfetch.cpparse.fetch import BrowserFetch

_log = logging.getLogger(__name__)


def write_samples(tests_dir: Path, samples: list[SampleCase]) -> None:
    """Write sample test cases as .in / .out files under *tests_dir*."""
    tests_dir.mkdir(parents=True, exist_ok=True)

    for p in tests_dir.iterdir():
        if p.suffix in (".in", ".out") and p.stem.isdigit():
            p.unlink()

    for i, sample in enumerate(samples, 1):
        _ = (tests_dir / f"{i:02d}.in").write_text(sample.input, encoding="utf-8")
        _ = (tests_dir / f"{i:02d}.out").write_text(sample.output, encoding="utf-8")


def process_url(url: str, out_dir: Path, nest: bool, fetcher: BrowserFetch) -> str | None:
    """Fetch problem, render markdown, write artifacts. Returns output dir path or None."""
    parser = get_parser(url, fetcher)
    if parser is None:
        _log.error("unsupported platform for URL: %s", url)
        return None

    data = parser.parse(url)
    if data is None:
        _log.error("failed to fetch: %s", url)
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

    _log.info("saved: %s", output_dir)
    return str(output_dir)


def setup() -> None:
    """Install Patchright Chromium browser."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "patchright", "install", "chromium"],
        )
    except subprocess.CalledProcessError as exc:
        _log.error("patchright install failed: %s", exc)
        sys.exit(1)


def main() -> None:
    """Entry point: parse CLI arguments and dispatch to the appropriate action."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

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
        _log.error("--all and --url are mutually exclusive")
        sys.exit(1)

    if args.all:
        root = Path(args.problems_dir).resolve()
        if not root.is_dir():
            _log.error("problems root not found: %s", root)
            sys.exit(1)
        failures = 0
        meta_paths = sorted(root.glob("**/meta.json"))
        total = len(meta_paths)
        with BrowserFetch() as fetcher:
            for i, meta_path in enumerate(meta_paths, 1):
                _log.info("(%d/%d) processing %s", i, total, meta_path.parent)
                url = load_meta_url(meta_path.parent)
                if url is None:
                    _log.error("invalid meta.json in %s", meta_path.parent)
                    failures += 1
                    continue
                result = process_url(url, meta_path.parent, nest=False, fetcher=fetcher)
                if result is None:
                    failures += 1
        if failures:
            _log.error("%d problem(s) failed", failures)
            sys.exit(1)
        return

    if not args.url:
        _log.error("specify --url or --all")
        sys.exit(1)

    urls: list[str] = args.url
    if len(urls) > 1 and not args.nest:
        _log.error("multiple --url requires --nest")
        sys.exit(1)

    out_dir = Path(args.out_dir).resolve()
    failures = 0
    results: list[str] = []
    with BrowserFetch() as fetcher:
        for url in urls:
            result = process_url(url, out_dir, args.nest, fetcher)
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
