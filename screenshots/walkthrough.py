"""End-to-end Playwright walkthrough of the TIP platform.

Captures one full-page screenshot per major view (40+ shots) for the
report deliverable. Numbered prefixes keep files sorted in the order an
analyst would naturally encounter them.

Usage:
    python screenshots/walkthrough.py

Targets http://192.168.150.135:3000 by default — override with PLATFORM_URL
env var if running against a different host.

Resilience:
    - Each capture is wrapped in try/except so one missing page never
      breaks the whole run.
    - Detail-page captures resolve the target id from the list query
      result (no hard-coded UUIDs).
    - For pages whose data is empty (no threats, no IOCs, etc.) the
      empty-state UI is captured instead of skipping.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from playwright.sync_api import (
    Page, TimeoutError as PWTimeout, sync_playwright,
)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except Exception:
    pass

PLATFORM_URL = os.environ.get("PLATFORM_URL", "http://192.168.150.135:3000")
ADMIN_USER   = os.environ.get("ADMIN_USER", "admin")
ADMIN_PW     = os.environ.get("ADMIN_PW", "changeme")
OUT_DIR      = Path(__file__).resolve().parent

# How long to wait for navigations / network to settle. Some pages
# (dashboard with fan-out, ASM with health probes) take a moment.
NAV_TIMEOUT_MS = 30_000


def shot(page: Page, name: str, full: bool = True) -> None:
    """Take a screenshot, prefix-numbered for sort order."""
    # We track a counter via a closure inside main() instead of a global —
    # see _make_shot.
    raise RuntimeError("use _make_shot from main()")


def _make_shot(page: Page):
    counter = {"i": 0}
    def go(name: str, full: bool = True) -> None:
        counter["i"] += 1
        n = counter["i"]
        path = OUT_DIR / f"{n:02d}_{name}.png"
        try:
            # Wait briefly for any animation / async render. We don't
            # block on networkidle here because some pages keep a 30s
            # poll (/me, etc.) that would never settle.
            page.wait_for_timeout(600)
            page.screenshot(path=str(path), full_page=full, timeout=15_000)
            print(f"  [{n:02d}] {name:42s} -> {path.name}")
        except Exception as e:
            print(f"  [{n:02d}] {name:42s} FAILED: {e!s:.150}")
    return go


def safe_goto(page: Page, url: str, *, wait_selector: str | None = None,
              wait_timeout: int = NAV_TIMEOUT_MS) -> bool:
    """Navigate + wait for the page shell. Returns True on success."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=wait_timeout)
        if wait_selector:
            page.wait_for_selector(wait_selector, timeout=wait_timeout)
        # Settle: SWR + initial fetches usually land within ~1.5s after DOMContent.
        page.wait_for_timeout(1800)
        return True
    except PWTimeout as e:
        print(f"  [nav] {url} timeout: {e!s:.120}")
        return False
    except Exception as e:
        print(f"  [nav] {url} error: {e!s:.120}")
        return False


def try_click(page: Page, selector: str, timeout: int = 5_000) -> bool:
    """Click the first match if it exists. Never raises."""
    try:
        page.locator(selector).first.click(timeout=timeout)
        page.wait_for_timeout(700)
        return True
    except Exception as e:
        print(f"  [click] {selector} -> {e!s:.100}")
        return False


def main() -> int:
    print(f"\n  TIP walkthrough → {PLATFORM_URL}")
    print(f"  user: {ADMIN_USER}    out: {OUT_DIR}\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 1440x900 — wide enough for two-column dashboards, narrow enough
        # that the screenshots render reasonably embedded in a PDF.
        ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                                  device_scale_factor=1)
        page = ctx.new_page()
        shot = _make_shot(page)

        # ── Login ──────────────────────────────────────────────────────
        print("\n[1/8] Auth")
        if not safe_goto(page, f"{PLATFORM_URL}/login",
                         wait_selector='input[type="password"]'):
            print("  could not reach platform; aborting")
            return 1
        shot("login")

        # Fill credentials. Both inputs carry standard autoComplete
        # attributes which give us stable, unique selectors regardless of
        # form layout changes.
        try:
            page.locator('input[autocomplete="username"]').first.fill(ADMIN_USER)
            page.locator('input[autocomplete="current-password"]').first.fill(ADMIN_PW)
            # Submit via Enter — avoids hunting for the button label.
            page.locator('input[autocomplete="current-password"]').first.press("Enter")
        except Exception as e:
            print(f"  login fill failed: {e}")
            return 2

        # After login the layout polls /me; wait for any element of the
        # app shell to be visible.
        try:
            page.wait_for_url(f"{PLATFORM_URL}/", timeout=NAV_TIMEOUT_MS)
        except PWTimeout:
            # Some installs redirect to /dashboard or land on /. If the
            # URL didn't move, just wait for sidebar to mount.
            pass
        try:
            page.wait_for_selector("text=Daily Threat Briefing", timeout=NAV_TIMEOUT_MS)
        except PWTimeout:
            # Fall back to any heading; dashboard variants may differ.
            page.wait_for_timeout(3000)

        # ── Dashboard ──────────────────────────────────────────────────
        print("\n[2/8] Dashboard")
        safe_goto(page, f"{PLATFORM_URL}/",
                  wait_selector="text=Daily Threat Briefing")
        shot("dashboard")

        # ── Intelligence ───────────────────────────────────────────────
        print("\n[3/8] Intelligence")
        # Articles
        # NB: the earlier wait_selector mixed CSS + Playwright text= which
        # Playwright treats as pure CSS and times out finding "text" tags.
        # Use a plain CSS selector list throughout.
        if safe_goto(page, f"{PLATFORM_URL}/intelligence/articles",
                     wait_selector=".card, table"):
            shot("articles_list")
            # Click first row → detail.
            if try_click(page, "table tbody tr"):
                page.wait_for_timeout(1500)
                shot("article_detail")
                # Insight tab (right pane). The tabs are <div class="tab">.
                if try_click(page, "div.tab:has-text('insight')"):
                    page.wait_for_timeout(1500)
                    shot("article_detail_insight_tab")

        # CVEs
        if safe_goto(page, f"{PLATFORM_URL}/intelligence/cves",
                     wait_selector="table"):
            shot("cves_list")
            if try_click(page, "table tbody tr"):
                page.wait_for_timeout(1500)
                shot("cve_detail")

        # Threats (general)
        if safe_goto(page, f"{PLATFORM_URL}/intelligence/threats",
                     wait_selector="table, .card"):
            shot("threats_list")
            if try_click(page, "table tbody tr"):
                page.wait_for_timeout(1500)
                shot("threat_detail")

        # Supply chain (drawer-based)
        if safe_goto(page, f"{PLATFORM_URL}/intelligence/supply-chain",
                     wait_selector="table, .card"):
            shot("supply_chain_list")
            if try_click(page, "table tbody tr"):
                page.wait_for_timeout(1500)
                shot("supply_chain_drawer")
                # Close drawer by pressing Escape so subsequent navs are clean.
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)

        # Ransomware (path is /intelligence/ransomware OR /actors/ransomware
        # depending on the build — try both, capture first that responds).
        for url in (f"{PLATFORM_URL}/intelligence/ransomware",
                    f"{PLATFORM_URL}/actors/ransomware"):
            if safe_goto(page, url, wait_selector=".card, table"):
                shot("ransomware")
                break

        # ── IOCs ───────────────────────────────────────────────────────
        print("\n[4/8] IOCs")
        if safe_goto(page, f"{PLATFORM_URL}/iocs", wait_selector="table"):
            shot("iocs_library")
            # First row → detail
            if try_click(page, "table tbody tr"):
                page.wait_for_timeout(1500)
                shot("ioc_detail")

        # Investigate (empty state first, then with a search)
        if safe_goto(page, f"{PLATFORM_URL}/iocs/investigate",
                     wait_selector="input"):
            shot("ioc_investigate_empty")
            # Search for a well-known IP; result populates the panels.
            try:
                # Find the search input (usually a single visible text input).
                search = page.locator('input[type="text"], input[placeholder*="ip" i], input[placeholder*="domain" i]').first
                search.fill("8.8.8.8")
                search.press("Enter")
                # Investigation is async; poll for the "Network intelligence"
                # section to appear or give up after ~25s.
                try:
                    page.wait_for_selector("text=Network intelligence", timeout=25_000)
                    page.wait_for_timeout(1500)
                except PWTimeout:
                    page.wait_for_timeout(3000)
                shot("ioc_investigate_result")

                # Expand the Google dorking panel (collapsible).
                if try_click(page, "text=Google dorking"):
                    page.wait_for_timeout(1500)
                    shot("ioc_investigate_dorking")
            except Exception as e:
                print(f"  investigate query failed: {e}")

        # ── Actors ─────────────────────────────────────────────────────
        print("\n[5/8] Actors")
        if safe_goto(page, f"{PLATFORM_URL}/actors", wait_selector="table"):
            shot("actors_list")
            if try_click(page, "table tbody tr"):
                page.wait_for_timeout(1500)
                shot("actor_profile_overview")
                # AI insight tab — Playwright doesn't allow mixed CSS+text
                # syntax inside a single selector; use :has-text() only.
                if try_click(page, "button:has-text('AI insight')"):
                    page.wait_for_timeout(1500)
                    shot("actor_ai_insight_tab")
                # TTPs tab
                if try_click(page, "button:has-text('TTPs')"):
                    page.wait_for_timeout(1500)
                    shot("actor_ttps_tab")

        # ── Assets / CMDB ──────────────────────────────────────────────
        print("\n[6/8] Assets")
        if safe_goto(page, f"{PLATFORM_URL}/assets", wait_selector=".card, table"):
            shot("assets_list")
        if safe_goto(page, f"{PLATFORM_URL}/assets/profile",
                     wait_selector=".card"):
            shot("assets_company_profile")

        # ── Surface (ASM + DomainWatch) ────────────────────────────────
        print("\n[7/8] Attack surface")
        if safe_goto(page, f"{PLATFORM_URL}/surface/scopes",
                     wait_selector=".card"):
            shot("asm_scopes")
        # Findings may be empty (no scans run yet). Use a shorter wait
        # so the empty-state UI is captured instead of timing out.
        if safe_goto(page, f"{PLATFORM_URL}/surface/findings",
                     wait_selector="body", wait_timeout=10_000):
            page.wait_for_timeout(2000)
            shot("asm_findings")
        if safe_goto(page, f"{PLATFORM_URL}/surface/domains",
                     wait_selector=".card"):
            shot("domainwatch")

        # ── Integrations ───────────────────────────────────────────────
        if safe_goto(page, f"{PLATFORM_URL}/integrations/wazuh",
                     wait_selector=".card"):
            shot("integrations_wazuh")
        if safe_goto(page, f"{PLATFORM_URL}/integrations/misp",
                     wait_selector=".card"):
            shot("integrations_misp")

        # ── Operations + AI ────────────────────────────────────────────
        print("\n[8/8] Ops + AI + Admin + Settings")
        if safe_goto(page, f"{PLATFORM_URL}/operations/scheduler",
                     wait_selector=".card, table"):
            shot("scheduler")
        if safe_goto(page, f"{PLATFORM_URL}/operations/policies",
                     wait_selector=".card, table"):
            shot("ai_policies")
        if safe_goto(page, f"{PLATFORM_URL}/operations/reports",
                     wait_selector=".card"):
            shot("reports")

        if safe_goto(page, f"{PLATFORM_URL}/ask", wait_selector="textarea, input"):
            shot("ask_ai_empty")

        if safe_goto(page, f"{PLATFORM_URL}/flowviz", wait_selector="textarea"):
            shot("flowviz")

        # Admin (3 sub-pages)
        for sub in ("users", "roles", "sessions"):
            if safe_goto(page, f"{PLATFORM_URL}/admin/{sub}",
                         wait_selector=".card, table"):
                shot(f"admin_{sub}")

        # Settings tabs — single page with internal tabbed UI
        if safe_goto(page, f"{PLATFORM_URL}/settings",
                     wait_selector="text=Settings"):
            # Default tab is RSS feeds.
            shot("settings_feeds")
            # Tags
            if try_click(page, "button:has-text('Tag catalog')"):
                page.wait_for_timeout(1200)
                shot("settings_tags")
            # AI providers
            if try_click(page, "button:has-text('AI providers')"):
                page.wait_for_timeout(1200)
                shot("settings_ai_providers")
            # Notifications
            if try_click(page, "button:has-text('Notifications')"):
                page.wait_for_timeout(1200)
                shot("settings_notifications")

        browser.close()

    # Summary
    pngs = sorted(OUT_DIR.glob("*.png"))
    print(f"\n  Done — {len(pngs)} screenshots saved to {OUT_DIR}")
    for p in pngs:
        print(f"    {p.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
