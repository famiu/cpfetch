r"""Base parser template, math extraction, section normalization, and markdown rendering.

markdownify escapes underscores (_ → \\_) in text content, which corrupts inline LaTeX delimiters.
To work around this, math nodes are replaced with sentinel keys before markdownify runs,
then the sentinels are restored as raw $...$ expressions afterward.
"""

import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag
from markdownify import markdownify

from ..cp_metadata import MathExtractor, ProblemData, SampleCase, restore_math
from .fetch import BrowserFetch


def space_latex_commands(text: str) -> str:
    """Append {} after each LaTeX command followed by whitespace to prevent gobbling."""
    return re.sub(r"\\(\w+)(?=\s)", r"\\\1{}", text)


def classify_section_heading(text: str) -> bool:
    """Return True if *text* looks like a section heading (Input, Constraints, etc.)."""
    text = text.strip().lower().rstrip(":")
    prefixes = (
        "input",
        "output",
        "constraint",
        "subtask",
        "sample",
        "example",
        "explanation",
        "note",
        "scoring",
        "editorial",
        "hint",
    )
    return any(text.startswith(p) for p in prefixes)


def _normalize_section_headings(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if classify_section_heading(tag.get_text()):
            tag.name = "h2"


def _extract_semantic_latex(node: Tag) -> str | None:
    """Extract LaTeX from a math element using a three-tier priority.

    Priority:
    1. <annotation encoding="application/x-tex"> — authoritative TeX source (CodeChef KaTeX).
    2. <span.math> — controlled text after stripping aria-hidden visual renderings (CSES).
    3. <var> — simple variable name (AtCoder).
    """
    classes = node.get("class")
    if not isinstance(classes, list):
        classes = []

    annotation = node.select_one("annotation[encoding='application/x-tex']")
    if annotation is not None:
        latex = space_latex_commands(annotation.get_text().strip())
        is_display = "math-display" in classes or "katex-display" in classes
        return f"$${latex}$$" if is_display else f"${latex}$"

    if node.name == "span" and "math" in classes:
        for hidden in list(node.select('[aria-hidden="true"]')):
            hidden.decompose()
        raw = space_latex_commands(node.get_text().strip())
        is_display = "math-display" in classes
        return f"$${raw}$$" if is_display else f"${raw}$"

    if node.name == "var":
        return f"${space_latex_commands(node.get_text().strip())}$"

    return None


def extract_math_nodes(soup: BeautifulSoup) -> MathExtractor:
    """Scan for element-based math nodes (span.math, var) and replace them with sentinel keys.

    This is the default math extraction path used by CSES, AtCoder, and CodeChef.
    Codeforces uses a separate dollar-scan path (see codeforces.py) instead.
    """
    extractor = MathExtractor()

    for node in soup.select("span.math, var"):
        if node.parent is None:
            continue
        latex = _extract_semantic_latex(node)
        if latex is not None:
            _ = node.replace_with(extractor.add(latex))

    return extractor


class BaseParser:
    """Template for fetching, parsing, and normalizing a problem statement.

    Subclasses configure:
      - site, platform: identifiers for dispatch and display.
      - selector: CSS selector for the problem body element on the page.
      - extract_name: extract problem title from full-page soup.
      - extract_limits: extract time/memory limits from full-page soup.
      - normalize: process the body element soup (harvest samples, strip boilerplate, extract math).
      - _strip_trailing: whether to strip trailing <hr> and empty containers after normalization.
        Set to False in subclasses that handle boilerplate stripping themselves.
    """

    site: str = ""
    platform: str = ""
    selector: str = ""
    headless: bool = True
    _strip_trailing: bool = True

    def __init__(self, fetcher: BrowserFetch | None = None) -> None:
        self._fetcher = fetcher

    _TIME_MS_RE: re.Pattern[str] = re.compile(r"([\d.]+)\s*(ms|milliseconds?)\b", re.IGNORECASE)
    _TIME_S_RE: re.Pattern[str] = re.compile(r"([\d.]+)\s*(seconds?|secs|sec|s)\b", re.IGNORECASE)
    _MEM_RE: re.Pattern[str] = re.compile(r"([\d.]+)\s*(gigabytes?|GiB|GB|megabytes?|MiB|MB)\b", re.IGNORECASE)

    @staticmethod
    def parse_time_limit(text: str) -> float | None:
        """Extract time limit from a text string and return it in milliseconds.

        Handles values like "2 seconds", "500 ms", "1.5 sec". Returns None
        if no time limit is found.
        """
        m = BaseParser._TIME_MS_RE.search(text)
        if m:
            return float(m.group(1))
        m = BaseParser._TIME_S_RE.search(text)
        if m:
            return float(m.group(1)) * 1000
        return None

    @staticmethod
    def parse_memory_limit(text: str) -> int | None:
        """Extract memory limit from a text string and return it in megabytes.

        Handles values like "256 MB", "1 GB", "512 MiB". Returns None if
        no memory limit is found. Gigabyte values are multiplied by 1024.
        """
        m = BaseParser._MEM_RE.search(text)
        if not m:
            return None
        value = float(m.group(1))
        if m.group(2).lower().startswith("g"):
            value *= 1024
        return round(value)

    @staticmethod
    def _strip_trailing_separators(soup: BeautifulSoup) -> None:
        """Remove trailing <hr> and empty containers, stopping at media elements.

        The method first walks into the deepest single-child chain to find the
        innermost container that holds problem content. It then strips trailing
        nodes (empty tags, whitespace strings, <hr> elements) from that container
        in reverse order, stopping at the first meaningful element or a media tag
        (img, svg, video, canvas).
        """
        _media_tags = frozenset({"img", "svg", "video", "canvas"})
        target: Tag = soup
        while len(target.contents) == 1 and isinstance(target.contents[0], Tag):
            target = target.contents[0]
        while target.contents:
            last = target.contents[-1]
            if isinstance(last, Tag) and last.name == "hr":
                last.decompose()
            elif isinstance(last, NavigableString) and not str(last).strip():
                _ = last.extract()
            elif isinstance(last, Tag) and not last.get_text(strip=True):
                if last.name in _media_tags:
                    break
                last.decompose()
            else:
                break

    def _fallback_id_from_url(self, url: str) -> str | None:
        segments = [s for s in urlparse(url).path.split("/") if s]
        return segments[-1] if segments else None

    def fetch_page(self, url: str) -> str | None:
        """Fetch the problem page HTML via the browser and return it."""
        if self._fetcher is None:
            raise RuntimeError("No BrowserFetch injected; construct the parser via get_parser(url, fetcher).")
        return self._fetcher.fetch(url, self.selector, headless=self.headless)

    def extract_name(self, soup: BeautifulSoup) -> str | None:
        """Extract the problem title from the full-page soup. Subclasses override."""
        return None

    def extract_limits(self, soup: BeautifulSoup) -> tuple[float | None, int | None]:
        """Extract time and memory limits from the full-page soup. Subclasses override."""
        return None, None

    def extract_math(self, soup: BeautifulSoup) -> MathExtractor:
        """Find math nodes in *soup* and replace them with sentinel keys."""
        return extract_math_nodes(soup)

    def normalize(self, soup: BeautifulSoup, name: str | None = None) -> tuple[MathExtractor, list[SampleCase]]:
        """Clean up *soup* and return its math extractor and sample cases. Subclasses override."""
        return self.extract_math(soup), []

    def extract_data(self, html: str, url: str) -> ProblemData | None:
        """Parse full-page HTML into a ProblemData without fetching."""
        full_soup = BeautifulSoup(html, "html.parser")
        body_elem = full_soup.select_one(self.selector)
        if body_elem is None:
            return None

        name = self.extract_name(full_soup) or self._fallback_id_from_url(url) or "Unknown Problem"
        time_limit, memory_limit = self.extract_limits(full_soup)

        body_soup = BeautifulSoup("", "html.parser")
        _ = body_soup.append(body_elem)  # reparents — full_soup no longer owns body_elem
        extractor, samples = self.normalize(body_soup, name)
        _normalize_section_headings(body_soup)
        if self._strip_trailing:
            self._strip_trailing_separators(body_soup)

        return ProblemData(
            name=name,
            site=self.site,
            platform=self.platform,
            url=url,
            time_limit=time_limit,
            memory_limit=memory_limit,
            samples=samples,
            body_html=str(body_soup),
            math=extractor.mapping,
        )

    def parse(self, url: str) -> ProblemData | None:
        """Fetch problem page, extract metadata + body, return ProblemData.

        Note: extract_name / extract_limits receive the *full* page soup (titles and
        limits often live outside the selector-scoped body), while normalize receives
        only the body element (self.selector). See individual platform parsers.
        """
        html = self.fetch_page(url)
        if html is None:
            return None
        return self.extract_data(html, url)


def fmt_time(ms: float) -> str:
    """Format a time in milliseconds as a human-readable string (e.g. '1.5 s')."""
    ms = max(0.0, ms)
    return f"{ms / 1000:g} s"


def as_code_block(text: str) -> str:
    """Wrap *text* in a Markdown code fence, adjusting the fence length if needed."""
    fence = "```"
    while fence in text:
        fence += "`"
    return f"{fence}\n{text}\n{fence}"


def render_markdown(data: ProblemData) -> str:
    """Render a ProblemData as a complete Markdown file."""
    limits: list[str] = []
    if data.time_limit is not None:
        limits.append(f"**Time limit:** {fmt_time(data.time_limit)}")
    if data.memory_limit is not None:
        limits.append(f"**Memory limit:** {data.memory_limit} MB")
    limits.append(f"**Platform**: {data.platform}")

    limits_str = " | ".join(limits)
    body_md = markdownify(data.body_html, heading_style="ATX").strip()
    body_md = restore_math(body_md, data.math)

    lines = [f"# {data.name}", "", limits_str, "", "---", "", body_md]

    if data.samples:
        lines.extend(["", "## Examples", ""])
        for i, sample in enumerate(data.samples, 1):
            lines.append(f"### Example {i}")
            lines.append("")
            lines.append("**Input:**")
            lines.append("")
            lines.append(as_code_block(sample.input.rstrip()))
            lines.append("")
            lines.append("**Output:**")
            lines.append("")
            lines.append(as_code_block(sample.output.rstrip()))
            lines.append("")

    lines.extend(["---", "", f"*Source: [{data.platform}]({data.url})*"])
    return "\n".join(lines)
