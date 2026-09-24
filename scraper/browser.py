"""
The Chrome session shared by every mode.

Opens pages in your real Google Chrome (via Playwright), so Amazon's JavaScript
bot check is passed the same way a normal visit would pass it. Every page load
is spaced 4-8 s from the previous one - fast paging gets blocked.
"""

import random
import time

from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
DELAY = (4, 8)  # seconds between page loads


class Blocked(Exception):
    """Amazon answered with a CAPTCHA instead of the page."""


class Browser:
    def __init__(self, show=False):
        self.show = show
        self.status = None  # HTTP status of the last page load
        self._last_load = 0.0

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(channel="chrome", headless=not self.show)
        ctx = self._browser.new_context(
            locale="en-GB", user_agent=USER_AGENT, viewport={"width": 1366, "height": 900},
        )
        self.page = ctx.new_page()
        return self

    def __exit__(self, *exc):
        for close in (self._browser.close, self._pw.stop):
            try:
                close()
            except Exception:
                pass  # already gone, e.g. Chrome was stopped by Ctrl+C
        return False

    def load(self, url, ready_selector, timeout=30_000):
        """Open url and wait for ready_selector. Returns True once it appears, False if
        it doesn't (self.status has the HTTP status). Raises Blocked on a CAPTCHA."""
        wait = self._last_load + random.uniform(*DELAY) - time.time()
        if wait > 0:
            time.sleep(wait)
        self.status = None
        try:
            resp = self.page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            self.status = resp.status if resp else None
            self.page.wait_for_selector(ready_selector, timeout=timeout)
            return True
        except PlaywrightTimeout:
            pass
        finally:
            self._last_load = time.time()
        if not self.is_blocked():
            return False
        if self.show:
            print("  Amazon is showing a CAPTCHA - solve it in the Chrome window (waiting up to 3 min)...")
            try:
                self.page.wait_for_selector(ready_selector, timeout=180_000)
                return True
            except PlaywrightTimeout:
                pass
        raise Blocked("Amazon blocked the request (CAPTCHA). Re-run with --show-browser and solve it.")

    def clear_cookies(self):
        self.page.context.clear_cookies()

    def html(self):
        return self.page.content()

    def is_blocked(self):
        html = self.page.content()
        return "validateCaptcha" in html or "Type the characters you see" in html
