import json

import pytest
from bs4 import BeautifulSoup

from tests.testutils.fixture_data import FIXTURE_ENTRIES, FIXTURES_DIR


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


_SCRUB_TAGS = ("script", "style", "link", "meta", "noscript", "iframe", "svg", "nav", "footer", "header", "form")


# Fixture HTML is scrubbed before storage to remove page chrome (nav, footer,
# forms) and transient data (CSRF tokens, tracking scripts) that are never
# read by any parser. If a future parser needs these elements, revisit this list.
def _scrub_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_SCRUB_TAGS):
        tag.decompose()
    for tag in soup.select("input[type=hidden], span.csrf-token, #comments_table"):
        tag.decompose()
    return soup.prettify()


def _regenerate_fixtures(filter_key: str, mode: str) -> None:
    from cpfetch.cpparse import get_parser
    from cpfetch.cpparse.fetch import BrowserFetch

    entries = _resolve_entries(filter_key)

    with BrowserFetch() as fetcher:
        for site, url, slug in entries:
            parser = get_parser(url, fetcher)
            assert parser is not None

            if mode in ("all", "html"):
                html = fetcher.fetch(url, parser.selector, headless=parser.headless)
                if html is None:
                    pytest.exit(f"Failed to fetch {url}", returncode=1)
                html = _scrub_html(html)
                html_path = FIXTURES_DIR / site / f"{slug}.html"
                html_path.write_text(html, encoding="utf-8")
                print(f"Regenerated {html_path}")
            else:
                html = (FIXTURES_DIR / site / f"{slug}.html").read_text(encoding="utf-8")

            if mode in ("all", "json"):
                data = parser.extract_data(html, url)
                assert data is not None
                snapshot = {
                    "name": data.name,
                    "site": data.site,
                    "platform": data.platform,
                    "url": data.url,
                    "time_limit": data.time_limit,
                    "memory_limit": data.memory_limit,
                    "body_html": data.body_html,
                    "samples": [{"input": s.input, "output": s.output} for s in data.samples],
                    "math_values": list(dict.fromkeys(data.math.values())),
                }
                json_path = FIXTURES_DIR / site / f"{slug}.json"
                json_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                print(f"Regenerated {json_path}")


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--regenerate",
        nargs="?",
        const="",
        default=None,
        help="Regenerate fixture snapshots. Filter: site or site/slug",
    )
    parser.addoption(
        "--html-only",
        action="store_true",
        default=False,
        help="With --regenerate: regenerate HTML only",
    )
    parser.addoption(
        "--json-only",
        action="store_true",
        default=False,
        help="With --regenerate: regenerate JSON only",
    )


@pytest.fixture(scope="session", autouse=True)
def _handle_regenerate(request: pytest.FixtureRequest) -> None:
    val: str | None = request.config.getoption("--regenerate")
    if val is None:
        return
    html_only: bool = request.config.getoption("--html-only")
    json_only: bool = request.config.getoption("--json-only")
    if html_only and json_only:
        pytest.exit("Cannot use both --html-only and --json-only", returncode=1)
    if html_only:
        mode = "html"
    elif json_only:
        mode = "json"
    else:
        mode = "all"
    _regenerate_fixtures(val, mode)
    pytest.exit("Fixtures regenerated; stopping test run.", returncode=0)
