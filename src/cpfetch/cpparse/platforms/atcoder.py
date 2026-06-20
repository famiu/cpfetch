"""AtCoder problem statement parser.

AtCoder embeds both Japanese and English in the page under <span class="lang-ja"> and
<span class="lang-en"> respectively. We target .lang-en to get the English version exclusively.
Math is in <var> and <span class="math"> elements, handled by the default extract_math_nodes path.
The inline Sample Input / Sample Output sections are stripped to avoid duplication with the
structured Examples rendered at the bottom of problem.md.
"""

import re
from typing import override

from bs4 import BeautifulSoup

from ...cp_metadata import MathExtractor, SampleCase
from ..lib import BaseParser, extract_math_nodes

_SAMPLE_RE = re.compile(r"Sample (Input|Output)\s*(\d+)", re.IGNORECASE)


def _extract_atcoder_samples(soup: BeautifulSoup) -> list[SampleCase]:
    inputs: dict[int, str] = {}
    outputs: dict[int, str] = {}
    for part in list(soup.select("div.part")):
        section = part.find("section")
        if section is None:
            continue
        h3 = section.find("h3")
        if h3 is None:
            continue
        m = _SAMPLE_RE.match(h3.get_text(strip=True))
        if m is None:
            continue
        kind, idx = m.group(1).lower(), int(m.group(2))
        pre = section.find("pre")
        text = pre.get_text() if pre is not None else ""
        if kind == "input":
            inputs[idx] = text
        else:
            outputs[idx] = text
        part.decompose()
    return [SampleCase(input=inputs[i], output=outputs[i]) for i in sorted(inputs) if i in outputs]


class AtCoderParser(BaseParser):
    """Parser for AtCoder problem statements. English-only, inline samples stripped."""

    site: str = "atcoder"
    platform: str = "AtCoder"
    selector: str = "#task-statement .lang-en"

    @override
    def extract_name(self, soup: BeautifulSoup) -> str | None:
        h2 = soup.select_one("span.h2")
        if h2 is None:
            return None
        return next(h2.stripped_strings, None)

    @override
    def extract_limits(self, soup: BeautifulSoup) -> tuple[float | None, int | None]:
        statement = soup.select_one("#task-statement")
        if statement is None:
            return None, None
        p = statement.find_previous("p")
        if p is None:
            return None, None
        text = p.get_text()
        return self.parse_time_limit(text), self.parse_memory_limit(text)

    @override
    def normalize(self, soup: BeautifulSoup, name: str | None = None) -> tuple[MathExtractor, list[SampleCase]]:
        samples = _extract_atcoder_samples(soup)
        score_tag = soup.find("p")
        if score_tag is not None and score_tag.get_text(strip=True).lower().startswith("score"):
            score_tag.decompose()
        for heading in list(soup.find_all(["h1", "h2", "h3", "h4"])):
            if heading.get_text(strip=True).lower() in (
                "problem statement",
                "problem description",
            ):
                heading.decompose()
        for hr in list(soup.select("hr")):
            hr.decompose()
        return extract_math_nodes(soup), samples
