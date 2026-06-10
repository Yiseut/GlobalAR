"""Screenshot the v3 left rail after evidence/MDR removal."""
from playwright.sync_api import sync_playwright
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector("#rail .rail-section", timeout=8000)
    # Wait a moment for the rail rendering to settle, but skip globe webgl + font wait
    page.wait_for_timeout(2500)
    # Disable font wait by forcing screenshot with shorter timeout via specific clip
    rail_box = page.evaluate("(() => { const r = document.getElementById('rail').getBoundingClientRect(); return {x:r.x, y:r.y, w:r.width, h:r.height}; })()")
    print(f"rail bbox: {rail_box}")
    page.screenshot(
        path=str(OUT / "rail_after_evidence_removed.png"),
        clip={"x": rail_box["x"], "y": rail_box["y"], "width": rail_box["w"] + 4, "height": min(900, rail_box["h"])},
        timeout=60000,
        animations="disabled",
    )
    print(f"OK → {OUT / 'rail_after_evidence_removed.png'}")
    browser.close()
