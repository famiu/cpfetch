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
    as_code_block,
    classify_section_heading,
    fmt_time,
    render_markdown,
    space_latex_commands,
)
from cpfetch.cpparse.platforms.codeforces import CodeforcesParser


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
        save_meta_json(tmp_path, "https://example.com/problem/1")
        assert load_meta_url(tmp_path) == "https://example.com/problem/1"

    def test_missing_file(self, tmp_path):
        assert load_meta_url(tmp_path) is None

    def test_invalid_json(self, tmp_path):
        (tmp_path / ".meta.json").write_text("not json")
        assert load_meta_url(tmp_path) is None

    def test_missing_url_key(self, tmp_path):
        (tmp_path / ".meta.json").write_text('{"foo": "bar"}')
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
