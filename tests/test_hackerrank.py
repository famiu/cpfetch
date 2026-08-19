"""Unit tests for the HackerRank platform parser."""

from cpfetch.cpparse import get_parser
from cpfetch.cpparse.platforms.hackerrank import HackerRankParser


def test_dispatches_hackerrank_urls() -> None:
    assert isinstance(get_parser("https://www.hackerrank.com/challenges/solve-me-first/problem"), HackerRankParser)
    assert isinstance(get_parser("https://hackerrank.com/challenges/solve-me-first/problem"), HackerRankParser)


def test_extracts_samples_and_removes_legacy_svg_math() -> None:
    html = """<html><head>
      <meta property="og:title" content="Solve Me First | HackerRank">
    </head><body>
      <div class="challenge-body-html">
        <style>.MathJax_SVG { display: inline; }</style>
        <p>Complete the function <span class="MathJax_SVG"><svg><path></path></svg></span>.</p>
        <div class="challenge_sample_input">
          <div class="challenge_sample_input_body">2\n3\n</div>
        </div>
        <div class="challenge_sample_output">
          <div class="challenge_sample_output_body">5\n</div>
        </div>
        <div class="challenge_explanation"><p>2 + 3 = 5.</p></div>
      </div>
    </body></html>"""

    data = HackerRankParser().extract_data(html, "https://www.hackerrank.com/challenges/solve-me-first/problem")

    assert data is not None
    assert data.name == "Solve Me First"
    assert data.site == "hackerrank"
    assert data.platform == "HackerRank"
    assert data.time_limit is None
    assert data.memory_limit is None
    assert [(sample.input, sample.output) for sample in data.samples] == [("2\n3", "5")]
    assert "challenge_sample_input" not in data.body_html
    assert "challenge_sample_output" not in data.body_html
    assert "MathJax_SVG" not in data.body_html
    assert "<svg" not in data.body_html
    assert "2 + 3 = 5." in data.body_html


def test_preserves_unpaired_sample_blocks() -> None:
    html = """<div class="challenge-body-html">
      <div class="challenge_sample_input"><div class="challenge_sample_input_body">2</div></div>
    </div>"""

    data = HackerRankParser().extract_data(html, "https://www.hackerrank.com/challenges/solve-me-first/problem")

    assert data is not None
    assert data.samples == []
    assert "challenge_sample_input" in data.body_html
