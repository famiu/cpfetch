"""Unit tests for cpfetch.cpparse.lib — base parser, math extraction, rendering."""

import typing

from bs4 import BeautifulSoup

from cpfetch.cp_metadata import MathSentinelRegistry, ProblemData, SampleCase
from cpfetch.cpparse.lib import (
    BaseParser,
    as_code_block,
    fmt_time,
    is_section_heading,
    render_markdown,
    space_latex_commands,
)


class TestSpaceLatexCommands:
    def test_basic_command(self):
        assert space_latex_commands(r"\le n") == r"\le{} n"

    def test_no_command(self):
        assert space_latex_commands("plain text") == "plain text"

    def test_multiple_commands(self):
        assert space_latex_commands(r"\le n \ge m") == r"\le{} n \ge{} m"

    def test_command_at_end(self):
        assert space_latex_commands(r"abc \le") == r"abc \le"


class TestIsSectionHeading:
    def test_input(self):
        assert is_section_heading("Input") is True

    def test_output(self):
        assert is_section_heading("Output") is True

    def test_constraints(self):
        assert is_section_heading("Constraints") is True

    def test_sample(self):
        assert is_section_heading("Sample 1") is True

    def test_example(self):
        assert is_section_heading("Example") is True

    def test_note(self):
        assert is_section_heading("Note") is True

    def test_scoring(self):
        assert is_section_heading("Scoring") is True

    def test_editorial(self):
        assert is_section_heading("Editorial") is True

    def test_hint(self):
        assert is_section_heading("Hint") is True

    def test_explanation(self):
        assert is_section_heading("Explanation") is True

    def test_case_insensitive(self):
        assert is_section_heading("input") is True
        assert is_section_heading("INPUT") is True

    def test_strips_colon(self):
        assert is_section_heading("Input:") is True

    def test_generic_text(self):
        assert is_section_heading("Some random heading") is False

    def test_empty_string(self):
        assert is_section_heading("") is False


class TestAsCodeBlock:
    def test_basic(self):
        result = as_code_block("hello")
        assert result == "```\nhello\n```"

    def test_multi_line(self):
        result = as_code_block("line1\nline2")
        assert result == "```\nline1\nline2\n```"

    def test_empty_string(self):
        result = as_code_block("")
        assert result == "```\n\n```"

    def test_avoids_fence_collision(self):
        result = as_code_block("```")
        assert result == "````\n```\n````"

    def test_trailing_text_stays(self):
        result = as_code_block("hello\n")
        assert result == "```\nhello\n\n```"

    def test_longer_backtick_run(self):
        result = as_code_block("````")
        assert result == "`````\n````\n`````"


class TestFmtTime:
    def test_basic(self) -> None:
        assert fmt_time(1000.0) == "1 s"

    def test_decimal(self) -> None:
        assert fmt_time(1500.0) == "1.5 s"

    def test_milliseconds(self) -> None:
        assert fmt_time(500.0) == "0.5 s"

    def test_zero(self) -> None:
        assert fmt_time(0.0) == "0 s"

    def test_negative_clamped(self) -> None:
        assert fmt_time(-100.0) == "0 s"

    def test_sub_ms_avoids_sci_notation(self) -> None:
        result = fmt_time(0.0001)
        assert "e" not in result
        assert "ms" in result


class TestRenderMarkdownEdgeCases:
    def test_no_limits_no_samples(self) -> None:
        data = ProblemData(
            name="Minimal Problem",
            site="test",
            platform="Test",
            url="https://example.com",
            time_limit=None,
            memory_limit=None,
            samples=[],
            body_html="<p>Just a description.</p>",
        )
        md = render_markdown(data)
        assert "# Minimal Problem" in md
        assert "Time limit:" not in md
        assert "Memory limit:" not in md
        assert "## Examples" not in md
        assert "Source: [Test]" in md

    def test_math_restoration(self) -> None:
        data = ProblemData(
            name="Math Problem",
            site="test",
            platform="Test",
            url="https://example.com",
            time_limit=1000.0,
            memory_limit=256,
            samples=[],
            body_html="<p>Value of XX-MATH-0-abcdef12-XX is important.</p>",
            math={"XX-MATH-0-abcdef12-XX": "$x^2$"},
        )
        md = render_markdown(data)
        assert "$x^2$" in md
        assert "XX-MATH-" not in md

    def test_multiple_samples(self) -> None:
        data = ProblemData(
            name="Multi Sample",
            site="test",
            platform="Test",
            url="https://example.com",
            time_limit=None,
            memory_limit=None,
            samples=[
                SampleCase(input="1", output="2"),
                SampleCase(input="3", output="4"),
            ],
            body_html="<p>Desc</p>",
        )
        md = render_markdown(data)
        assert "### Example 1" in md
        assert "### Example 2" in md
        assert "```\n1\n```" in md
        assert "```\n3\n```" in md


class TestPostNormalize:
    """Verify that post_normalize runs after heading normalization and trailing strip."""

    def test_post_normalize_runs_after_heading_normalization(self) -> None:
        received_soup: list[BeautifulSoup] = []

        class TrackingParser(BaseParser):
            selector = "div"
            _strip_trailing = True
            call_order: typing.ClassVar[list[str]] = []

            def extract_name(self, soup: BeautifulSoup) -> str | None:
                return "Test"

            def normalize(self, soup: BeautifulSoup) -> tuple[MathSentinelRegistry, list[SampleCase]]:
                self.call_order.append("normalize")
                return MathSentinelRegistry(), []

            def post_normalize(self, soup: BeautifulSoup, name: str) -> None:
                self.call_order.append("post_normalize")
                received_soup.append(soup)

        parser = TrackingParser()
        html = "<div><h3>Input</h3><p>data</p><hr></div>"
        _ = parser.extract_data(html, "https://example.com/test")
        assert parser.call_order == ["normalize", "post_normalize"]
        assert len(received_soup) == 1
        soup = received_soup[0]
        # Heading normalization: <h3>Input</h3> was converted to <h2> before post_normalize ran.
        assert soup.find("h3") is None
        h2 = soup.find("h2")
        assert h2 is not None
        assert h2.get_text(strip=True) == "Input"
        # Trailing separator strip: the <hr> was removed before post_normalize ran.
        assert soup.find("hr") is None

    def test_post_normalize_receives_name(self) -> None:
        received_name: list[str] = []

        class NameCheckerParser(BaseParser):
            selector = "div"
            _strip_trailing = False

            def extract_name(self, soup: BeautifulSoup) -> str | None:
                return "My Problem"

            def normalize(self, soup: BeautifulSoup) -> tuple[MathSentinelRegistry, list[SampleCase]]:
                return MathSentinelRegistry(), []

            def post_normalize(self, soup: BeautifulSoup, name: str) -> None:
                received_name.append(name)

        parser = NameCheckerParser()
        _ = parser.extract_data("<div><p>data</p></div>", "https://example.com/test")
        assert received_name == ["My Problem"]
