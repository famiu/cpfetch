"""Unit tests for BrowserFetch dispatch, injection, context manager, and retry."""

from unittest.mock import MagicMock, patch

import pytest

from cpfetch.cpparse import get_parser
from cpfetch.cpparse.fetch import _MAX_RETRIES, BrowserFetch
from cpfetch.cpparse.platforms.codeforces import CodeforcesParser


class TestBrowserFetchDispatch:
    """Verify that fetch() correctly dispatches headed vs headless paths,
    and that cf_clearance cookie reuse prevents redundant headed launches."""

    def test_headed_no_clearance_triggers_temporary_browser(self) -> None:
        fetcher = BrowserFetch()
        ctx = MagicMock()
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(MagicMock(), ctx)),
            patch.object(fetcher, "_has_cf_clearance", return_value=False),
            patch.object(fetcher, "_fetch_headed_and_seed", return_value="<html>headed</html>") as mock_headed,
        ):
            result = fetcher.fetch("https://spoj.com/test", "#content", headless=False)
        assert result == "<html>headed</html>"
        mock_headed.assert_called_once()

    def test_headed_with_clearance_skips_temporary_browser(self) -> None:
        fetcher = BrowserFetch()
        ctx = MagicMock()
        page = MagicMock()
        page.content.return_value = "<html>headless</html>"
        ctx.new_page.return_value = page
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(MagicMock(), ctx)),
            patch.object(fetcher, "_has_cf_clearance", return_value=True),
            patch.object(fetcher, "_fetch_headed_and_seed") as mock_headed,
        ):
            result = fetcher.fetch("https://spoj.com/test", "#content", headless=False)
        assert result == "<html>headless</html>"
        mock_headed.assert_not_called()

    def test_headless_never_checks_clearance(self) -> None:
        fetcher = BrowserFetch()
        ctx = MagicMock()
        page = MagicMock()
        page.content.return_value = "<html>headless</html>"
        ctx.new_page.return_value = page
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(MagicMock(), ctx)),
            patch.object(fetcher, "_has_cf_clearance") as mock_has,
            patch.object(fetcher, "_fetch_headed_and_seed") as mock_headed,
        ):
            result = fetcher.fetch("https://codeforces.com/test", "#content", headless=True)
        assert result == "<html>headless</html>"
        mock_has.assert_not_called()
        mock_headed.assert_not_called()

    def test_fetch_headed_and_seed_copies_only_cloudflare_cookies(self) -> None:
        fetcher = BrowserFetch()
        headless_ctx = MagicMock()
        pw = MagicMock()
        mock_browser = MagicMock()
        pw.chromium.launch.return_value = mock_browser
        temp_ctx = MagicMock()
        mock_browser.new_context.return_value = temp_ctx
        page = MagicMock()
        page.content.return_value = "<html>test</html>"
        temp_ctx.new_page.return_value = page
        temp_ctx.storage_state.return_value = {
            "cookies": [
                {
                    "name": "cf_clearance",
                    "value": "abc",
                    "domain": ".spoj.com",
                    "path": "/",
                    "expires": 9999999999.0,
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                },
                {
                    "name": "__cf_bm",
                    "value": "def",
                    "domain": ".spoj.com",
                    "path": "/",
                    "expires": 9999999999.0,
                    "httpOnly": True,
                    "secure": True,
                    "sameSite": "None",
                },
                {
                    "name": "session_id",
                    "value": "xyz",
                    "domain": ".spoj.com",
                    "path": "/",
                    "expires": -1.0,
                    "httpOnly": False,
                    "secure": False,
                    "sameSite": "Lax",
                },
            ]
        }

        result = fetcher._fetch_headed_and_seed(pw, headless_ctx, "https://spoj.com/test", "#content")

        assert result == "<html>test</html>"
        headless_ctx.add_cookies.assert_called_once()
        cookie_names = {c["name"] for c in headless_ctx.add_cookies.call_args[0][0]}
        assert cookie_names == {"cf_clearance", "__cf_bm"}


class TestFetcherInjection:
    """Verify that BrowserFetch is injected into parsers and shared across calls."""

    def test_get_parser_passes_fetcher(self) -> None:
        fetcher = BrowserFetch()
        parser = get_parser("https://codeforces.com/problemset/problem/1/A", fetcher)
        assert parser is not None
        assert parser._fetcher is fetcher

    def test_get_parser_without_fetcher_defaults_to_none(self) -> None:
        parser = get_parser("https://codeforces.com/problemset/problem/1/A")
        assert parser is not None
        assert parser._fetcher is None

    def test_fetch_page_raises_without_fetcher(self) -> None:
        parser = CodeforcesParser()
        with pytest.raises(RuntimeError):
            _ = parser.fetch_page("https://codeforces.com/problemset/problem/1/A")

    def test_multiple_parsers_share_one_fetcher(self) -> None:
        fetcher = BrowserFetch()
        p1 = get_parser("https://codeforces.com/problemset/problem/1/A", fetcher)
        p2 = get_parser("https://cses.fi/problemset/task/1083", fetcher)
        assert p1 is not None and p2 is not None
        assert p1._fetcher is fetcher
        assert p2._fetcher is fetcher


class TestBrowserFetchContextManager:
    """Verify BrowserFetch context manager protocol."""

    def test_context_manager_closes_on_exit(self) -> None:
        fetcher = BrowserFetch()
        with patch.object(fetcher, "close") as mock_close, fetcher:
            pass
        mock_close.assert_called_once()

    def test_context_manager_returns_self(self) -> None:
        fetcher = BrowserFetch()
        with fetcher as ctx:
            assert ctx is fetcher


class TestBrowserFetchRetry:
    """Verify that transient failures are retried with backoff."""

    def test_retries_on_failure_then_succeeds(self) -> None:
        fetcher = BrowserFetch()
        ctx = MagicMock()
        page = MagicMock()
        page.content.return_value = "<html>ok</html>"
        ctx.new_page.return_value = page
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(MagicMock(), ctx)),
            patch.object(fetcher, "_fetch_once", side_effect=[TimeoutError, "<html>ok</html>"]),
            patch("cpfetch.cpparse.fetch.time.sleep"),
        ):
            result = fetcher.fetch("https://example.com", "#content")
        assert result == "<html>ok</html>"

    def test_exhausts_retries_then_returns_none(self) -> None:
        fetcher = BrowserFetch()
        ctx = MagicMock()
        ctx.new_page.return_value = MagicMock()
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(MagicMock(), ctx)),
            patch.object(fetcher, "_fetch_once", side_effect=TimeoutError),
            patch("cpfetch.cpparse.fetch.time.sleep"),
        ):
            result = fetcher.fetch("https://example.com", "#content")
        assert result is None

    def test_headed_retries_on_failure_then_succeeds(self) -> None:
        """Headed bootstrap path (headless=False, no clearance) retries on transient failure."""
        fetcher = BrowserFetch()
        ctx = MagicMock()
        pw = MagicMock()
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(pw, ctx)),
            patch.object(fetcher, "_has_cf_clearance", return_value=False),
            patch.object(
                fetcher,
                "_fetch_headed_and_seed",
                side_effect=[TimeoutError, "<html>headed-ok</html>"],
            ) as mock_headed,
            patch("cpfetch.cpparse.fetch.time.sleep"),
        ):
            result = fetcher.fetch("https://spoj.com/test", "#content", headless=False)
        assert result == "<html>headed-ok</html>"
        assert mock_headed.call_count == 2

    def test_headed_exhausts_retries_then_returns_none(self) -> None:
        """Headed bootstrap path returns None after exhausting retries."""
        fetcher = BrowserFetch()
        ctx = MagicMock()
        pw = MagicMock()
        with (
            patch.object(fetcher, "_ensure_headless", return_value=(pw, ctx)),
            patch.object(fetcher, "_has_cf_clearance", return_value=False),
            patch.object(fetcher, "_fetch_headed_and_seed", side_effect=TimeoutError) as mock_headed,
            patch("cpfetch.cpparse.fetch.time.sleep"),
        ):
            result = fetcher.fetch("https://spoj.com/test", "#content", headless=False)
        assert result is None
        assert mock_headed.call_count == _MAX_RETRIES + 1
