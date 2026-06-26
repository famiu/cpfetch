"""Offline parser tests using pre-fetched HTML fixtures.

These tests validate full ProblemData extraction from real saved problem pages.
Each fixture directory contains an .html file (the page source) and a .json file
(the expected ProblemData snapshot). Tests compare every output field.

The body_html field comparison depends on BeautifulSoup's serialization format,
which can change across bs4 versions. If tests fail after a bs4 upgrade, regenerate
snapshots with:

    uv run pytest --regenerate                     # all fixtures, HTML + JSON
    uv run pytest --regenerate cses                # cses fixtures
    uv run pytest --regenerate cses/two_sets       # one fixture
    uv run pytest --regenerate --json-only         # JSON only, no re-fetch
"""

import json
import re

import pytest

from cpfetch.cpparse import get_parser
from tests.testutils.fixture_data import FIXTURE_ENTRIES, FIXTURES_DIR

_SENTINEL_RE = re.compile(r"XX-MATH-(\d+)-[a-f0-9]+-XX")


def _normalize_sentinels(html: str) -> str:
    """Strip the per-instance uuid token from sentinel keys for stable comparison."""
    return _SENTINEL_RE.sub(r"XX-MATH-\1-XX", html)


@pytest.mark.parametrize(("site", "url", "slug"), FIXTURE_ENTRIES)
def test_fixture_parse(site: str, url: str, slug: str) -> None:
    parser = get_parser(url)
    assert parser is not None

    html = (FIXTURES_DIR / site / f"{slug}.html").read_text(encoding="utf-8")
    expected = json.loads((FIXTURES_DIR / site / f"{slug}.json").read_text(encoding="utf-8"))

    data = parser.extract_data(html, url)
    assert data is not None

    assert data.name == expected["name"]
    assert data.site == expected["site"]
    assert data.platform == expected["platform"]
    assert data.url == expected["url"]
    assert data.time_limit == expected["time_limit"]
    assert data.memory_limit == expected["memory_limit"]
    assert _normalize_sentinels(data.body_html) == _normalize_sentinels(expected["body_html"])

    assert len(data.samples) == len(expected["samples"])
    for i, (a, e) in enumerate(zip(data.samples, expected["samples"], strict=True)):
        assert a.input == e["input"], f"sample[{i}] input differs"
        assert a.output == e["output"], f"sample[{i}] output differs"

    assert set(data.math.values()) == set(expected["math_values"])
