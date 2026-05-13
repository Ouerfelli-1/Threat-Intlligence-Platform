import os
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENSHOTS_DIR = Path(__file__).resolve().parent.parent / "data" / "screenshots"


def _chromium_path() -> str:
    """Auto-discover the locally-installed Chromium executable."""
    base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    for candidate in sorted(base.glob("chromium-*"), reverse=True):
        exe = candidate / "chrome-win64" / "chrome.exe"
        if exe.exists():
            return str(exe)
    return ""


def take_screenshot(domain: str) -> str:
    """Take a full-page screenshot of a domain. Returns the saved file path."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize domain for safe filename: only keep alphanumeric, dots, hyphens
    safe_domain = re.sub(r'[^a-zA-Z0-9.\-]', '_', domain)[:200]
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"{safe_domain}_{timestamp}.png"
    filepath = SCREENSHOTS_DIR / filename

    chromium_exe = _chromium_path()

    try:
        with sync_playwright() as p:
            launch_opts = {"headless": True}
            if chromium_exe:
                launch_opts["executable_path"] = chromium_exe
            browser = p.chromium.launch(**launch_opts)
            try:
                page = browser.new_page()
                try:
                    page.goto(f"https://{domain}", timeout=30000)
                except Exception:
                    try:
                        page.goto(f"http://{domain}", timeout=30000)
                    except Exception:
                        print(f"[DomainWatch] Screenshot failed: could not load {domain}")
                        return ""
                try:
                    page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    pass  # proceed with screenshot even if networkidle times out
                page.screenshot(path=str(filepath), full_page=True)
            finally:
                browser.close()
    except Exception as e:
        print(f"[DomainWatch] Screenshot error for {domain}: {e}")
        return ""
    print(f"[DomainWatch] Screenshot saved to {filepath}")
    return str(filepath)

