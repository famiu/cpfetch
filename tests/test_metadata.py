import json
from unittest.mock import patch

from bs4 import BeautifulSoup

from cpfetch.cp_metadata import (
    MathExtractor,
    ProblemData,
    SampleCase,
    load_meta_url,
    restore_math,
    save_meta_json,
    site_from_url,
    slugify,
)
from cpfetch.cpparse.lib import (
    BaseParser,
    as_code_block,
    classify_section_heading,
    fmt_time,
    render_markdown,
    space_latex_commands,
)
from cpfetch.cpparse.platforms.codechef import (
    CodeChefParser,
    _extract_codechef_problem_code,
    _fetch_codechef_api_samples,
)
from cpfetch.cpparse.platforms.codeforces import CodeforcesParser
from cpfetch.cpparse.platforms.cses import _extract_cses_samples


class TestSiteFromUrl:
    def test_exact_match(self):
        assert site_from_url("https://codeforces.com/problemset/problem/1/A") == "codeforces"

    def test_subdomain_match(self):
        assert site_from_url("https://mirror.codeforces.com/problemset/1/A") == "codeforces"

    def test_atcoder(self):
        assert site_from_url("https://atcoder.jp/contests/abc233/tasks/abc233_a") == "atcoder"

    def test_cses(self):
        assert site_from_url("https://cses.fi/problemset/task/1083") == "cses"

    def test_codechef(self):
        assert site_from_url("https://www.codechef.com/problems/FLOW006") == "codechef"

    def test_unknown(self):
        assert site_from_url("https://example.com/problem/1") == "unknown"

    def test_empty_url(self):
        assert site_from_url("") == "unknown"


class TestSlugify:
    def test_basic(self):
        assert slugify("Missing Number") == "missing_number"

    def test_mixed_case(self):
        assert slugify("Theatre Square") == "theatre_square"

    def test_special_chars(self):
        assert slugify("10yen Stamp") == "10yen_stamp"

    def test_leading_trailing_spaces(self):
        assert slugify("  Hello World  ") == "hello_world"

    def test_multiple_hyphens(self):
        assert slugify("a---b") == "a_b"

    def test_unicode(self):
        assert slugify("Café") == "cafe"

    def test_empty_string(self):
        assert slugify("") == "problem"

    def test_only_special_chars(self):
        assert slugify("!!!") == "problem"


class TestRestoreMath:
    def test_single_placeholder(self):
        result = restore_math("before XX-MATH-0-XX after", {"XX-MATH-0-XX": "$x^2$"})
        assert result == "before $x^2$ after"

    def test_multiple_placeholders(self):
        result = restore_math(
            "a XX-MATH-0-XX b XX-MATH-1-XX c",
            {"XX-MATH-0-XX": "$x$", "XX-MATH-1-XX": "$y$"},
        )
        assert result == "a $x$ b $y$ c"

    def test_missing_key(self):
        result = restore_math("XX-MATH-0-XX", {})
        assert result == "XX-MATH-0-XX"

    def test_no_placeholders(self):
        result = restore_math("hello world", {"XX-MATH-0-XX": "$x$"})
        assert result == "hello world"


class TestSaveLoadMetaUrl:
    def test_round_trip(self, tmp_path):
        data = ProblemData(
            name="Watermelon",
            site="codeforces",
            platform="Codeforces",
            url="https://example.com/problem/1",
            time_limit=1000.0,
            memory_limit=256,
            samples=[],
            body_html="<p>Test</p>",
        )
        save_meta_json(tmp_path, data)
        assert load_meta_url(tmp_path) == "https://example.com/problem/1"
        raw = json.loads((tmp_path / "meta.json").read_text(encoding="utf-8"))
        assert raw["version"] == 1
        assert raw["name"] == "Watermelon"
        assert raw["site"] == "codeforces"
        assert raw["platform"] == "Codeforces"
        assert raw["time_limit"] == 1000.0
        assert raw["memory_limit"] == 256
        assert "samples" not in raw
        assert "body_html" not in raw

    def test_missing_file(self, tmp_path):
        assert load_meta_url(tmp_path) is None

    def test_invalid_json(self, tmp_path):
        (tmp_path / "meta.json").write_text("not json")
        assert load_meta_url(tmp_path) is None

    def test_missing_url_key(self, tmp_path):
        (tmp_path / "meta.json").write_text('{"foo": "bar"}')
        assert load_meta_url(tmp_path) is None


class TestMathExtractor:
    def test_add_creates_sentinel(self):
        extractor = MathExtractor()
        key = extractor.add("$x^2$")
        assert key == "XX-MATH-0-XX"
        assert extractor.mapping == {"XX-MATH-0-XX": "$x^2$"}

    def test_counter_increments(self):
        extractor = MathExtractor()
        k1 = extractor.add("$a$")
        k2 = extractor.add("$b$")
        assert k1 == "XX-MATH-0-XX"
        assert k2 == "XX-MATH-1-XX"

    def test_empty_extractor(self):
        extractor = MathExtractor()
        assert extractor.mapping == {}


class TestSpaceLatexCommands:
    def test_basic_command(self):
        assert space_latex_commands(r"\le n") == r"\le{} n"

    def test_no_command(self):
        assert space_latex_commands("plain text") == "plain text"

    def test_multiple_commands(self):
        assert space_latex_commands(r"\le n \ge m") == r"\le{} n \ge{} m"

    def test_command_at_end(self):
        assert space_latex_commands(r"abc \le") == r"abc \le"


class TestClassifySectionHeading:
    def test_input(self):
        assert classify_section_heading("Input") is True

    def test_output(self):
        assert classify_section_heading("Output") is True

    def test_constraints(self):
        assert classify_section_heading("Constraints") is True

    def test_sample(self):
        assert classify_section_heading("Sample 1") is True

    def test_example(self):
        assert classify_section_heading("Example") is True

    def test_note(self):
        assert classify_section_heading("Note") is True

    def test_scoring(self):
        assert classify_section_heading("Scoring") is True

    def test_editorial(self):
        assert classify_section_heading("Editorial") is True

    def test_hint(self):
        assert classify_section_heading("Hint") is True

    def test_explanation(self):
        assert classify_section_heading("Explanation") is True

    def test_case_insensitive(self):
        assert classify_section_heading("input") is True
        assert classify_section_heading("INPUT") is True

    def test_strips_colon(self):
        assert classify_section_heading("Input:") is True

    def test_generic_text(self):
        assert classify_section_heading("Some random heading") is False

    def test_empty_string(self):
        assert classify_section_heading("") is False


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


class TestParseTimeLimit:
    def test_seconds(self) -> None:
        assert CodeforcesParser.parse_time_limit("2 seconds") == 2000

    def test_sec_abbrev(self) -> None:
        assert CodeforcesParser.parse_time_limit("1 sec") == 1000

    def test_milliseconds(self) -> None:
        assert CodeforcesParser.parse_time_limit("500 ms") == 500

    def test_milliseconds_long(self) -> None:
        assert CodeforcesParser.parse_time_limit("1500 milliseconds") == 1500

    def test_decimal_seconds(self) -> None:
        assert CodeforcesParser.parse_time_limit("1.5 sec") == 1500

    def test_no_match(self) -> None:
        assert CodeforcesParser.parse_time_limit("no time here") is None

    def test_empty_string(self) -> None:
        assert CodeforcesParser.parse_time_limit("") is None


class TestParseMemoryLimit:
    def test_megabytes(self) -> None:
        assert CodeforcesParser.parse_memory_limit("256 MB") == 256

    def test_mebibytes(self) -> None:
        assert CodeforcesParser.parse_memory_limit("128 MiB") == 128

    def test_gigabytes(self) -> None:
        assert CodeforcesParser.parse_memory_limit("1 GB") == 1024

    def test_gibibytes(self) -> None:
        assert CodeforcesParser.parse_memory_limit("2 GiB") == 2048

    def test_gigabytes_long(self) -> None:
        assert CodeforcesParser.parse_memory_limit("1 gigabytes") == 1024

    def test_no_match(self) -> None:
        assert CodeforcesParser.parse_memory_limit("no memory here") is None

    def test_empty_string(self) -> None:
        assert CodeforcesParser.parse_memory_limit("") is None


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
            body_html="<p>Value of XX-MATH-0-XX is important.</p>",
            math={"XX-MATH-0-XX": "$x^2$"},
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


_CSES_WRAPPER = '<div class="md">\n{}\n</div>'


def _cses_soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(_CSES_WRAPPER.format(body), "html.parser")


class TestExtractCsesSamples:
    def test_single_example_one_pair(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1>'
            "<p>Input:</p><pre>3</pre>"
            "<p>Output:</p><pre>3 10 5 16 8 4 2 1</pre>"
        )
        samples = _extract_cses_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "3"
        assert samples[0].output == "3 10 5 16 8 4 2 1"

    def test_single_example_two_pairs(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1>'
            "<p>Input:</p><pre>1</pre>"
            "<p>Output:</p><pre>2</pre>"
            "<p>Input:</p><pre>3</pre>"
            "<p>Output:</p><pre>4</pre>"
        )
        samples = _extract_cses_samples(soup)
        assert len(samples) == 2
        assert samples[0].input == "1"
        assert samples[0].output == "2"
        assert samples[1].input == "3"
        assert samples[1].output == "4"

    def test_numbered_examples(self) -> None:
        soup = _cses_soup(
            '<h1 id="example1">Example 1</h1>'
            "<p>Input:</p><pre>7</pre>"
            "<p>Output:</p><pre>YES</pre>"
            '<h1 id="example2">Example 2</h1>'
            "<p>Input:</p><pre>6</pre>"
            "<p>Output:</p><pre>NO</pre>"
        )
        samples = _extract_cses_samples(soup)
        assert len(samples) == 2
        assert samples[0].input == "7"
        assert samples[0].output == "YES"
        assert samples[1].input == "6"
        assert samples[1].output == "NO"

    def test_no_example_heading(self) -> None:
        soup = _cses_soup("<p>No examples here.</p>")
        assert _extract_cses_samples(soup) == []

    def test_example_without_pres(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1><p>Just some text.</p>'
        )
        assert _extract_cses_samples(soup) == []

    def test_odd_number_of_pres(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1>'
            "<p>Input:</p><pre>1</pre>"
            "<p>Output:</p><pre>2</pre>"
            "<p>Input:</p><pre>3</pre>"
        )
        samples = _extract_cses_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "1"
        assert samples[0].output == "2"

    def test_decomposes_example_section(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1>'
            "<p>Input:</p><pre>3</pre>"
            "<p>Output:</p><pre>4</pre>"
            '<h1 id="constraints">Constraints</h1>'
            "<p>Keep this text.</p>"
        )
        _ = _extract_cses_samples(soup)
        assert soup.find("h1", id="example") is None
        assert "Keep this text." in soup.get_text()

    def test_decomposes_numbered_examples(self) -> None:
        soup = _cses_soup(
            '<h1 id="example1">Example 1</h1>'
            "<p>Input:</p><pre>7</pre>"
            "<p>Output:</p><pre>YES</pre>"
            '<h1 id="example2">Example 2</h1>'
            "<p>Input:</p><pre>6</pre>"
            "<p>Output:</p><pre>NO</pre>"
            '<h1 id="constraints">Constraints</h1>'
            "<p>Trailing text.</p>"
        )
        _ = _extract_cses_samples(soup)
        assert soup.find("h1", id="example1") is None
        assert soup.find("h1", id="example2") is None
        assert "Trailing text." in soup.get_text()

    def test_non_example_h1_not_removed(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1>'
            "<p>Input:</p><pre>3</pre>"
            "<p>Output:</p><pre>4</pre>"
            '<h1 id="constraints">Constraints</h1>'
            "<ul><li>n &le; 10</li></ul>"
        )
        _ = _extract_cses_samples(soup)
        constraints = soup.find("h1", id="constraints")
        assert constraints is not None
        assert "n" in constraints.find_next("ul").get_text()


class TestFetchCodechefApiSamples:
    def _make_response(self, data: dict) -> bytes:
        return json.dumps(data).encode()

    def test_success(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = self._make_response(
                {
                    "status": "success",
                    "problemComponents": {
                        "sampleTestCases": [
                            {"id": "1", "input": "123", "output": "123", "isDeleted": False},
                            {"id": "2", "input": "15", "output": "15", "isDeleted": False},
                        ]
                    },
                }
            )
            samples = _fetch_codechef_api_samples("START01")
        assert samples is not None
        assert len(samples) == 2
        assert samples[0].input == "123"
        assert samples[0].output == "123"
        assert samples[1].input == "15"
        assert samples[1].output == "15"

    def test_filters_deleted(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = self._make_response(
                {
                    "status": "success",
                    "problemComponents": {
                        "sampleTestCases": [
                            {"id": "1", "input": "in1", "output": "out1", "isDeleted": True},
                            {"id": "2", "input": "in2", "output": "out2", "isDeleted": False},
                        ]
                    },
                }
            )
            samples = _fetch_codechef_api_samples("TEST")
        assert samples is not None
        assert len(samples) == 1
        assert samples[0].input == "in2"

    def test_not_success(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = self._make_response(
                {"status": "error"}
            )
            assert _fetch_codechef_api_samples("TEST") is None

    def test_network_error(self) -> None:
        with patch("urllib.request.urlopen", side_effect=OSError("network error")):
            assert _fetch_codechef_api_samples("TEST") is None

    def test_empty_sample_test_cases(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = self._make_response(
                {
                    "status": "success",
                    "problemComponents": {"sampleTestCases": []},
                }
            )
            assert _fetch_codechef_api_samples("TEST") == []

    def test_missing_sample_test_cases(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = self._make_response(
                {"status": "success", "problemComponents": {}}
            )
            assert _fetch_codechef_api_samples("TEST") is None

    def test_malformed_json(self) -> None:
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = b"not json"
            assert _fetch_codechef_api_samples("TEST") is None


class TestExtractCodechefProblemCode:
    def test_practice_problem(self) -> None:
        assert _extract_codechef_problem_code("https://www.codechef.com/problems/START01") == "START01"

    def test_contest_problem(self) -> None:
        assert _extract_codechef_problem_code("https://www.codechef.com/START37/problems/MINHEIGHT") is None

    def test_non_problem_url(self) -> None:
        assert _extract_codechef_problem_code("https://www.codechef.com/") is None

    def test_trailing_slash(self) -> None:
        assert _extract_codechef_problem_code("https://www.codechef.com/problems/START01/") == "START01"

    def test_blog_url(self) -> None:
        assert _extract_codechef_problem_code("https://www.codechef.com/blogs/how-to") is None


class TestCodeChefParserParse:
    def _base_data(self) -> ProblemData:
        return ProblemData(
            name="Test",
            site="codechef",
            platform="CodeChef",
            url="https://www.codechef.com/problems/TEST",
            time_limit=1000.0,
            memory_limit=256,
            samples=[SampleCase(input="scraped", output="scraped")],
            body_html="<p>test</p>",
        )

    def test_api_samples_replace_playwright_samples(self) -> None:
        parser = CodeChefParser()
        with (
            patch.object(BaseParser, "parse", return_value=self._base_data()),
            patch(
                "cpfetch.cpparse.platforms.codechef._fetch_codechef_api_samples",
                return_value=[SampleCase(input="api_in", output="api_out")],
            ),
        ):
            data = parser.parse("https://www.codechef.com/problems/TEST")
        assert data is not None
        assert len(data.samples) == 1
        assert data.samples[0].input == "api_in"

    def test_api_failure_keeps_playwright_samples(self) -> None:
        parser = CodeChefParser()
        with (
            patch.object(BaseParser, "parse", return_value=self._base_data()),
            patch(
                "cpfetch.cpparse.platforms.codechef._fetch_codechef_api_samples",
                return_value=None,
            ),
        ):
            data = parser.parse("https://www.codechef.com/problems/TEST")
        assert data is not None
        assert data.samples[0].input == "scraped"

    def test_contest_url_skips_api(self) -> None:
        parser = CodeChefParser()
        base = ProblemData(
            name="Test",
            site="codechef",
            platform="CodeChef",
            url="https://www.codechef.com/START37/problems/TEST",
            time_limit=1000.0,
            memory_limit=256,
            samples=[SampleCase(input="scraped", output="scraped")],
            body_html="<p>test</p>",
        )
        with patch.object(BaseParser, "parse", return_value=base):
            data = parser.parse("https://www.codechef.com/START37/problems/TEST")
        assert data is not None
        assert data.samples[0].input == "scraped"
