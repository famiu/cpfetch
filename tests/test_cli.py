"""Tests for CLI argument parsing and dispatch."""

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cpfetch.fetch_problem import _build_parser, main


class TestCliDispatch:
    """Verify that main() correctly dispatches to subcommands."""

    def test_no_subcommand_exits(self) -> None:
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_setup_dispatches(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "setup"]),
            patch("cpfetch.fetch_problem.setup") as mock_setup,
        ):
            main()
        mock_setup.assert_called_once()

    def test_fetch_single_url(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "fetch", "https://example.com/1"]),
            patch("cpfetch.fetch_problem._run_fetch", return_value=0) as mock_run,
        ):
            main()
        mock_run.assert_called_once()
        urls, _out_dir, nest = mock_run.call_args[0]
        assert urls == ["https://example.com/1"]
        assert nest is False

    def test_fetch_multiple_urls_with_nest(self) -> None:
        with (
            patch.object(
                sys,
                "argv",
                ["cpfetch", "fetch", "https://a.com/1", "https://b.com/2", "--nest"],
            ),
            patch("cpfetch.fetch_problem._run_fetch", return_value=0) as mock_run,
        ):
            main()
        urls, _, nest = mock_run.call_args[0]
        assert urls == ["https://a.com/1", "https://b.com/2"]
        assert nest is True

    def test_fetch_with_out_dir(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "fetch", "https://a.com/1", "--out-dir", "/tmp/probs"]),
            patch("cpfetch.fetch_problem._run_fetch", return_value=0) as mock_run,
        ):
            main()
        _, out_dir, _ = mock_run.call_args[0]
        assert out_dir == Path("/tmp/probs").resolve()

    def test_fetch_failures_exit_nonzero(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "fetch", "https://a.com/1"]),
            patch("cpfetch.fetch_problem._run_fetch", return_value=1),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1

    def test_refetch_dispatches(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "refetch"]),
            patch("cpfetch.fetch_problem._run_refetch", return_value=0) as mock_run,
        ):
            main()
        mock_run.assert_called_once()
        problems_dir = mock_run.call_args[0][0]
        assert problems_dir == Path().resolve()

    def test_refetch_with_problems_dir(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "refetch", "--problems-dir", "/tmp/probs"]),
            patch("cpfetch.fetch_problem._run_refetch", return_value=0) as mock_run,
        ):
            main()
        problems_dir = mock_run.call_args[0][0]
        assert problems_dir == Path("/tmp/probs").resolve()

    def test_refetch_failures_exit_nonzero(self) -> None:
        with (
            patch.object(sys, "argv", ["cpfetch", "refetch"]),
            patch("cpfetch.fetch_problem._run_refetch", return_value=1),
        ):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 1


class TestRunFetchValidation:
    """Verify that _run_fetch enforces multi-URL-requires-nest."""

    def test_multiple_urls_without_nest_exits(self) -> None:
        with (
            patch("cpfetch.fetch_problem.BrowserFetch") as mock_bf,
            patch("cpfetch.fetch_problem.process_url") as mock_proc,
        ):
            mock_bf.return_value.__enter__ = MagicMock(return_value=mock_bf.return_value)
            mock_bf.return_value.__exit__ = MagicMock(return_value=None)
            with pytest.raises(SystemExit):
                _run_fetch_impl(["https://a.com/1", "https://b.com/2"], Path(), nest=False)
            mock_proc.assert_not_called()


def _run_fetch_impl(urls: list[str], out_dir: Path, nest: bool) -> int:
    """Helper to call the module-level _run_fetch."""
    from cpfetch.fetch_problem import _run_fetch

    return _run_fetch(urls, out_dir, nest)


class TestRunRefetchValidation:
    """Verify that _run_refetch errors on non-existent directory."""

    def test_nonexistent_dir_exits(self, tmp_path: Path) -> None:
        from cpfetch.fetch_problem import _run_refetch

        with pytest.raises(SystemExit):
            _run_refetch(tmp_path / "nonexistent")

    def test_restores_stranded_backup(self, tmp_path: Path) -> None:
        from cpfetch.fetch_problem import _run_refetch

        backup_dir = tmp_path / ".prob.old"
        backup_dir.mkdir(parents=True)
        (backup_dir / "meta.json").write_text(
            json.dumps({"url": "https://a.com/1"}),
            encoding="utf-8",
        )

        with (
            patch("cpfetch.fetch_problem.BrowserFetch") as mock_bf,
            patch("cpfetch.fetch_problem.process_url", return_value=None),
        ):
            mock_bf.return_value.__enter__ = MagicMock(return_value=mock_bf.return_value)
            mock_bf.return_value.__exit__ = MagicMock(return_value=None)
            _run_refetch(tmp_path)

        assert not backup_dir.exists()
        assert (tmp_path / "prob" / "meta.json").exists()
