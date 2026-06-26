"""CodeChef problem statement parser.

CodeChef's page framework embeds the problem statement inside a component tree that leaves orphaned
boilerplate blocks (recommendations, feedback forms, contributor lists) even after the statement is
rendered. These must be stripped to produce clean output.

Math is rendered via KaTeX with <annotation encoding="application/x-tex"> — the authoritative TeX
source. The surrounding KaTeX visual markup (aria-hidden spans) must be ignored to avoid
concatenating visual-rendering text into the math output.

Practice problems have a public JSON API at /api/contests/PRACTICE/problems/<CODE> that provides
structured sampleTestCases. We replace the Patchright-scraped samples with API data for
practice problems, since the API is the authoritative source for sample test cases.
"""

import json
import re
import urllib.request
from typing import override
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from ...cp_metadata import MathExtractor, ProblemData, SampleCase
from ..lib import BaseParser

_SAMPLE_HEADING_RE = re.compile(r"sample\s*\d+\s*:?\s*$", re.IGNORECASE)


def _extract_codechef_problem_code(url: str) -> str | None:
    """Extract the problem code from a CodeChef practice URL.

    Returns the uppercase problem identifier (e.g. 'START01' from
    /problems/START01) or None if the URL is not a practice problem page.
    Contest problem URLs (/CONTEST/problems/CODE) return None because
    the practice API does not serve contest-specific problem data.
    """
    path = urlparse(url).path.rstrip("/")
    parts = [p for p in path.split("/") if p]
    if len(parts) == 2 and parts[0] == "problems":
        return parts[1]
    return None


def _fetch_codechef_api_samples(problem_code: str) -> list[SampleCase] | None:
    """Fetch sample test cases from the CodeChef practice problem API.

    Returns a list of SampleCase objects or None if the API is unreachable,
    returns a non-success status, or the response is malformed. Deleted
    sample test cases (isDeleted: true) are filtered out.
    """
    api_url = f"https://www.codechef.com/api/contests/PRACTICE/problems/{problem_code}"
    try:
        with urllib.request.urlopen(api_url, timeout=10) as resp:
            data = json.loads(resp.read())
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    if data.get("status") != "success":
        return None
    test_cases = data.get("problemComponents", {}).get("sampleTestCases")
    if not isinstance(test_cases, list):
        return None
    samples: list[SampleCase] = []
    for tc in test_cases:
        if not isinstance(tc, dict) or tc.get("isDeleted", False):
            continue
        inp = tc.get("input")
        out = tc.get("output")
        if isinstance(inp, str) and isinstance(out, str):
            samples.append(SampleCase(input=inp, output=out))
    return samples


def _remove_duplicate_title(soup: BeautifulSoup, problem_name: str) -> None:
    normalized = " ".join(problem_name.strip().lower().split())
    for tag in soup.find_all(["h1", "h2", "h3"], limit=5):
        candidate = " ".join(tag.get_text().lower().split())
        if candidate == normalized:
            tag.decompose()
            return


def _extract_codechef_samples(soup: BeautifulSoup) -> list[SampleCase]:
    samples: list[SampleCase] = []
    for heading in list(soup.find_all("h3")):
        if _SAMPLE_HEADING_RE.match(heading.get_text(strip=True)) is None:
            continue
        table = heading.find_next_sibling(class_=re.compile(r"_input_output__table_"))
        if table is not None:
            pres = table.select('[class*="_values_"] pre')
            if len(pres) >= 2:
                samples.append(SampleCase(input=pres[0].get_text(), output=pres[1].get_text()))
            table.decompose()
        heading.decompose()
    return samples


class CodeChefParser(BaseParser):
    """Parser for CodeChef problem statements. Strips component boilerplate and uses KaTeX annotation math."""

    site: str = "codechef"
    platform: str = "CodeChef"
    selector: str = "#problem-statement"

    @override
    def extract_name(self, soup: BeautifulSoup) -> str | None:
        h3 = soup.select_one("#problem-statement h3")
        return h3.get_text(strip=True) if h3 is not None else None

    @override
    def extract_limits(self, soup: BeautifulSoup) -> tuple[float | None, int | None]:
        time_limit: float | None = None
        memory_limit: int | None = None
        for span in soup.find_all("span"):
            label = span.get_text(strip=True).lower()
            if label not in ("time limit", "memory limit"):
                continue
            # Read the value from the sibling span rather than parent.get_text(),
            # which would concatenate all text with case mismatches.
            value_span = span.find_next_sibling("span")
            if value_span is None:
                continue
            value_str = value_span.get_text(strip=True)
            if label == "time limit":
                time_limit = self.parse_time_limit(value_str)
            else:
                memory_limit = self.parse_memory_limit(value_str)
        return time_limit, memory_limit

    @override
    def normalize(self, soup: BeautifulSoup, name: str | None = None) -> tuple[MathExtractor, list[SampleCase]]:
        samples = _extract_codechef_samples(soup)

        extractor = self.extract_math(soup)
        _remove_duplicate_title(soup, name or "")

        for heading in list(soup.find_all(["h1", "h2", "h3", "h4"])):
            text = heading.get_text(strip=True).lower().rstrip(":")
            if text == "input format":
                heading.string = "Input"
            elif text == "output format":
                heading.string = "Output"
        return extractor, samples

    @override
    def parse(self, url: str) -> ProblemData | None:
        """Fetch and parse a CodeChef problem, enhancing samples via the practice API."""
        data = super().parse(url)
        if data is None:
            return None
        problem_code = _extract_codechef_problem_code(url)
        if problem_code is not None:
            api_samples = _fetch_codechef_api_samples(problem_code)
            if api_samples:
                data.samples = api_samples
        return data
