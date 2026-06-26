#!/usr/bin/env python3
"""CLI entry point for fetching problem data and rendering problem.md.

Fetch:   cpfetch fetch <url> [<url> ...] [--out-dir <dir>] [--nest]
Refetch: cpfetch refetch [--problems-dir <dir>]
Setup:   cpfetch setup
"""

import argparse
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from cpfetch.cp_metadata import (
    ProblemData,
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


def process_url(
    url: str,
    out_dir: Path,
    nest: bool,
    fetcher: BrowserFetch,
    *,
    atomic: bool = False,
) -> str | None:
    """Fetch problem, render markdown, write artifacts. Returns output dir path or None.

    When *atomic* is True, artifacts are written to a temporary staging directory
    and the target directory is replaced only after all writes succeed. This
    prevents partial updates to an existing problem directory on failure.
    """
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

    # Build all file contents in memory before writing to minimize partial state on failure.
    md_content = render_markdown(data)

    if atomic:
        try:
            return _write_atomic(output_dir, data, md_content)
        except OSError as exc:
            _log.error("failed to write %s: %s", output_dir, exc)
            return None

    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        write_samples(output_dir / "tests", data.samples)
        _ = (output_dir / "problem.md").write_text(md_content, encoding="utf-8")
        save_meta_json(output_dir, data)
    except OSError as exc:
        _log.error("failed to write %s: %s", output_dir, exc)
        return None

    _log.info("saved: %s", output_dir)
    return str(output_dir)


def _write_atomic(output_dir: Path, data: ProblemData, md_content: str) -> str | None:
    """Write artifacts to a staging dir, then atomically replace *output_dir*."""
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    # Restore leftover backup from a previous interrupted run
    backup_dir = output_dir.with_name(f".{output_dir.name}.old")
    if backup_dir.exists() and not output_dir.exists():
        backup_dir.rename(output_dir)

    staging_dir = Path(tempfile.mkdtemp(dir=output_dir.parent, prefix=f".{output_dir.name}."))
    try:
        write_samples(staging_dir / "tests", data.samples)
        _ = (staging_dir / "problem.md").write_text(md_content, encoding="utf-8")
        save_meta_json(staging_dir, data)

        if output_dir.exists():
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            output_dir.rename(backup_dir)
            try:
                staging_dir.rename(output_dir)
            except OSError:
                backup_dir.rename(output_dir)
                raise
            shutil.rmtree(backup_dir, ignore_errors=True)
        else:
            staging_dir.rename(output_dir)

        _log.info("saved: %s", output_dir)
        return str(output_dir)
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise


def setup() -> None:
    """Install Patchright Chromium browser."""
    try:
        subprocess.check_call(
            [sys.executable, "-m", "patchright", "install", "chromium"],
        )
    except subprocess.CalledProcessError as exc:
        _log.error("patchright install failed: %s", exc)
        sys.exit(1)


def _run_fetch(urls: list[str], out_dir: Path, nest: bool) -> int:
    """Fetch one or more problems. Returns failure count."""
    if len(urls) > 1 and not nest:
        _log.error("multiple URLs require --nest")
        sys.exit(1)
    failures = 0
    results: list[str] = []
    with BrowserFetch() as fetcher:
        for url in urls:
            result = process_url(url, out_dir, nest, fetcher, atomic=nest)
            if result is None:
                failures += 1
            else:
                results.append(result)
    if results:
        for path in results:
            print(path)
    return failures


def _run_refetch(problems_dir: Path) -> int:
    """Re-fetch all problems with meta.json under *problems_dir*. Returns failure count."""
    if not problems_dir.is_dir():
        _log.error("problems root not found: %s", problems_dir)
        sys.exit(1)

    for backup_dir in problems_dir.glob("**/.*.old"):
        if backup_dir.is_dir():
            visible_dir = backup_dir.with_name(backup_dir.name[1:-4])
            if not visible_dir.exists():
                backup_dir.rename(visible_dir)

    failures = 0
    meta_paths = sorted(problems_dir.glob("**/meta.json"))
    total = len(meta_paths)
    with BrowserFetch() as fetcher:
        for i, meta_path in enumerate(meta_paths, 1):
            _log.info("(%d/%d) processing %s", i, total, meta_path.parent)
            url = load_meta_url(meta_path.parent)
            if url is None:
                _log.error("invalid meta.json in %s", meta_path.parent)
                failures += 1
                continue
            result = process_url(url, meta_path.parent, nest=False, fetcher=fetcher, atomic=True)
            if result is None:
                failures += 1
    return failures


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(description="Fetch problem data and render problem.md")
    subparsers = parser.add_subparsers(dest="command", required=True)

    _ = subparsers.add_parser("setup", help="install Patchright Chromium browser")

    fetch_parser = subparsers.add_parser("fetch", help="fetch one or more problem URLs")
    _ = fetch_parser.add_argument("urls", type=str, nargs="+", help="problem URL(s) to fetch")
    _ = fetch_parser.add_argument(
        "--out-dir",
        type=str,
        default=".",
        help="output directory (default: current directory)",
    )
    _ = fetch_parser.add_argument(
        "--nest",
        action="store_true",
        help="create {site}/{slug} subdirectory under --out-dir",
    )

    refetch_parser = subparsers.add_parser("refetch", help="re-fetch all problems using meta.json")
    _ = refetch_parser.add_argument(
        "--problems-dir",
        type=str,
        default=".",
        help="directory to walk for meta.json files (default: current directory)",
    )

    return parser


def main() -> None:
    """Entry point: parse CLI arguments and dispatch to the appropriate action."""
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "setup":
        setup()
        return

    if args.command == "fetch":
        out_dir = Path(args.out_dir).resolve()
        failures = _run_fetch(args.urls, out_dir, args.nest)
        if failures:
            sys.exit(1)
        return

    if args.command == "refetch":
        problems_dir = Path(args.problems_dir).resolve()
        failures = _run_refetch(problems_dir)
        if failures:
            _log.error("%d problem(s) failed", failures)
            sys.exit(1)
        return


if __name__ == "__main__":
    main()
