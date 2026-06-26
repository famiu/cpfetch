"""Browser-based page fetcher.

Returns full-page HTML after waiting for a target selector. Sites gated by
Cloudflare Turnstile (SPOJ) require a headed browser; others run headless.

The first time a headed fetch is requested, a temporary headed browser is
launched to acquire the cf_clearance cookie. That cookie is then injected into
the persistent headless context so all subsequent fetches reuse it without
opening another visible window.
"""

import contextlib
import logging
import os
import time
from types import TracebackType

from patchright.sync_api import Browser, BrowserContext
from patchright.sync_api import Playwright as Driver
from patchright.sync_api import sync_playwright as sync_driver

_log = logging.getLogger(__name__)

_INIT_SCRIPT = 'Object.defineProperty(navigator, "webdriver", {get: () => undefined})'

_MAX_RETRIES = 2
_RETRY_BACKOFFS = (1.0, 2.0)


def _launch_args() -> list[str]:
    args = ["--disable-blink-features=AutomationControlled"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        args.insert(0, "--no-sandbox")
    return args


def _derive_user_agent(browser: Browser) -> str:
    """Read the bundled Chromium's default UA and strip the `Headless` token.

    A `HeadlessChrome` UA is blocked by some CDNs (e.g. Codeforces). Deriving
    the UA from the actual browser build guarantees the version string matches
    the installed Chromium instead of drifting against a hardcoded value.
    """
    ctx = browser.new_context()
    try:
        page = ctx.new_page()
        try:
            page.goto("about:blank")
            raw = page.evaluate("() => navigator.userAgent")
        finally:
            page.close()
    finally:
        with contextlib.suppress(Exception):
            ctx.close()
    return raw.replace("HeadlessChrome", "Chrome")


class BrowserFetch:
    """Fetch full page HTML via a headless browser with optional headed bootstrap.

    Maintains a single headless browser + context. When a headed fetch is
    requested and no cf_clearance cookie exists yet, a temporary headed browser
    is launched to obtain it; thereafter all fetches go through the headless
    context, reusing the clearance cookie.

    Use as a context manager to ensure cleanup, or call ``close()`` explicitly.
    """

    def __init__(self) -> None:
        self._driver: Driver | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._user_agent: str | None = None

    def __enter__(self) -> BrowserFetch:
        """Return self for use in a ``with`` block."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Close the browser and driver on context exit."""
        self.close()

    def _ensure_headless(self) -> tuple[Driver, BrowserContext]:
        if self._context is not None:
            if self._driver is None:
                raise RuntimeError
            return self._driver, self._context
        if self._driver is None:
            self._driver = sync_driver().start()
        self._browser = self._driver.chromium.launch(
            headless=True,
            args=_launch_args(),
        )
        try:
            if self._user_agent is None:
                self._user_agent = _derive_user_agent(self._browser)
            self._context = self._browser.new_context(user_agent=self._user_agent)
        except Exception:
            with contextlib.suppress(Exception):
                self._browser.close()
            self._browser = None
            raise
        return self._driver, self._context

    def _has_cf_clearance(self, ctx: BrowserContext, url: str) -> bool:
        cookies = ctx.cookies(url)
        now = time.time()
        for c in cookies:
            if c["name"] == "cf_clearance":
                expires = c.get("expires", -1)
                if expires is None or expires < 0 or expires > now:
                    return True
        return False

    def _fetch_headed_and_seed(self, pw: Driver, ctx: BrowserContext, url: str, selector: str) -> str:
        browser = pw.chromium.launch(headless=False, args=_launch_args())
        try:
            temp_ctx = browser.new_context(user_agent=self._user_agent or _derive_user_agent(browser))
            try:
                page = temp_ctx.new_page()
                page.add_init_script(_INIT_SCRIPT)
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_selector(selector, timeout=30_000)
                html = page.content()
                state = temp_ctx.storage_state()
                cf_cookies = [c for c in state.get("cookies", []) if c["name"] in ("cf_clearance", "__cf_bm")]
                if cf_cookies:
                    ctx.add_cookies(
                        [
                            {
                                "name": c["name"],
                                "value": c["value"],
                                "domain": c.get("domain"),
                                "path": c.get("path"),
                                "expires": c.get("expires", -1),
                                "httpOnly": c.get("httpOnly", False),
                                "secure": c.get("secure", False),
                                "sameSite": c.get("sameSite"),
                            }
                            for c in cf_cookies
                        ]
                    )
                return html
            finally:
                with contextlib.suppress(Exception):
                    temp_ctx.close()
        finally:
            with contextlib.suppress(Exception):
                browser.close()

    def _fetch_once(self, ctx: BrowserContext, url: str, selector: str) -> str:
        page = ctx.new_page()
        try:
            page.add_init_script(_INIT_SCRIPT)
            page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            page.wait_for_selector(selector, timeout=30_000)
            html = page.content()
        finally:
            with contextlib.suppress(Exception):
                page.close()
        return html

    def fetch(self, url: str, selector: str, *, headless: bool = True) -> str | None:
        """Navigate to URL, wait for selector, return full page HTML.

        When headless=False and no cf_clearance cookie is cached, a temporary
        headed browser is launched to acquire it; thereafter all fetches
        (including those with headless=False) reuse the headless context.

        Transient failures (headed bootstrap or headless fetch) are retried
        with backoff (up to ``_MAX_RETRIES`` additional attempts).
        """
        try:
            pw, ctx = self._ensure_headless()
            needs_headed = not headless and not self._has_cf_clearance(ctx, url)
            last_exc: Exception | None = None
            for attempt in range(_MAX_RETRIES + 1):
                try:
                    if needs_headed:
                        return self._fetch_headed_and_seed(pw, ctx, url, selector)
                    return self._fetch_once(ctx, url, selector)
                except Exception as exc:
                    last_exc = exc
                    if attempt < _MAX_RETRIES:
                        delay = _RETRY_BACKOFFS[attempt]
                        _log.warning(
                            "fetch attempt %d failed for %s: %s — retrying in %.1fs",
                            attempt + 1,
                            url,
                            exc,
                            delay,
                        )
                        time.sleep(delay)
            else:
                _log.error("fetch failed for %s after %d attempts: %s", url, _MAX_RETRIES + 1, last_exc)
                return None
        except Exception as exc:
            _log.error("fetch failed for %s: %s", url, exc)
            return None

    def request_get(self, url: str) -> object | None:
        """Fetch JSON from *url* via the browser context's request API.

        Returns the parsed JSON value, or None if the request fails or the
        response is not valid JSON. The caller is responsible for validating
        the shape of the returned value.
        """
        try:
            _, ctx = self._ensure_headless()
            response = ctx.request.get(url, timeout=10_000)
            if not response.ok:
                _log.warning("API request to %s returned status %d", url, response.status)
                return None
            return response.json()
        except Exception as exc:
            _log.warning("API request to %s failed: %s", url, exc)
            return None

    def close(self) -> None:
        """Close the cached context and browser and stop the driver if running."""
        if self._context is not None:
            with contextlib.suppress(Exception):
                self._context.close()
            self._context = None
        if self._browser is not None:
            with contextlib.suppress(Exception):
                self._browser.close()
            self._browser = None
        if self._driver is not None:
            with contextlib.suppress(Exception):
                self._driver.stop()
            self._driver = None
