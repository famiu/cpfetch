"""Fixture regeneration utilities and HTML scrubbing."""

import json
import re

import pytest
from bs4 import BeautifulSoup

from tests.testutils.fixture_data import FIXTURE_ENTRIES, FIXTURES_DIR

_SCRUB_TAGS = ("script", "style", "link", "meta", "noscript", "iframe", "svg", "nav", "footer", "header", "form")

SENTINEL_RE = re.compile(r"XX-MATH-(\d+)-[a-f0-9]+-XX")


def normalize_sentinels(text: str) -> str:
    """Strip the per-instance uuid token from sentinel keys for stable comparison."""
    return SENTINEL_RE.sub(r"XX-MATH-\1-XX", text)


# Fixture HTML is scrubbed before storage to remove page chrome (nav, footer,
# forms) and transient data (CSRF tokens, tracking scripts) that are never
# read by any parser. If a future parser needs these elements, revisit this list.
def scrub_html(html: str) -> str:
    """Remove page chrome and transient elements from fixture HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_SCRUB_TAGS):
        tag.decompose()
    for tag in soup.select("input[type=hidden], span.csrf-token, #comments_table"):
        tag.decompose()
    return str(soup)


def _resolve_entries(filter_key: str) -> list[tuple[str, str, str]]:
    if not filter_key:
        return list(FIXTURE_ENTRIES)
    parts = filter_key.split("/", 1)
    site = parts[0]
    slug = parts[1] if len(parts) > 1 else None
    if slug is not None:
        entries = [(s, u, sl) for (s, u, sl) in FIXTURE_ENTRIES if s == site and sl == slug]
    else:
        entries = [(s, u, sl) for (s, u, sl) in FIXTURE_ENTRIES if s == site]
    if not entries:
        pytest.exit(f"No fixtures matching {filter_key!r}", returncode=1)
    return entries


def regenerate_fixtures(filter_key: str, mode: str) -> None:
    """Regenerate fixture HTML and/or JSON snapshots."""
    from cpfetch.cpparse import get_parser
    from cpfetch.cpparse.fetch import BrowserFetch

    entries = _resolve_entries(filter_key)

    with BrowserFetch() as fetcher:
        for site, url, slug in entries:
            parser = get_parser(url, fetcher)
            if parser is None:
                pytest.exit(f"No parser found for {url}", returncode=1)

            if mode in ("all", "html"):
                html = fetcher.fetch(url, parser.selector, headless=parser.headless)
                if html is None:
                    pytest.exit(f"Failed to fetch {url}", returncode=1)
                html = scrub_html(html)
                html_path = FIXTURES_DIR / site / f"{slug}.html"
                html_path.write_text(html, encoding="utf-8")
                print(f"Regenerated {html_path}")
            else:
                html = (FIXTURES_DIR / site / f"{slug}.html").read_text(encoding="utf-8")

            if mode in ("all", "json"):
                data = parser.extract_data(html, url)
                if data is None:
                    pytest.exit(f"Failed to parse {url}", returncode=1)
                snapshot = {
                    "name": data.name,
                    "site": data.site,
                    "platform": data.platform,
                    "url": data.url,
                    "time_limit": data.time_limit,
                    "memory_limit": data.memory_limit,
                    "body_html": normalize_sentinels(data.body_html),
                    "samples": [{"input": s.input, "output": s.output} for s in data.samples],
                    "math": {normalize_sentinels(k): v for k, v in data.math.items()},
                }
                json_path = FIXTURES_DIR / site / f"{slug}.json"
                json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(f"Regenerated {json_path}")
