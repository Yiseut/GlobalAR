"""Take 4 viewport-sized screenshots of v3 index — page-hero, KPI grid,
editorial row, flat-map area — so the user can point at the offending card."""
from playwright.sync_api import sync_playwright
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector("#rail .rail-section", timeout=8000)
    page.wait_for_timeout(2500)

    # Disable font wait by passing timeout AND using clip
    targets = [
        (".page-hero",     "shot_1_page_hero",    260),
        (".kpi-grid",      "shot_2_kpi_grid",     380),
        (".editorial-row", "shot_3_editorial",    340),
        (".flat-map-section", "shot_4_flat_map",  900),
    ]
    for sel, name, max_h in targets:
        try:
            page.eval_on_selector(sel, "el => el.scrollIntoView({block:'start', behavior:'instant'})")
            page.wait_for_timeout(800)
            box = page.evaluate(f"() => {{ const r = document.querySelector('{sel}').getBoundingClientRect(); return {{x:r.x, y:r.y, w:r.width, h:r.height}}; }}")
            clip = {
                "x": max(0, box["x"] - 8),
                "y": max(0, box["y"] - 8),
                "width": min(1440, box["w"] + 16),
                "height": min(max_h, max(60, box["h"] + 16)),
            }
            page.screenshot(path=str(OUT / f"{name}.png"), clip=clip, animations="disabled", timeout=60000)
            print(f"  → {name}.png  bbox={box}  clip={clip}")
        except Exception as e:
            print(f"  ! {sel}: {e}")
    browser.close()
