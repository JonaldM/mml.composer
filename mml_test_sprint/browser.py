"""Playwright browser session management for MML test sprint."""
import base64
from typing import Optional

from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

from mml_test_sprint.config import (
    BASE_URL, LOGIN_EMAIL, LOGIN_PASSWORD,
    VIEWPORT_W, VIEWPORT_H, HEADLESS, NAV_TIMEOUT, WAIT_TIMEOUT
)
from mml_test_sprint.checks import Check, Status


class BrowserSession:
    """Single Playwright session with login and helper methods."""

    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._console_errors: list[str] = []

    def start(self):
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=HEADLESS)
        self._context = self._browser.new_context(
            viewport={"width": VIEWPORT_W, "height": VIEWPORT_H}
        )
        self.page = self._context.new_page()
        self.page.set_default_navigation_timeout(NAV_TIMEOUT)
        self.page.set_default_timeout(WAIT_TIMEOUT)
        self.page.on("console", self._on_console)
        self.page.on("pageerror", lambda e: self._console_errors.append(f"[PAGE ERROR] {e}"))

    def _on_console(self, msg):
        if msg.type in ("error", "warning"):
            text = msg.text
            # Filter known non-issues
            if "favicon" in text or "ERR_UNKNOWN_URL_SCHEME" in text:
                return
            self._console_errors.append(f"[{msg.type.upper()}] {text}")

    def drain_errors(self) -> list[str]:
        """Return and clear accumulated console errors."""
        errors = list(self._console_errors)
        self._console_errors.clear()
        return errors

    def login(self):
        """Log in to Odoo. Must be called once after start()."""
        self.page.goto(f"{BASE_URL}/web", wait_until="domcontentloaded")
        self.page.wait_for_timeout(2000)
        self.page.fill('input[name="login"]', LOGIN_EMAIL)
        self.page.fill('input[name="password"]', LOGIN_PASSWORD)
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(4000)
        if "/web/login" in self.page.url or "login" in self.page.url:
            raise RuntimeError("Login failed — check credentials in config.py")

    def goto(self, url: str, wait_ms: int = 4000):
        """Navigate to URL and wait for DOM + settle."""
        self.page.goto(url, wait_until="domcontentloaded")
        self.page.wait_for_timeout(wait_ms)

    def screenshot_b64(self, clip_top_only: bool = True) -> str:
        """Take a screenshot and return as base64 string."""
        if clip_top_only:
            clip = {"x": 0, "y": 0, "width": VIEWPORT_W, "height": VIEWPORT_H}
            png = self.page.screenshot(clip=clip)
        else:
            png = self.page.screenshot(full_page=False)
        return base64.b64encode(png).decode()

    def scroll_to_top(self):
        """Scroll Odoo content container to top."""
        self.page.evaluate(
            'const c = document.querySelector(".o_content"); if (c) c.scrollTop = 0;'
        )
        self.page.wait_for_timeout(300)

    def check_no_blank_page(self, name: str) -> Check:
        """Fail if o_form_sheet_bg is narrower than 100px (chatter-collapse bug)."""
        w = self.page.evaluate('''() => {
            const bg = document.querySelector(".o_form_sheet_bg");
            if (!bg) return 9999;
            return bg.getBoundingClientRect().width;
        }''')
        if w < 100:
            return Check(name, Status.FAIL,
                         f"Form sheet collapsed to {w:.0f}px — likely widget/chatter rendering bug")
        return Check(name, Status.PASS)

    def check_no_js_errors(self, name: str) -> Check:
        errors = self.drain_errors()
        if errors:
            return Check(name, Status.FAIL, "; ".join(errors[:3]))
        return Check(name, Status.PASS)

    def check_element_exists(self, selector: str, name: str,
                              description: str = "") -> Check:
        """Pass if at least one matching element exists in the DOM."""
        count = self.page.locator(selector).count()
        if count == 0:
            return Check(name, Status.FAIL,
                         f"Expected to find '{selector}' — {description or 'not found'}")
        return Check(name, Status.PASS, f"Found {count} match(es)")

    def check_text_visible(self, text: str, name: str) -> Check:
        """Pass if the text appears anywhere on the page."""
        count = self.page.locator(f"text={text}").count()
        if count == 0:
            return Check(name, Status.FAIL, f"Text '{text}' not found on page")
        return Check(name, Status.PASS)

    def check_no_error_dialog(self, name: str) -> Check:
        """Fail if Odoo error dialog is visible."""
        selectors = [".o_error_dialog", ".modal .alert-danger", ".o_notification_error"]
        for sel in selectors:
            if self.page.locator(sel).count() > 0:
                try:
                    msg = self.page.locator(sel).first.inner_text()
                except Exception:
                    msg = "(could not read error text)"
                return Check(name, Status.FAIL, f"Error dialog: {msg[:200]}")
        return Check(name, Status.PASS)

    def check_row_count(self, selector: str, min_rows: int, name: str) -> Check:
        """Pass if at least min_rows elements match selector."""
        count = self.page.locator(selector).count()
        if count < min_rows:
            return Check(name, Status.FAIL,
                         f"Expected >= {min_rows} rows matching '{selector}', got {count}")
        return Check(name, Status.PASS, f"{count} row(s) found")

    def snap(self, check: Check) -> Check:
        """Attach a screenshot to a check result and return it."""
        self.scroll_to_top()
        check.screenshot_b64 = self.screenshot_b64()
        return check

    def stop(self):
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
