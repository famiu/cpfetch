from cpfetch.cp_metadata import ProblemData, SampleCase
from cpfetch.cpparse.lib import render_markdown
from cpfetch.fetch_problem import write_samples


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
