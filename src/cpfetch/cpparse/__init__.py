"""Per-platform problem statement parsers.

The get_parser(url, fetcher) factory dispatches to the correct platform parser by extracting the
site key from the URL hostname. Each subclass of BaseParser encapsulates DOM extraction
and normalization logic specific to one judge — Codeforces, CodeChef, CSES, or AtCoder.
"""

from ..cp_metadata import site_from_url
from .fetch import BrowserFetch
from .lib import BaseParser, render_markdown
from .platforms import AtCoderParser, CodeChefParser, CodeforcesParser, CsesParser, SpojParser

__all__ = ["get_parser", "render_markdown"]

_PARSERS: dict[str, type[BaseParser]] = {
    "codeforces": CodeforcesParser,
    "codechef": CodeChefParser,
    "cses": CsesParser,
    "atcoder": AtCoderParser,
    "spoj": SpojParser,
}


def get_parser(url: str, fetcher: BrowserFetch | None = None) -> BaseParser | None:
    site = site_from_url(url)
    cls = _PARSERS.get(site)
    if cls is None:
        return None
    return cls(fetcher)
