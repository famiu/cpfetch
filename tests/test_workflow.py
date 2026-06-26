from cpfetch.cp_metadata import ProblemData, SampleCase
from cpfetch.cpparse.lib import render_markdown
from cpfetch.fetch_problem import process_url, write_samples
from tests.testutils.regenerate import scrub_html


class TestWriteSamples:
    def test_creates_files(self, tmp_path):
        data = ProblemData(
            name="Test",
            site="cses",
            platform="CSES",
            url="https://example.com",
            time_limit=1000.0,
            memory_limit=512,
            samples=[SampleCase(input="1 2\n3 4", output="3\n7")],
            body_html="<p>Desc</p>",
            math={},
        )
        write_samples(tmp_path / "tests", data.samples)
        assert (tmp_path / "tests" / "01.in").stat().st_size > 0
        assert (tmp_path / "tests" / "01.out").stat().st_size > 0

    def test_removes_stale_files(self, tmp_path):
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "01.in").write_text("old")
        (tests_dir / "02.in").write_text("stale")
        (tests_dir / "notes.txt").write_text("keep me")

        data = ProblemData(
            name="Test",
            site="cses",
            platform="CSES",
            url="https://example.com",
            time_limit=None,
            memory_limit=None,
            samples=[SampleCase(input="1", output="2")],
            body_html="<p>Desc</p>",
            math={},
        )
        write_samples(tests_dir, data.samples)

        assert (tests_dir / "01.in").stat().st_size > 0
        assert not (tests_dir / "02.in").exists()
        assert not (tests_dir / "03.out").exists()
        assert (tests_dir / "notes.txt").exists()


class TestRenderMarkdown:
    def test_writes_problem_md(self, tmp_path):
        data = ProblemData(
            name="Test Problem",
            site="cses",
            platform="CSES",
            url="https://example.com",
            time_limit=1000.0,
            memory_limit=512,
            samples=[SampleCase(input="1 2\n3 4", output="3\n7")],
            body_html="<p>A problem description</p>",
            math={},
        )
        md = render_markdown(data)
        (tmp_path / "problem.md").write_text(md)
        assert (tmp_path / "problem.md").stat().st_size > 0
        assert "# Test Problem" in md
        assert "Time limit:" in md
        assert "Memory limit:" in md
        assert "```\n1 2\n3 4\n```" in md
        assert "```\n3\n7\n```" in md
        assert "XX-MATH-" not in md


class TestScrubHtml:
    def test_removes_comment_table(self) -> None:
        html = """<html><body>
<p>keep this</p>
<table id="comments_table">
<tr><td class="comm comm_odd">user: azizshahid9080</td></tr>
</table>
</body></html>"""
        result = scrub_html(html)
        assert "comments_table" not in result
        assert "azizshahid9080" not in result
        assert "keep this" in result


class TestAtomicWrite:
    """Verify that atomic writes preserve the original directory on failure."""

    def test_failure_preserves_original(self, tmp_path) -> None:
        from unittest.mock import MagicMock, patch

        output_dir = tmp_path / "codeforces" / "test_problem"
        output_dir.mkdir(parents=True)
        (output_dir / "problem.md").write_text("old content")
        (output_dir / "meta.json").write_text('{"url": "old"}')
        tests_dir = output_dir / "tests"
        tests_dir.mkdir()
        (tests_dir / "01.in").write_text("old_input")
        (tests_dir / "01.out").write_text("old_output")

        fetcher = MagicMock()
        data = ProblemData(
            name="Test Problem",
            site="codeforces",
            platform="Codeforces",
            url="https://codeforces.com/problemset/problem/1/A",
            time_limit=1000.0,
            memory_limit=256,
            samples=[SampleCase(input="1", output="2")],
            body_html="<p>new</p>",
        )

        with (
            patch("cpfetch.fetch_problem.get_parser") as mock_get_parser,
            patch("cpfetch.fetch_problem.save_meta_json", side_effect=OSError("disk full")),
        ):
            mock_parser = MagicMock()
            mock_parser.parse.return_value = data
            mock_get_parser.return_value = mock_parser

            result = process_url(
                "https://codeforces.com/problemset/problem/1/A",
                tmp_path,
                nest=True,
                fetcher=fetcher,
                atomic=True,
            )

        assert result is None
        # Original directory is intact
        assert (output_dir / "problem.md").read_text() == "old content"
        assert (output_dir / "meta.json").read_text() == '{"url": "old"}'
        assert (tests_dir / "01.in").read_text() == "old_input"
        assert (tests_dir / "01.out").read_text() == "old_output"
        # No staging artifacts left behind
        staging_dirs = [p for p in tmp_path.glob("**/.*.") if p.is_dir()]
        assert not staging_dirs

    def test_success_replaces_original(self, tmp_path) -> None:
        from unittest.mock import MagicMock, patch

        output_dir = tmp_path / "codeforces" / "test_problem"
        output_dir.mkdir(parents=True)
        (output_dir / "problem.md").write_text("old content")

        fetcher = MagicMock()
        data = ProblemData(
            name="Test Problem",
            site="codeforces",
            platform="Codeforces",
            url="https://codeforces.com/problemset/problem/1/A",
            time_limit=1000.0,
            memory_limit=256,
            samples=[SampleCase(input="1", output="2")],
            body_html="<p>new</p>",
        )

        with patch("cpfetch.fetch_problem.get_parser") as mock_get_parser:
            mock_parser = MagicMock()
            mock_parser.parse.return_value = data
            mock_get_parser.return_value = mock_parser

            result = process_url(
                "https://codeforces.com/problemset/problem/1/A",
                tmp_path,
                nest=True,
                fetcher=fetcher,
                atomic=True,
            )

        assert result is not None
        assert "new" in (output_dir / "problem.md").read_text()
        assert (output_dir / "tests" / "01.in").exists()
        assert (output_dir / "meta.json").exists()
        # Old content is gone
        assert "old content" not in (output_dir / "problem.md").read_text()
