"""Unit tests for the CodeChef platform parser."""

from typing import NotRequired, TypedDict
from unittest.mock import MagicMock, patch

from cpfetch.cp_metadata import ProblemData, SampleCase
from cpfetch.cpparse.lib import BaseParser
from cpfetch.cpparse.platforms.codechef import (
    CodeChefParser,
    _extract_codechef_problem_code,
    _fetch_codechef_api_samples,
)


class _SampleTestCase(TypedDict):
    id: str
    input: str
    output: str
    isDeleted: NotRequired[bool]


class _ProblemComponents(TypedDict):
    sampleTestCases: NotRequired[list[_SampleTestCase]]


class CodeChefApiResponse(TypedDict):
    status: str
    problemComponents: NotRequired[_ProblemComponents]


class TestFetchCodechefApiSamples:
    def _make_fetcher(self, response_data: CodeChefApiResponse | None) -> MagicMock:
        fetcher = MagicMock()
        fetcher.request_get.return_value = response_data
        return fetcher

    def test_success(self) -> None:
        fetcher = self._make_fetcher(
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
        samples = _fetch_codechef_api_samples("START01", fetcher)
        assert samples is not None
        assert len(samples) == 2
        assert samples[0].input == "123"
        assert samples[0].output == "123"
        assert samples[1].input == "15"
        assert samples[1].output == "15"

    def test_filters_deleted(self) -> None:
        fetcher = self._make_fetcher(
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
        samples = _fetch_codechef_api_samples("TEST", fetcher)
        assert samples is not None
        assert len(samples) == 1
        assert samples[0].input == "in2"

    def test_not_success(self) -> None:
        fetcher = self._make_fetcher({"status": "error"})
        assert _fetch_codechef_api_samples("TEST", fetcher) is None

    def test_network_error(self) -> None:
        fetcher = MagicMock()
        fetcher.request_get.return_value = None
        assert _fetch_codechef_api_samples("TEST", fetcher) is None

    def test_empty_sample_test_cases(self) -> None:
        fetcher = self._make_fetcher(
            {
                "status": "success",
                "problemComponents": {"sampleTestCases": []},
            }
        )
        assert _fetch_codechef_api_samples("TEST", fetcher) == []

    def test_missing_sample_test_cases(self) -> None:
        fetcher = self._make_fetcher({"status": "success", "problemComponents": {}})
        assert _fetch_codechef_api_samples("TEST", fetcher) is None

    def test_malformed_json(self) -> None:
        fetcher = MagicMock()
        fetcher.request_get.return_value = None
        assert _fetch_codechef_api_samples("TEST", fetcher) is None


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
        fetcher = MagicMock()
        parser = CodeChefParser(fetcher)
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
        fetcher = MagicMock()
        parser = CodeChefParser(fetcher)
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

    def test_empty_api_result_clears_scraped_samples(self) -> None:
        """Regression: an authoritative empty API response clears scraped samples."""
        fetcher = MagicMock()
        parser = CodeChefParser(fetcher)
        with (
            patch.object(BaseParser, "parse", return_value=self._base_data()),
            patch(
                "cpfetch.cpparse.platforms.codechef._fetch_codechef_api_samples",
                return_value=[],
            ),
        ):
            data = parser.parse("https://www.codechef.com/problems/TEST")
        assert data is not None
        assert data.samples == []

    def test_contest_url_skips_api(self) -> None:
        fetcher = MagicMock()
        parser = CodeChefParser(fetcher)
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
