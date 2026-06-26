"""Codeforces problem statement parser.

Codeforces renders math in three possible forms:
1. <script type="math/tex"> elements (Patchright-hydrated MathJax v2)
2. <span class="tex-span"> elements (static HTML)
3. Bare $...$ delimiters inside text nodes (legacy fallback)

We handle all three in priority order: MathJax scripts first, then tex-span elements, then fall back
to dollar-sign text-node scanning. Section titles are converted to <h2> after math extraction so
.get_text() sees clean text.
"""

from typing import override
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from bs4.element import Tag

from ...cp_metadata import MathSentinelRegistry, SampleCase, parse_memory_limit, parse_time_limit
from ..lib import BaseParser, space_latex_commands

_SKIP_ANCESTORS = {"pre", "code", "script", "style"}


def _extract_tex_span_math(soup: BeautifulSoup, extractor: MathSentinelRegistry) -> None:
    for node in soup.select("span.tex-span"):
        text = node.get_text().strip().replace("\u2009", " ")
        _ = node.replace_with(extractor.add(f"${space_latex_commands(text)}$"))


def _extract_mathjax_nodes(soup: BeautifulSoup, extractor: MathSentinelRegistry) -> None:
    scripts = soup.select('script[type^="math/tex"]')
    if not scripts:
        return
    # Remove visual-rendering MathJax elements that duplicate the script source.
    for noise in soup.select(".MathJax, .MathJax_Preview, .MathJax_Display"):
        noise.decompose()
    for script in scripts:
        raw = script.string or ""
        processed = space_latex_commands(raw)
        is_display = "mode=display" in (script.get("type") or "")
        delim = "$$" if is_display else "$"
        _ = script.replace_with(extractor.add(f"{delim}{processed}{delim}"))


def _extract_raw_dollar_math(soup: BeautifulSoup, extractor: MathSentinelRegistry) -> None:
    """Extract bare $...$ math by walking DOM text nodes.

    A global regex on the raw HTML string would corrupt the tree structure.
    Manual iteration preserves the BeautifulSoup parse tree.
    """
    for text_node in list(soup.find_all(string=True)):
        if any(a.name in _SKIP_ANCESTORS for a in text_node.parents):
            continue

        s = str(text_node)
        parts: list[str] = []

        i = 0
        while i < len(s):
            if s[i] != "$":
                j = s.find("$", i)
                if j == -1:
                    parts.append(s[i:])
                    break
                parts.append(s[i:j])
                i = j
                continue

            j = i
            while j < len(s) and s[j] == "$":
                j += 1
            delim = s[i:j]
            end = s.find(delim, j)
            if end == -1:
                parts.append(s[i:])
                break

            raw = s[j:end]
            processed = space_latex_commands(raw)
            parts.append(extractor.add(f"{delim}{processed}{delim}"))
            i = end + len(delim)

        if parts != [s]:
            _ = text_node.replace_with("".join(parts))


def _pre_text(pre: Tag) -> str:
    return pre.get_text(separator="\n").strip()


def _extract_cf_samples(soup: BeautifulSoup) -> list[SampleCase]:
    samples: list[SampleCase] = []
    for test in soup.select(".sample-tests .sample-test"):
        inp = test.select_one(".input pre")
        out = test.select_one(".output pre")
        if inp is not None and out is not None:
            samples.append(SampleCase(input=_pre_text(inp), output=_pre_text(out)))
    return samples


class CodeforcesParser(BaseParser):
    """Parser for Codeforces problem statements. Uses raw $...$ delimiter scanning for math."""

    site: str = "codeforces"
    platform: str = "Codeforces"
    selector: str = ".problem-statement"
    _strip_trailing: bool = False

    @override
    def extract_name(self, soup: BeautifulSoup) -> str | None:
        title = soup.select_one(".problem-statement .header .title")
        return title.get_text(strip=True) if title is not None else None

    @override
    def extract_limits(self, soup: BeautifulSoup) -> tuple[float | None, int | None]:
        header = soup.select_one(".problem-statement .header")
        if header is None:
            return None, None

        time_limit: float | None = None
        memory_limit: int | None = None
        t_el = header.select_one(".time-limit")
        if t_el is not None:
            text = t_el.get_text(strip=True)
            # Strip the property-title label prefix without mutating the tree.
            for pt in t_el.select(".property-title"):
                text = text.removeprefix(pt.get_text(strip=True)).strip()
            time_limit = parse_time_limit(text)
        m_el = header.select_one(".memory-limit")
        if m_el is not None:
            text = m_el.get_text(strip=True)
            for pt in m_el.select(".property-title"):
                text = text.removeprefix(pt.get_text(strip=True)).strip()
            memory_limit = parse_memory_limit(text)
        return time_limit, memory_limit

    @override
    def _fallback_id_from_url(self, url: str) -> str | None:
        """Concatenate contest number + problem letter (e.g. /contest/123/problem/A → "123A")."""
        segments = [s for s in urlparse(url).path.split("/") if s]
        if not segments:
            return None
        letter = segments[-1]
        for segment in reversed(segments[:-1]):
            if segment.isdigit():
                return segment + letter
        return letter

    @override
    def extract_math(self, soup: BeautifulSoup) -> MathSentinelRegistry:
        extractor = MathSentinelRegistry()
        _extract_mathjax_nodes(soup, extractor)
        _extract_tex_span_math(soup, extractor)
        _extract_raw_dollar_math(soup, extractor)
        return extractor

    @override
    def normalize(self, soup: BeautifulSoup, name: str | None = None) -> tuple[MathSentinelRegistry, list[SampleCase]]:
        samples = _extract_cf_samples(soup)

        header = soup.select_one(".problem-statement > .header")
        if header is not None:
            header.decompose()

        for node in soup.select(".sample-tests"):
            node.decompose()

        extractor = self.extract_math(soup)

        for title in soup.select(".section-title"):
            h2 = soup.new_tag("h2")
            _ = h2.extend(title.contents)
            _ = title.replace_with(h2)

        return extractor, samples
