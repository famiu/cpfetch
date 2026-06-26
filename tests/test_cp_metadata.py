"""Unit tests for cpfetch.cp_metadata — data types, URL dispatch, and helpers."""

import json

from cpfetch.cp_metadata import (
    MathSentinelRegistry,
    ProblemData,
    load_meta_url,
    parse_memory_limit,
    parse_time_limit,
    restore_math,
    save_meta_json,
    site_from_url,
    slugify,
)


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

    def test_spoj(self):
        assert site_from_url("https://www.spoj.com/problems/TEST/") == "spoj"

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
        key = "XX-MATH-0-abcdef12-XX"
        result = restore_math(f"before {key} after", {key: "$x^2$"})
        assert result == "before $x^2$ after"

    def test_multiple_placeholders(self):
        k1 = "XX-MATH-0-abcdef12-XX"
        k2 = "XX-MATH-1-abcdef12-XX"
        result = restore_math(f"a {k1} b {k2} c", {k1: "$x$", k2: "$y$"})
        assert result == "a $x$ b $y$ c"

    def test_missing_key(self):
        result = restore_math("XX-MATH-0-abcdef12-XX", {})
        assert result == "XX-MATH-0-abcdef12-XX"

    def test_no_placeholders(self):
        result = restore_math("hello world", {"XX-MATH-0-abcdef12-XX": "$x$"})
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
        assert "version" not in raw
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


class TestMathSentinelRegistry:
    def test_add_creates_sentinel(self):
        extractor = MathSentinelRegistry()
        key = extractor.add("$x^2$")
        assert key.startswith("XX-MATH-0-")
        assert key.endswith("-XX")
        assert extractor.mapping == {key: "$x^2$"}

    def test_counter_increments(self):
        extractor = MathSentinelRegistry()
        k1 = extractor.add("$a$")
        k2 = extractor.add("$b$")
        assert k1.startswith("XX-MATH-0-")
        assert k2.startswith("XX-MATH-1-")
        assert k1 != k2

    def test_empty_extractor(self):
        extractor = MathSentinelRegistry()
        assert extractor.mapping == {}

    def test_sentinels_have_unique_token_per_instance(self):
        e1 = MathSentinelRegistry()
        e2 = MathSentinelRegistry()
        k1 = e1.add("$a$")
        k2 = e2.add("$a$")
        assert k1 != k2


class TestParseTimeLimit:
    def test_seconds(self) -> None:
        assert parse_time_limit("2 seconds") == 2000

    def test_sec_abbrev(self) -> None:
        assert parse_time_limit("1 sec") == 1000

    def test_milliseconds(self) -> None:
        assert parse_time_limit("500 ms") == 500

    def test_milliseconds_long(self) -> None:
        assert parse_time_limit("1500 milliseconds") == 1500

    def test_decimal_seconds(self) -> None:
        assert parse_time_limit("1.5 sec") == 1500

    def test_no_match(self) -> None:
        assert parse_time_limit("no time here") is None

    def test_empty_string(self) -> None:
        assert parse_time_limit("") is None


class TestParseMemoryLimit:
    def test_megabytes(self) -> None:
        assert parse_memory_limit("256 MB") == 256

    def test_mebibytes(self) -> None:
        assert parse_memory_limit("128 MiB") == 128

    def test_gigabytes(self) -> None:
        assert parse_memory_limit("1 GB") == 1024

    def test_gibibytes(self) -> None:
        assert parse_memory_limit("2 GiB") == 2048

    def test_gigabytes_long(self) -> None:
        assert parse_memory_limit("1 gigabytes") == 1024

    def test_no_match(self) -> None:
        assert parse_memory_limit("no memory here") is None

    def test_empty_string(self) -> None:
        assert parse_memory_limit("") is None
