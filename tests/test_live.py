import os

import pytest

from cpfetch.cpparse import get_parser

# (site, url, expected_name, time_limit_ms, memory_limit_mb, sample_count)
SITES = [
    pytest.param(
        "cses",
        "https://cses.fi/problemset/task/1092",
        "Two Sets",
        1000.0,
        512,
        2,
        id="cses",
    ),
    pytest.param(
        "atcoder",
        "https://atcoder.jp/contests/abc233/tasks/abc233_a",
        "A - 10yen Stamp",
        2000.0,
        1024,
        3,
        id="atcoder",
    ),
    pytest.param(
        "codeforces",
        "https://codeforces.com/problemset/problem/1/A",
        "A. Theatre Square",
        1000.0,
        256,
        1,
        id="codeforces",
    ),
    pytest.param(
        "codechef",
        "https://www.codechef.com/problems/FLOW006",
        "Sum of Digits",
        1000.0,
        1536,
        1,
        id="codechef",
    ),
    pytest.param(
        "spoj",
        "https://www.spoj.com/problems/FCTRL/",
        "FCTRL - Factorial",
        6000.0,
        1536,
        1,
        id="spoj",
        marks=pytest.mark.skipif(
            not os.environ.get("DISPLAY"),
            reason="SPOJ requires a headed browser (Cloudflare Turnstile); set DISPLAY or use xvfb-run",
        ),
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize(
    "site,url,expected_name,time,mem,count",
    SITES,
)
def test_live_fetch(
    site: str,
    url: str,
    expected_name: str,
    time: float,
    mem: int,
    count: int,
) -> None:
    """Smoke test: fetch and parse a known live problem, verifying full metadata."""
    parser = get_parser(url)
    assert parser is not None
    data = parser.parse(url)
    assert data is not None, f"{site}: parse returned None"
    assert data.name == expected_name, f"{site}: expected {expected_name!r}, got {data.name!r}"
    assert data.time_limit == time
    assert data.memory_limit == mem
    assert data.url == url
    assert data.site == site
    assert len(data.body_html) > 0
    assert len(data.samples) == count
    for i, sample in enumerate(data.samples):
        assert sample.input.strip(), f"sample[{i}] input is empty"
        assert sample.output.strip(), f"sample[{i}] output is empty"
    assert len(data.math) > 0
