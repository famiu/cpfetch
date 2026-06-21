import pytest

from cpfetch.cpparse import get_parser

SITES = [
    pytest.param(
        "cses",
        "https://cses.fi/problemset/task/1092",
        "Two Sets",
        id="cses",
    ),
    pytest.param(
        "atcoder",
        "https://atcoder.jp/contests/abc233/tasks/abc233_a",
        "A - 10yen Stamp",
        id="atcoder",
    ),
    pytest.param(
        "codeforces",
        "https://codeforces.com/problemset/problem/1/A",
        "A. Theatre Square",
        id="codeforces",
    ),
    pytest.param(
        "codechef",
        "https://www.codechef.com/problems/FLOW006",
        "Sum of Digits",
        id="codechef",
    ),
]


@pytest.mark.integration
@pytest.mark.parametrize("site,url,expected_name", SITES)
def test_live_fetch(site: str, url: str, expected_name: str) -> None:
    """Smoke test: fetch and parse a known live problem."""
    parser = get_parser(url)
    assert parser is not None
    data = parser.parse(url)
    assert data is not None, f"{site}: parse returned None"
    assert data.name == expected_name, f"{site}: expected {expected_name!r}, got {data.name!r}"
    assert len(data.samples) > 0
