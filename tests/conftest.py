import pytest

from tests.testutils.regenerate import regenerate_fixtures


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
    regenerate_fixtures(val, mode)
    pytest.exit("Fixtures regenerated; stopping test run.", returncode=0)
