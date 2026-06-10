"""Focused screenshot of v3 flat-map and globe-on-top hero."""
from playwright.sync_api import sync_playwright
from pathlib import Path

BASE = "http://127.0.0.1:8790"
OUT = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
OUT.mkdir(exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto(f"{BASE}/v3/index.html", wait_until="networkidle", timeout=30000)
        page.wait_for_function(
            "document.querySelectorAll('.flat-map-stage path.flat-city-dot').length > 50",
            timeout=15000,
        )

        # Hero (page-hero + globe-section)
        page.evaluate("document.querySelector('.page-hero').scrollIntoView({behavior:'instant', block:'start'})")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "hero_globe_top.png"))
        print(f"1 → {OUT / 'hero_globe_top.png'}")

        # Flat-map section
        page.evaluate("document.querySelector('.flat-map-section').scrollIntoView({behavior:'instant', block:'start'})")
        page.wait_for_timeout(1500)
        # The flat-map-section itself
        box = page.evaluate("""() => {
            const el = document.querySelector('.flat-map-section');
            const r = el.getBoundingClientRect();
            return {x: r.x, y: r.y, w: r.width, h: r.height};
        }""")
        print(f"   flat-map bbox: {box}")
        # Clamp to viewport
        clip = {
            "x": max(0, box["x"]),
            "y": max(0, box["y"]),
            "width": min(1600 - max(0, box["x"]), box["w"]),
            "height": min(900 - max(0, box["y"]), box["h"]),
        }
        page.screenshot(path=str(OUT / "flat_map_focus.png"), clip=clip)
        print(f"2 → {OUT / 'flat_map_focus.png'} clip={clip}")

        # Toggle to by-companies + open one tooltip
        page.click("[data-flat-metric='companies']")
        page.wait_for_timeout(800)
        page.screenshot(path=str(OUT / "flat_map_by_companies.png"), clip=clip)
        print(f"3 → {OUT / 'flat_map_by_companies.png'}")

        browser.close()


if __name__ == "__main__":
    main()
