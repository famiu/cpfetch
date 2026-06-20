"""CodeChef problem statement parser.

CodeChef's page framework embeds the problem statement inside a component tree that leaves orphaned
boilerplate blocks (recommendations, feedback forms, contributor lists) even after the statement is
rendered. These must be stripped to produce clean output.

Math is rendered via KaTeX with <annotation encoding="application/x-tex"> — the authoritative TeX
source. The surrounding KaTeX visual markup (aria-hidden spans) must be ignored to avoid
concatenating visual-rendering text into the math output.
"""

import re
from typing import override

from bs4 import BeautifulSoup

from ...cp_metadata import MathExtractor, SampleCase
from ..lib import BaseParser

_SAMPLE_HEADING_RE = re.compile(r"sample\s*\d+\s*:?\s*$", re.IGNORECASE)


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
