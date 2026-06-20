"""Playwright-based page fetcher.

Returns full-page HTML after waiting for a target selector.
"""

import atexit
import contextlib
import os
import platform as _platform
import sys

from playwright.sync_api import Browser, Playwright, sync_playwright


def _default_user_agent() -> str:
    system = _platform.system()
    if system == "Darwin":
        os_token = "Macintosh; Intel Mac OS X 10_15_7"
    elif system == "Windows":
        os_token = "Windows NT 10.0; Win64; x64"
    else:
        os_token = "X11; Linux x86_64"
    return f"Mozilla/5.0 ({os_token}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"


class PlaywrightFetch:
    """Fetch full page HTML via headless Chromium."""

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None

    def _get_browser(self) -> Browser:
        if self._browser is not None:
            return self._browser
        self._playwright = sync_playwright().start()
        args = ["--disable-blink-features=AutomationControlled"]
        if os.geteuid() == 0:
            args.insert(0, "--no-sandbox")
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=args,
        )
        return self._browser

    def fetch(self, url: str, selector: str) -> str | None:
        """Navigate to URL, wait for selector, return full page HTML."""
        try:
            browser = self._get_browser()
            ctx = browser.new_context(user_agent=_default_user_agent())
            try:
                page = ctx.new_page()
                # Evade basic headless Chromium detection.
                _ = page.add_init_script(
                    'Object.defineProperty(navigator, "webdriver", ' + "{get: () => undefined})",
                )
                _ = page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                _ = page.wait_for_selector(selector, timeout=30_000)
                return page.content()
            finally:
                ctx.close()
        except Exception as exc:
            print(
                f"error: Playwright fetch failed for {url}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None

    def cleanup(self) -> None:
        """Close the browser and stop the Playwright instance if running."""
        if self._browser is not None:
            with contextlib.suppress(Exception):
                self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                self._playwright.stop()
            self._playwright = None


playwright_fetch = PlaywrightFetch()
_ = atexit.register(playwright_fetch.cleanup)
