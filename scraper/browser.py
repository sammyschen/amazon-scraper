"""
The Chrome session shared by every mode.

Opens pages in your real Google Chrome (via Playwright), so Amazon's JavaScript
bot check is passed the same way a normal visit would pass it. Every page load
is spaced 4-8 s from the previous one - fast paging gets blocked.

At the start of a run the session's delivery location is set to DELIVERY_ZIP
(through Amazon's own "Deliver to" box) and checked on every page after that.
"""

import random
import time

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from .config import AMAZON_DOMAIN, BASE, DELIVERY_ZIP, LOCALE

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)
DELAY = (4, 8)  # seconds between page loads
LOCATION_LINE = "#glow-ingress-line2"  # the "Deliver to ..." text in Amazon's header


class Blocked(Exception):
    """Amazon answered with a CAPTCHA instead of the page."""


class Browser:
    def __init__(self, show=False, zip_code=DELIVERY_ZIP):
        self.show = show
        self.zip_code = zip_code
        self.status = None        # HTTP status of the last page load
        self.location = ""        # what Amazon shows after "Deliver to"
        self.zip_applied = False
        self._last_load = 0.0
        self._session_cookies = None  # cookie jar right after the ZIP was set
        self._fixing_location = False

    def __enter__(self):
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(channel="chrome", headless=not self.show)
        ctx = self._browser.new_context(
            locale=LOCALE, user_agent=USER_AGENT, viewport={"width": 1366, "height": 900},
        )
        self.page = ctx.new_page()
        if self.zip_code:
            self.set_location()
        return self

    def __exit__(self, *exc):
        for close in (self._browser.close, self._pw.stop):
            try:
                close()
            except Exception:
                pass  # already gone, e.g. Chrome was stopped by Ctrl+C
        return False

    # ------------------------------------------------------------ loading ---

    def load(self, url, ready_selector, timeout=30_000):
        """Open url and wait for ready_selector. Returns True once it appears, False if
        it doesn't (self.status has the HTTP status). Raises Blocked on a CAPTCHA.
        If the page shows a different delivery location, the ZIP is applied again."""
        if not self._open(url, ready_selector, timeout):
            return False
        if self.zip_applied and not self._fixing_location:
            shown = self.shown_location()
            if shown and self.zip_code not in shown:
                print(f"  WARNING: delivery location changed to '{shown}' - re-applying ZIP {self.zip_code}")
                self._fixing_location = True
                try:
                    if self.set_location():
                        return self._open(url, ready_selector, timeout)
                finally:
                    self._fixing_location = False
        return True

    def _open(self, url, ready_selector, timeout):
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

    def html(self):
        return self.page.content()

    def is_blocked(self):
        html = self.page.content()
        return "validateCaptcha" in html or "Type the characters you see" in html

    # ----------------------------------------------------------- location ---

    def shown_location(self):
        """The 'Deliver to' location on the current page, e.g. 'New York 10010' ('' if none)."""
        try:
            line = self.page.locator(LOCATION_LINE).first.inner_text(timeout=2_000)
        except PlaywrightError:
            return ""
        return line.replace("‌", "").strip()

    def set_location(self, attempts=3):
        """Set the delivery ZIP through Amazon's 'Deliver to' box and verify it.
        Returns True when Amazon shows the ZIP; otherwise prints a warning."""
        print(f"Delivery location: setting ZIP {self.zip_code} on {AMAZON_DOMAIN} ...")
        for _ in range(attempts):
            try:
                if not self._open(f"{BASE}/", "#nav-global-location-popover-link", 30_000):
                    continue
                self.page.wait_for_load_state("load", timeout=30_000)  # the box needs the page's scripts
                if self.zip_code not in self.shown_location():
                    self.page.click("#nav-global-location-popover-link")
                    self.page.wait_for_selector("#GLUXZipUpdateInput", state="visible", timeout=10_000)
                    self.page.fill("#GLUXZipUpdateInput", self.zip_code)
                    self.page.click("#GLUXZipUpdate")
                    done = self.page.locator(".a-popover-footer .a-button-input, #GLUXConfirmClose").first
                    try:
                        done.wait_for(state="visible", timeout=10_000)
                        done.click()
                    except PlaywrightError:
                        pass  # some versions of the box close by themselves
                    self.page.wait_for_timeout(2_000)
                    self.page.reload(wait_until="domcontentloaded")
                    self.page.wait_for_selector(LOCATION_LINE, timeout=20_000)
                    self._last_load = time.time()
                self.location = self.shown_location()
                if self.zip_code in self.location:
                    self.zip_applied = True
                    self._session_cookies = self.page.context.cookies()
                    print(f"Delivery location: {self.location}\n")
                    return True
            except Blocked:
                raise
            except PlaywrightError:
                continue
        self.location = self.shown_location() or self.location
        self.zip_applied = False
        print(f"WARNING: could not set the delivery ZIP to {self.zip_code} - Amazon shows "
              f"'{self.location or 'unknown'}'. Delivery, stock and offers are for that location, "
              f"and prices shown in another currency are left blank.\n")
        return False

    def restore_session(self):
        """Go back to the cookies saved right after the ZIP was set (keeps the location)."""
        ctx = self.page.context
        ctx.clear_cookies()
        if self._session_cookies:
            ctx.add_cookies(self._session_cookies)
