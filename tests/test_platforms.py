"""Unit tests for CSES, SPOJ, and Codeforces platform parsers."""

from bs4 import BeautifulSoup

from cpfetch.cpparse.platforms.cses import _extract_cses_samples
from cpfetch.cpparse.platforms.spoj import SpojParser, _extract_spoj_samples

_CSES_WRAPPER = '<div class="md">\n{}\n</div>'


def _cses_soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(_CSES_WRAPPER.format(body), "html.parser")


class TestExtractCsesSamples:
    def test_single_example_one_pair(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1><p>Input:</p><pre>3</pre><p>Output:</p><pre>3 10 5 16 8 4 2 1</pre>'
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
        soup = _cses_soup('<h1 id="example">Example</h1><p>Just some text.</p>')
        assert _extract_cses_samples(soup) == []

    def test_odd_number_of_pres(self) -> None:
        soup = _cses_soup(
            '<h1 id="example">Example</h1><p>Input:</p><pre>1</pre><p>Output:</p><pre>2</pre><p>Input:</p><pre>3</pre>'
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
        ul = constraints.find_next("ul")
        assert ul is not None
        assert "n" in ul.get_text()


class TestCsesParserIntegration:
    def test_full_parser_flow(self) -> None:
        """Regression: verify full CsesParser flow including extract_limits() and normalize()."""
        from cpfetch.cpparse.platforms.cses import CsesParser

        html = """<html><head><title>CSES - Test Problem</title></head><body>
        <div class="md">
        <h1>Test Problem</h1>
        <ul class="task-constraints">
        <li>Time limit: 1.00 s</li>
        <li>Memory limit: 512 MB</li>
        </ul>
        <p>Problem description here.</p>
        <h1 id="example">Example</h1>
        <p>Input:</p><pre>5</pre>
        <p>Output:</p><pre>10</pre>
        </div>
        </body></html>"""

        parser = CsesParser()
        soup = BeautifulSoup(html, "html.parser")

        time_limit, memory_limit = parser.extract_limits(soup)
        assert time_limit == 1000.0
        assert memory_limit == 512

        _extractor, samples = parser.normalize(soup)
        assert len(samples) == 1
        assert samples[0].input == "5"
        assert samples[0].output == "10"
        assert soup.find("h1", id="example") is None


_SPOJ_WRAPPER = '<div id="problem-body">{}</div>'


def _spoj_soup(body: str) -> BeautifulSoup:
    return BeautifulSoup(_SPOJ_WRAPPER.format(body), "html.parser")


class TestExtractSpojSamples:
    def test_strong_labels(self) -> None:
        soup = _spoj_soup(
            "<h3>Example</h3>"
            "<pre><strong>Input:</strong>\n1\n2\n88\n42\n99\n\n<strong>Output:</strong>\n1\n2\n88\n</pre>"
        )
        samples = _extract_spoj_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "1\n2\n88\n42\n99"
        assert samples[0].output == "1\n2\n88"

    def test_b_labels(self) -> None:
        soup = _spoj_soup(
            "<h3>Example</h3><pre><b>Input:</b>\n2\n1 10\n3 5\n\n<b>Output:</b>\n2\n3\n5\n7\n\n3\n5\n</pre>"
        )
        samples = _extract_spoj_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "2\n1 10\n3 5"
        assert samples[0].output == "2\n3\n5\n7\n\n3\n5"

    def test_no_example_heading(self) -> None:
        soup = _spoj_soup("<p>No examples here.</p>")
        assert _extract_spoj_samples(soup) == []

    def test_example_without_pre(self) -> None:
        soup = _spoj_soup("<h3>Example</h3><p>Just text.</p>")
        assert _extract_spoj_samples(soup) == []

    def test_example_without_labels(self) -> None:
        soup = _spoj_soup("<h3>Example</h3><pre>just data</pre>")
        assert _extract_spoj_samples(soup) == []

    def test_non_example_h3_skipped(self) -> None:
        soup = _spoj_soup("<h3>Input</h3><pre>data</pre>")
        assert _extract_spoj_samples(soup) == []

    def test_wrapped_pre_is_decomposed(self) -> None:
        """Regression: a <pre> wrapped in a <div> is harvested and removed from body_html."""
        soup = _spoj_soup(
            "<h3>Example</h3><div><pre><b>Input:</b>\n1\n\n<b>Output:</b>\n2\n</pre></div>"
            "<h3>Information</h3><p>keep</p>"
        )
        samples = _extract_spoj_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "1"
        assert samples[0].output == "2"
        assert soup.find("pre") is None
        assert soup.find("h3", string="Example") is None

    def test_plain_text_labels(self) -> None:
        soup = _spoj_soup("<h3>Example</h3><pre>Sample Input:\n3\n2\n10\n20\n\nSample Output:\n1\n8\n22</pre>")
        samples = _extract_spoj_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "3\n2\n10\n20"
        assert samples[0].output == "1\n8\n22"
        assert soup.find("pre") is None
        assert soup.find("h3", string="Example") is None

    def test_data_line_contains_output_label(self) -> None:
        """Regression: 'Output:' as a data line in input is not mistaken for the output separator."""
        soup = _spoj_soup("<h3>Example</h3><pre>Sample Input:\n3\n2\n10\nOutput:\n20\n\nSample Output:\n1\n8\n22</pre>")
        samples = _extract_spoj_samples(soup)
        assert len(samples) == 1
        assert samples[0].input == "3\n2\n10\nOutput:\n20"
        assert samples[0].output == "1\n8\n22"
        assert soup.find("pre") is None
        assert soup.find("h3", string="Example") is None

    def test_incomplete_plain_text_labels_preserves_body(self) -> None:
        """Regression: only Sample Input: without Sample Output: leaves the
        Example heading and <pre> intact (not decomposed) in body_html."""
        soup = _spoj_soup("<h3>Example</h3><pre>Sample Input:\n1\n2\n3\n</pre>")
        samples = _extract_spoj_samples(soup)
        assert samples == []
        assert soup.find("pre") is not None
        assert soup.find("h3", string="Example") is not None


_SPOJ_FULL_WRAPPER = (
    '<div id="content" class="container">'
    '<div class="row first-row">'
    '<div class="col-lg-8 col-md-8"><div class="prob">{name}</div></div>'
    '<div class="col-lg-4 col-md-4">{meta}</div>'
    "</div>"
    "{body}"
    "</div>"
)


class TestSpojLimits:
    def _make_soup(self, name_html: str, meta_html: str) -> BeautifulSoup:
        html = _SPOJ_FULL_WRAPPER.format(name=name_html, meta=meta_html, body="")
        return BeautifulSoup(html, "html.parser")

    def test_extracts_time_and_memory(self) -> None:
        soup = self._make_soup(
            '<h2 id="problem-name">TEST - Life</h2>',
            '<table id="problem-meta" class="probleminfo">'
            "<tr><td>Added by:</td><td>mima</td></tr>"
            "<tr><td>Time limit:</td><td>1s</td></tr>"
            "<tr><td>Memory limit:</td><td>1536MB</td></tr>"
            "</table>",
        )
        parser = SpojParser()
        time_limit, memory_limit = parser.extract_limits(soup)
        assert time_limit == 1000.0
        assert memory_limit == 1536

    def test_extracts_name(self) -> None:
        soup = self._make_soup('<h2 id="problem-name">FCTRL - Factorial</h2>', "")
        parser = SpojParser()
        assert parser.extract_name(soup) == "FCTRL - Factorial"

    def test_no_meta_table(self) -> None:
        soup = self._make_soup('<h2 id="problem-name">Test</h2>', "")
        parser = SpojParser()
        assert parser.extract_limits(soup) == (None, None)

    def test_missing_limits(self) -> None:
        soup = self._make_soup(
            '<h2 id="problem-name">Test</h2>',
            '<table id="problem-meta"><tr><td>Added by:</td><td>mima</td></tr></table>',
        )
        parser = SpojParser()
        assert parser.extract_limits(soup) == (None, None)
