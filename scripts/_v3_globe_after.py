"""Screenshot hero+globe area after the bleed fix."""
from playwright.sync_api import sync_playwright
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector(".globe-section", timeout=8000)
    page.wait_for_timeout(2500)
    # Full viewport screenshot of hero + globe area (top of page)
    page.screenshot(path=str(OUT / "globe_bleed_fixed.png"),
                    clip={"x": 0, "y": 0, "width": 1440, "height": 900},
                    animations="disabled", timeout=60000)
    print(f"→ {OUT / 'globe_bleed_fixed.png'}")
    browser.close()
