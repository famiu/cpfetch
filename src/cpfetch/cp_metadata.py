"""Data types, URL dispatch, and utility functions for problem fetching.

Carries ProblemData through the fetch → render pipeline.
"""

import json
import re
import unicodedata
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SampleCase:
    """A single sample test case with input and expected output."""

    input: str
    output: str


class MathExtractor:
    """Generates unique sentinel keys for math expressions during DOM walking.

    After extraction, only .mapping (a plain dict) is stored on ProblemData.
    The extractor instance itself is discarded.
    """

    def __init__(self) -> None:
        self.mapping: dict[str, str] = {}
        self._counter: int = 0

    def add(self, latex: str) -> str:
        """Register a LaTeX expression and return its sentinel key."""
        key = f"XX-MATH-{self._counter}-XX"
        self.mapping[key] = latex
        self._counter += 1
        return key


@dataclass
class ProblemData:
    """Aggregated data for a single problem statement."""

    name: str
    site: str
    platform: str
    url: str
    time_limit: float | None
    memory_limit: int | None
    samples: list[SampleCase]
    body_html: str
    math: dict[str, str] = field(default_factory=dict)


_HOST_SITES: dict[str, str] = {
    "codeforces.com": "codeforces",
    "atcoder.jp": "atcoder",
    "cses.fi": "cses",
    "codechef.com": "codechef",
}


def site_from_url(url: str) -> str:
    """Extract a short site identifier from a problem URL."""
    host = urllib.parse.urlparse(url).hostname or ""
    for domain, site in _HOST_SITES.items():
        if host == domain or host.endswith("." + domain):
            return site
    return "unknown"


def slugify(text: str) -> str:
    """Convert arbitrary text into a filesystem-safe slug, falling back to 'problem'."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "_", text)
    return text.strip("_") or "problem"


def restore_math(text: str, math_map: dict[str, str]) -> str:
    """Replace sentinel keys in *text* with the original LaTeX from *math_map*."""
    if not math_map:
        return text
    pattern = re.compile("|".join(re.escape(k) for k in sorted(math_map, key=len, reverse=True)))
    return pattern.sub(lambda m: math_map[m.group(0)], text)


_META_FILE = ".meta.json"


def save_meta_json(directory: Path, url: str) -> None:
    """Write a .meta.json file tracking which URL was fetched into *directory*."""
    meta_path = directory / _META_FILE
    _ = meta_path.write_text(json.dumps({"url": url}, indent=2) + "\n", encoding="utf-8")


def load_meta_url(directory: Path) -> str | None:
    """Read the URL stored in a .meta.json file under *directory*."""
    meta_path = directory / _META_FILE
    if not meta_path.exists():
        return None
    try:
        raw: object = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(raw, dict):
        url: object = raw.get("url")
        if isinstance(url, str):
            return url
    return None
