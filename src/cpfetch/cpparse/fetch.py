"""Browser-based page fetcher.

Returns full-page HTML after waiting for a target selector. Sites gated by
Cloudflare Turnstile (SPOJ) require a headed browser; others run headless.

The first time a headed fetch is requested, a temporary headed browser is
launched to acquire the cf_clearance cookie. That cookie is then injected into
the persistent headless context so all subsequent fetches reuse it without
opening another visible window.
"""

import atexit
import contextlib
import os
import platform as _platform
import sys
import time

from patchright.sync_api import Browser, BrowserContext, Playwright, sync_playwright


def _default_user_agent() -> str:
    system = _platform.system()
    if system == "Darwin":
        os_token = "Macintosh; Intel Mac OS X 10_15_7"
    elif system == "Windows":
        os_token = "Windows NT 10.0; Win64; x64"
    else:
        os_token = "X11; Linux x86_64"
    return f"Mozilla/5.0 ({os_token}) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36"


def _launch_args() -> list[str]:
    args = ["--disable-blink-features=AutomationControlled"]
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        args.insert(0, "--no-sandbox")
    return args


class BrowserFetch:
    """Fetch full page HTML via a headless browser with optional headed bootstrap.

    Maintains a single headless browser + context. When a headed fetch is
    requested and no cf_clearance cookie exists yet, a temporary headed browser
    is launched to obtain it; thereafter all fetches go through the headless
    context, reusing the clearance cookie.
    """

    def __init__(self) -> None:
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None

    def _ensure_headless(self) -> tuple[Playwright, BrowserContext]:
        if self._context is not None:
            assert self._playwright is not None
            return self._playwright, self._context
        if self._playwright is None:
            self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=True,
            args=_launch_args(),
        )
        self._context = self._browser.new_context(user_agent=_default_user_agent())
        return self._playwright, self._context

    def _has_cf_clearance(self, ctx: BrowserContext, url: str) -> bool:
        cookies = ctx.cookies(url)
        now = time.time()
        for c in cookies:
            if c["name"] == "cf_clearance":
                expires = c.get("expires", -1)
                if expires is None or expires < 0 or expires > now:
                    return True
        return False

    def _fetch_headed_and_seed(self, pw: Playwright, ctx: BrowserContext, url: str, selector: str) -> str:
        browser = pw.chromium.launch(headless=False, args=_launch_args())
        temp_ctx = browser.new_context(user_agent=_default_user_agent())
        try:
            page = temp_ctx.new_page()
            page.add_init_script(
                'Object.defineProperty(navigator, "webdriver", ' + "{get: () => undefined})",
            )
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
            with contextlib.suppress(Exception):
                browser.close()

    def fetch(self, url: str, selector: str, *, headless: bool = True) -> str | None:
        """Navigate to URL, wait for selector, return full page HTML.

        When headless=False and no cf_clearance cookie is cached, a temporary
        headed browser is launched once to acquire it; thereafter all fetches
        (including those with headless=False) reuse the headless context.
        """
        try:
            pw, ctx = self._ensure_headless()
            if not headless and not self._has_cf_clearance(ctx, url):
                return self._fetch_headed_and_seed(pw, ctx, url, selector)
            page = ctx.new_page()
            try:
                page.add_init_script(
                    'Object.defineProperty(navigator, "webdriver", ' + "{get: () => undefined})",
                )
                page.goto(url, wait_until="domcontentloaded", timeout=30_000)
                page.wait_for_selector(selector, timeout=30_000)
                return page.content()
            finally:
                page.close()
        except Exception as exc:
            print(
                f"error: Patchright fetch failed for {url}: {exc}",
                file=sys.stderr,
                flush=True,
            )
            return None

    def cleanup(self) -> None:
        """Close the cached context and browser and stop Patchright if running."""
        if self._context is not None:
            with contextlib.suppress(Exception):
                self._context.close()
            self._context = None
        if self._browser is not None:
            with contextlib.suppress(Exception):
                self._browser.close()
            self._browser = None
        if self._playwright is not None:
            with contextlib.suppress(Exception):
                self._playwright.stop()
            self._playwright = None


browser_fetch = BrowserFetch()
_ = atexit.register(browser_fetch.cleanup)
