"""SPOJ problem statement parser.

SPOJ is gated by Cloudflare Turnstile, requiring a headed Patchright browser
to fetch problem pages (headless mode is detected and blocked). The problem
body lives in #problem-body, the title in h2#problem-name, and time/memory
limits in table#problem-meta.

Samples are embedded in a single <pre> under an <h3>Example</h3> heading,
labeled with <b>Input:</b> / <b>Output:</b> (or <strong>), or as plain text
("Sample Input:" / "Sample Output:"). The trailing <h3>Information</h3>
section (forum/cross-reference notes) is stripped.
"""

import re
from typing import override

from bs4 import BeautifulSoup
from bs4.element import Tag

from ...cp_metadata import MathSentinelRegistry, SampleCase, parse_memory_limit, parse_time_limit
from ..lib import BaseParser, extract_math_nodes


def _extract_spoj_samples(soup: BeautifulSoup) -> list[SampleCase]:
    """Extract sample test cases from the labeled <pre> under each Example heading.

    Also decomposes the Example heading and its <pre> so the raw sample text
    does not leak into body_html (which would duplicate the rendered Examples).
    """
    samples: list[SampleCase] = []
    to_remove: list[Tag] = []
    for heading in list(soup.select("#problem-body h3")):
        if heading.get_text(strip=True).lower() != "example":
            continue
        pre = None
        for sibling in heading.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "h3":
                break
            if not isinstance(sibling, Tag):
                continue
            candidate = sibling if sibling.name == "pre" else sibling.find("pre")
            if candidate is not None:
                pre = candidate
                break
        if pre is None:
            continue
        sections: dict[str, str] = {}
        current_label: str | None = None
        for child in pre.children:
            if isinstance(child, Tag) and child.name in ("b", "strong"):
                label = child.get_text(strip=True).lower().rstrip(":")
                current_label = label if label in ("input", "output") else None
            elif current_label is not None:
                sections[current_label] = sections.get(current_label, "") + str(child)
        if "input" not in sections or "output" not in sections:
            lines = pre.get_text().split("\n")
            input_start = None
            output_start = None
            for i, line in enumerate(lines):
                stripped = line.strip()
                if re.search(r"^Sample\s+Input\s*:?\s*$", stripped, re.IGNORECASE):
                    input_start = i + 1
                elif input_start is not None and re.search(r"^Sample\s+Output\s*:?\s*$", stripped, re.IGNORECASE):
                    output_start = i + 1
                    break
            if input_start is not None and output_start is not None:
                sections["input"] = "\n".join(lines[input_start : output_start - 1]).strip()
                sections["output"] = "\n".join(lines[output_start:]).strip()
        if "input" in sections and "output" in sections:
            samples.append(SampleCase(input=sections["input"].strip(), output=sections["output"].strip()))
            to_remove.extend((heading, pre))

    for node in to_remove:
        node.decompose()
    return samples


class SpojParser(BaseParser):
    """Parser for SPOJ problem statements. Headed browser required for Turnstile bypass."""

    site: str = "spoj"
    platform: str = "SPOJ"
    selector: str = "#problem-body"
    headless: bool = False

    @override
    def extract_name(self, soup: BeautifulSoup) -> str | None:
        h2 = soup.select_one("#problem-name")
        return h2.get_text(strip=True) if h2 is not None else None

    @override
    def extract_limits(self, soup: BeautifulSoup) -> tuple[float | None, int | None]:
        table = soup.select_one("#problem-meta")
        if table is None:
            return None, None
        time_limit: float | None = None
        memory_limit: int | None = None
        for tr in table.select("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            label = cells[0].get_text(strip=True).lower().rstrip(":")
            value = cells[1].get_text(strip=True)
            if label == "time limit":
                time_limit = parse_time_limit(value)
            elif label == "memory limit":
                memory_limit = parse_memory_limit(value)
        return time_limit, memory_limit

    @override
    def extract_samples(self, soup: BeautifulSoup) -> list[SampleCase]:
        return _extract_spoj_samples(soup)

    @override
    def normalize(self, soup: BeautifulSoup, name: str | None = None) -> tuple[MathSentinelRegistry, list[SampleCase]]:
        samples = self.extract_samples(soup)

        for heading in list(soup.select("#problem-body h3")):
            if heading.get_text(strip=True).lower() == "information":
                to_remove: list[Tag] = [heading]
                for sibling in heading.find_next_siblings():
                    to_remove.append(sibling)
                for node in to_remove:
                    node.decompose()

        return extract_math_nodes(soup), samples
