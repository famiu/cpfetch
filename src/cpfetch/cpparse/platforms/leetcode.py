"""LeetCode problem statement parser.

LeetCode embeds examples in the description rather than exposing conventional
stdin/stdout sample tables. Their ``Input:`` and ``Output:`` fields are parsed
for Markdown rendering, but are not written as stdin-based sample files.
"""

import re
from typing import override
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from bs4.element import Tag

from ...cp_metadata import MathSentinelRegistry, SampleCase
from ..lib import BaseParser

_SAMPLE_RE = re.compile(
    r"\bInput:\s*(.*?)\s*\bOutput:\s*(.*?)(?:\s*\bExplanation:|\s*\bConstraints:|$)",
    re.IGNORECASE | re.DOTALL,
)


def _extract_leetcode_samples(soup: BeautifulSoup) -> list[SampleCase]:
    samples: list[SampleCase] = []
    labels_with_explanations: set[int] = set()
    for pre in list(soup.find_all("pre")):
        match = _SAMPLE_RE.search(pre.get_text("", strip=False))
        if match is None:
            continue
        samples.append(SampleCase(input=match.group(1).strip(), output=match.group(2).strip()))

        explanation = next(
            (
                marker
                for marker in pre.find_all(["strong", "b"])
                if marker.get_text(strip=True).lower().rstrip(":") == "explanation"
            ),
            None,
        )
        if explanation is None:
            pre.decompose()
            continue

        explanation_root = explanation
        while explanation_root.parent is not pre and isinstance(explanation_root.parent, Tag):
            explanation_root = explanation_root.parent
        for child in list(pre.contents):
            if child is explanation_root:
                break
            _ = child.extract()

        label = pre.find_previous("strong", class_="example")
        if label is not None:
            labels_with_explanations.add(id(label))

    # Example labels are separate from their <pre> blocks in LeetCode's HTML.
    for label in list(soup.select("strong.example")):
        if id(label) in labels_with_explanations:
            continue
        parent = label.parent
        if isinstance(parent, Tag) and parent.get_text(strip=True) == label.get_text(strip=True):
            parent.decompose()
        else:
            label.decompose()
    return samples


def _extract_leetcode_math(soup: BeautifulSoup) -> MathSentinelRegistry:
    extractor = MathSentinelRegistry()
    for node in list(soup.select(".katex")):
        if node.parent is None or node.find_parent(class_="katex") is not None:
            continue
        annotation = node.select_one("annotation[encoding='application/x-tex']")
        if annotation is None:
            continue
        latex = annotation.get_text().strip()
        display_parent = node.find_parent(class_="katex-display")
        delimiters = "$$" if display_parent is not None else "$"
        replacement = extractor.add(f"{delimiters}{latex}{delimiters}")
        target = display_parent if display_parent is not None else node
        _ = target.replace_with(replacement)
    return extractor


class LeetCodeParser(BaseParser):
    """Parser for LeetCode's server-rendered problem description."""

    site: str = "leetcode"
    platform: str = "LeetCode"
    selector: str = 'div[data-track-load="description_content"]'
    write_sample_files: bool = False

    @override
    def _fallback_id_from_url(self, url: str) -> str | None:
        segments = [segment for segment in urlparse(url).path.split("/") if segment]
        try:
            problem_index = segments.index("problems")
        except ValueError:
            return super()._fallback_id_from_url(url)
        slug_index = problem_index + 1
        return segments[slug_index] if slug_index < len(segments) else None

    @override
    def extract_name(self, soup: BeautifulSoup) -> str | None:
        og_title = soup.select_one('meta[property="og:title"]')
        if og_title is not None:
            content = og_title.get("content")
            if isinstance(content, str) and content.strip():
                return content.removesuffix(" - LeetCode").strip()
        if soup.title is not None:
            title = soup.title.get_text(strip=True)
            if title:
                return title.removesuffix(" - LeetCode").strip()
        return None

    @override
    def extract_samples(self, soup: BeautifulSoup) -> list[SampleCase]:
        return _extract_leetcode_samples(soup)

    @override
    def normalize(self, soup: BeautifulSoup) -> tuple[MathSentinelRegistry, list[SampleCase]]:
        samples = self.extract_samples(soup)
        return _extract_leetcode_math(soup), samples
