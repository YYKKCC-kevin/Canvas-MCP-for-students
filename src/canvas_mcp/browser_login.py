"""Browser login helper for Canvas SSO and Duo flows."""

from __future__ import annotations

import getpass
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv


DEFAULT_BASE_URL = "https://canvas.eee.uci.edu"
DEFAULT_STORAGE_STATE = ".canvas-storage-state.json"

USERNAME_SELECTORS = [
    'input[name="pseudonym_session[unique_id]"]',
    'input[name="username"]',
    'input[name="j_username"]',
    'input[name="UserName"]',
    'input[name="user"]',
    'input[name="ucinetid"]',
    'input[name="loginfmt"]',
    'input[name="urn:mace:ucsd.edu:sso:username"]',
    'input[autocomplete="username"]',
    'input[type="email"]',
    "#username",
    "#j_username",
    "#UserName",
    "#user",
    "#ucinetid",
    "#ssousername",
    "#i0116",
]

PASSWORD_SELECTORS = [
    'input[name="pseudonym_session[password]"]',
    'input[name="password"]',
    'input[name="j_password"]',
    'input[name="Password"]',
    'input[name="passwd"]',
    'input[name="urn:mace:ucsd.edu:sso:password"]',
    'input[autocomplete="current-password"]',
    'input[type="password"]',
    "#password",
    "#j_password",
    "#Password",
    "#ssopassword",
    "#i0118",
]

SUBMIT_SELECTORS = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Log In")',
    'button:has-text("Login")',
    'button:has-text("Sign In")',
    'button:has-text("Continue")',
    'input[value="Log In"]',
    'input[value="Login"]',
    'input[value="Sign In"]',
    'input[value="Continue"]',
    "#idSIButton9",
]

POST_LOGIN_ACTION_PATTERNS = [
    r"^skip( for now)?$",
    r"^not now$",
    r"^maybe later$",
    r"^yes,? this is my device$",
    r"^this is my device$",
    r"^trust this (browser|device)$",
    r"^remember (me|this (browser|device))$",
    r"^don't ask again$",
    r"^continue( to canvas)?$",
    r"^暂时跳过$",
    r"^跳过$",
    r"^稍后再说$",
    r"^以后再说$",
    r"^是我的设备$",
    r"^这是我的设备$",
    r"^信任此浏览器$",
    r"^信任此设备$",
    r"^记住我$",
    r"^记住此浏览器$",
    r"^记住此设备$",
    r"^不要再询问$",
    r"^继续$",
]


def normalize_base_url(value: str | None) -> str:
    base_url = (value or DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    if not base_url.startswith(("http://", "https://")):
        base_url = f"https://{base_url}"
    return base_url.rstrip("/")


def canvas_settings_url(base_url: str) -> str:
    return urljoin(f"{normalize_base_url(base_url)}/", "profile/settings")


def _canvas_host(value: str) -> str:
    return (urlparse(normalize_base_url(value)).hostname or "").lower()


def _is_canvas_authenticated_url(page_url: str, base_url: str) -> bool:
    parsed = urlparse(page_url)
    if (parsed.hostname or "").lower() != _canvas_host(base_url):
        return False

    path = parsed.path.lower()
    login_markers = ("/login", "/saml", "/oauth", "/auth")
    return not any(marker in path for marker in login_markers)


def _is_post_login_action_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if not normalized:
        return False
    return any(re.fullmatch(pattern, normalized) for pattern in POST_LOGIN_ACTION_PATTERNS)


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _first_visible(page, selectors: list[str], timeout_ms: int = 750):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            if locator.count() and locator.is_visible(timeout=timeout_ms):
                return locator
        except Exception:
            continue
    return None


def _fill_if_available(page, selectors: list[str], value: str) -> bool:
    locator = _first_visible(page, selectors)
    if locator is None:
        return False
    locator.fill(value)
    return True


def _click_if_available(page, selectors: list[str]) -> bool:
    locator = _first_visible(page, selectors)
    if locator is None:
        return False
    locator.click()
    return True


def _click_post_login_action_if_available(page) -> bool:
    locators = [
        page.locator("button"),
        page.locator("input[type=submit]"),
        page.locator("input[type=button]"),
        page.locator("a"),
    ]
    for locator in locators:
        try:
            count = min(locator.count(), 30)
        except Exception:
            continue
        for index in range(count):
            item = locator.nth(index)
            try:
                if not item.is_visible(timeout=250):
                    continue
                text = _login_action_text(item)
                if _is_post_login_action_text(text):
                    item.click(timeout=1000)
                    return True
            except Exception:
                continue
    return False


def _login_action_text(locator) -> str:
    pieces = []
    for getter in (
        lambda: locator.inner_text(timeout=250),
        lambda: locator.get_attribute("value", timeout=250),
        lambda: locator.get_attribute("aria-label", timeout=250),
        lambda: locator.get_attribute("title", timeout=250),
    ):
        try:
            value = getter()
        except Exception:
            continue
        if value:
            pieces.append(value)
    return " ".join(pieces)


def _attempt_login_fill(page, username: str, password: str, seconds: int = 45) -> None:
    deadline = time.monotonic() + seconds
    filled_username = False
    filled_password = False
    while time.monotonic() < deadline:
        if not filled_username:
            filled_username = _fill_if_available(page, USERNAME_SELECTORS, username)
        if not filled_password:
            filled_password = _fill_if_available(page, PASSWORD_SELECTORS, password)
        if filled_username and filled_password:
            _click_if_available(page, SUBMIT_SELECTORS)
            return
        if filled_username and not filled_password:
            _click_if_available(page, SUBMIT_SELECTORS)
        page.wait_for_timeout(1000)


def _wait_for_canvas_session(page, base_url: str, seconds: int) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if _is_canvas_authenticated_url(page.url, base_url):
            return True
        _click_post_login_action_if_available(page)
        page.wait_for_timeout(1000)
    return False


def _launch_browser(playwright, headless: bool):
    channel = os.environ.get("CANVAS_BROWSER_CHANNEL", "").strip() or None
    try:
        return playwright.chromium.launch(headless=headless, channel=channel)
    except Exception:
        if channel:
            return playwright.chromium.launch(headless=headless)
        raise


def _env_path() -> Path:
    return Path(os.environ.get("CANVAS_STORAGE_STATE", DEFAULT_STORAGE_STATE)).expanduser()


def main() -> None:
    load_dotenv()
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise SystemExit(
            "Browser login requires Playwright. Install it with:\n"
            '  pip install -e ".[browser]"\n'
            "  python -m playwright install chromium"
        ) from exc

    base_url = normalize_base_url(os.environ.get("CANVAS_BASE_URL"))
    username = (
        os.environ.get("CANVAS_EMAIL", "").strip()
        or os.environ.get("CANVAS_USERNAME", "").strip()
        or input("Canvas username/email: ").strip()
    )
    password = os.environ.get("CANVAS_PASSWORD", "").strip()
    if not password:
        password = getpass.getpass("Canvas password: ").strip()
    if not username or not password:
        raise SystemExit("Missing Canvas username/email or password.")

    storage_state = _env_path()
    login_url = canvas_settings_url(base_url)
    headless = _truthy(os.environ.get("CANVAS_HEADLESS"))
    login_wait_seconds = int(os.environ.get("CANVAS_LOGIN_WAIT_SECONDS", "180"))

    print("Canvas MCP browser login")
    print(f"Opening {login_url}")
    print(
        "The browser will use your username/password, wait for Duo, "
        "then save automatically once Canvas loads."
    )

    try:
        with sync_playwright() as p:
            browser = _launch_browser(p, headless=headless)
            context = browser.new_context()
            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded")
            if not _is_canvas_authenticated_url(page.url, base_url):
                _attempt_login_fill(page, username, password)
            print(f"Waiting up to {login_wait_seconds} seconds for Canvas to load...")
            if _wait_for_canvas_session(page, base_url, login_wait_seconds):
                print("Detected Canvas page; saving session automatically.")
            else:
                input(
                    "\nCanvas was not detected automatically. If Canvas is already "
                    "loaded in the browser, press Enter to save the session..."
                )
            storage_state.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(storage_state))
            browser.close()
    except Exception as exc:
        message = str(exc)
        if "Executable doesn't exist" in message or "playwright install" in message:
            raise SystemExit(
                "Playwright is installed but Chromium is missing. Run:\n"
                "  python -m playwright install chromium"
            ) from exc
        raise

    print(f"Saved Canvas browser session to {storage_state}")
    print("You can now run `canvas-mcp`.")
