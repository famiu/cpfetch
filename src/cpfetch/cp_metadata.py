"""Data types, URL dispatch, and utility functions for problem fetching.

Carries ProblemData through the fetch → render pipeline.
"""

import json
import re
import unicodedata
import urllib.parse
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SampleCase:
    """A single sample test case with input and expected output."""

    input: str
    output: str


class MathSentinelRegistry:
    """Mints unique sentinel keys for math expressions during DOM walking.

    After extraction, only .mapping (a plain dict) is stored on ProblemData.
    The registry instance itself is discarded.
    """

    def __init__(self) -> None:
        self.mapping: dict[str, str] = {}
        self._counter: int = 0
        self._token: str = uuid.uuid4().hex[:8]

    def add(self, latex: str) -> str:
        """Register a LaTeX expression and return its sentinel key."""
        key = f"XX-MATH-{self._counter}-{self._token}-XX"
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
    "spoj.com": "spoj",
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


_TIME_MS_RE: re.Pattern[str] = re.compile(r"([\d.]+)\s*(ms|milliseconds?)\b", re.IGNORECASE)
_TIME_S_RE: re.Pattern[str] = re.compile(r"([\d.]+)\s*(seconds?|secs|sec|s)\b", re.IGNORECASE)
_MEM_RE: re.Pattern[str] = re.compile(r"([\d.]+)\s*(gigabytes?|GiB|GB|megabytes?|MiB|MB)\b", re.IGNORECASE)


def parse_time_limit(text: str) -> float | None:
    """Extract time limit from a text string and return it in milliseconds.

    Handles values like "2 seconds", "500 ms", "1.5 sec". Returns None
    if no time limit is found.
    """
    m = _TIME_MS_RE.search(text)
    if m:
        return float(m.group(1))
    m = _TIME_S_RE.search(text)
    if m:
        return float(m.group(1)) * 1000
    return None


def parse_memory_limit(text: str) -> int | None:
    """Extract memory limit from a text string and return it in megabytes.

    Handles values like "256 MB", "1 GB", "512 MiB". Returns None if
    no memory limit is found. Gigabyte values are multiplied by 1024.
    """
    m = _MEM_RE.search(text)
    if not m:
        return None
    value = float(m.group(1))
    if m.group(2).lower().startswith("g"):
        value *= 1024
    return round(value)


_META_FILE = "meta.json"


def save_meta_json(directory: Path, data: ProblemData) -> None:
    """Write a meta.json file with problem metadata into *directory*."""
    meta_path = directory / _META_FILE
    payload = {
        "version": 1,
        "url": data.url,
        "name": data.name,
        "site": data.site,
        "platform": data.platform,
        "time_limit": data.time_limit,
        "memory_limit": data.memory_limit,
    }
    _ = meta_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def load_meta_url(directory: Path) -> str | None:
    """Read the URL stored in a meta.json file under *directory*."""
    meta_path = directory / _META_FILE
    if not meta_path.exists():
        return None
    try:
        raw = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if isinstance(raw, dict):
        url = raw.get("url")
        if isinstance(url, str):
            return url
    return None
