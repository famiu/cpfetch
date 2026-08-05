"""Unit tests for the LeetCode platform parser."""

from cpfetch.cpparse import get_parser
from cpfetch.cpparse.platforms.leetcode import LeetCodeParser


def test_dispatches_leetcode_urls() -> None:
    assert isinstance(get_parser("https://leetcode.com/problems/two-sum/description/"), LeetCodeParser)
    assert isinstance(get_parser("https://www.leetcode.com/problems/two-sum/"), LeetCodeParser)


def test_extracts_problem_data_samples_and_math() -> None:
    html = """<html><head>
      <title>Fallback - LeetCode</title>
      <meta property="og:title" content="Two Sum - LeetCode">
    </head><body>
      <div data-track-load="description_content">
        <p>Find two values whose sum is <span class="katex"><span class="katex-mathml">
          <math><semantics><annotation encoding="application/x-tex">x+y</annotation></semantics></math>
        </span><span class="katex-html">visual duplicate</span></span>.</p>
        <p><strong class="example">Example 1:</strong></p>
        <pre><strong>Input:</strong> nums = [2,7,11,15], target = 9
<strong>Output:</strong> [0,1]
<strong>Explanation:</strong> The values add to 9.</pre>
        <p><strong class="example">Example 2:</strong></p>
        <pre><strong>Input:</strong> nums = [3,3], target = 6
<strong>Output:</strong> [0,1]</pre>
        <h3>Constraints:</h3><p>At least two values.</p>
      </div>
    </body></html>"""

    data = LeetCodeParser().extract_data(html, "https://leetcode.com/problems/two-sum/description/")

    assert data is not None
    assert data.name == "Two Sum"
    assert data.site == "leetcode"
    assert data.platform == "LeetCode"
    assert data.time_limit is None
    assert data.memory_limit is None
    assert LeetCodeParser.write_sample_files is False
    assert [(sample.input, sample.output) for sample in data.samples] == [
        ("nums = [2,7,11,15], target = 9", "[0,1]"),
        ("nums = [3,3], target = 6", "[0,1]"),
    ]
    assert list(data.math.values()) == ["$x+y$"]
    assert "visual duplicate" not in data.body_html
    assert "Example 1" in data.body_html
    assert "The values add to 9." in data.body_html
    assert "nums = [2,7,11,15]" not in data.body_html
    assert "Example 2" not in data.body_html
    assert "<h2>Constraints:</h2>" in data.body_html


def test_falls_back_to_url_slug_when_page_has_no_title() -> None:
    html = '<div data-track-load="description_content"><p>Description</p></div>'
    data = LeetCodeParser().extract_data(html, "https://leetcode.com/problems/two-sum/description/")
    assert data is not None
    assert data.name == "two-sum"
