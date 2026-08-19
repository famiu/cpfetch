"""HackerRank problem statement parser.

HackerRank renders samples as paired ``challenge_sample_input`` and
``challenge_sample_output`` blocks. The page's legacy MathJax renderer embeds
large SVGs without TeX source, so those nodes are removed from the statement.
"""

from typing import override

from bs4 import BeautifulSoup
from bs4.element import Tag

from ...cp_metadata import MathSentinelRegistry, SampleCase
from ..lib import BaseParser, extract_math_nodes


def _sample_body(section: Tag, selector: str) -> str | None:
    body = section.select_one(selector)
    if body is None:
        return None
    return body.get_text()


def _extract_hackerrank_samples(soup: BeautifulSoup) -> list[SampleCase]:
    """Extract and remove paired HackerRank sample input and output blocks."""
    inputs = list(soup.select(".challenge_sample_input"))
    outputs = list(soup.select(".challenge_sample_output"))
    samples: list[SampleCase] = []
    for input_section, output_section in zip(inputs, outputs, strict=False):
        sample_input = _sample_body(input_section, ".challenge_sample_input_body")
        sample_output = _sample_body(output_section, ".challenge_sample_output_body")
        if sample_input is None or sample_output is None:
            continue
        samples.append(SampleCase(input=sample_input.strip(), output=sample_output.strip()))
        input_section.decompose()
        output_section.decompose()
    return samples


class HackerRankParser(BaseParser):
    """Parser for HackerRank challenge problem statements."""

    site: str = "hackerrank"
    platform: str = "HackerRank"
    selector: str = ".challenge-body-html"

    @override
    def extract_name(self, soup: BeautifulSoup) -> str | None:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title is not None:
            content = og_title.get("content")
            if isinstance(content, str) and content.strip():
                return content.removesuffix(" | HackerRank").strip()
        if soup.title is not None:
            title = soup.title.get_text(strip=True)
            if title:
                return title.removesuffix(" | HackerRank").strip()
        title = soup.select_one("h1.page-label")
        return title.get_text(strip=True) if title is not None else None

    @override
    def extract_samples(self, soup: BeautifulSoup) -> list[SampleCase]:
        return _extract_hackerrank_samples(soup)

    @override
    def normalize(self, soup: BeautifulSoup) -> tuple[MathSentinelRegistry, list[SampleCase]]:
        samples = self.extract_samples(soup)
        for node in soup.select("style, svg, .MathJax_SVG"):
            node.decompose()
        return extract_math_nodes(soup), samples
