"""Screenshot technology-tree.html KPI grid after lede-text fix."""
from playwright.sync_api import sync_playwright
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/technology-tree.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector(".kpi-grid", timeout=8000)
    page.wait_for_timeout(2500)
    # check the actual text bound to #kpi-top-tech
    top_tech = page.evaluate("document.getElementById('kpi-top-tech')?.textContent")
    print(f"#kpi-top-tech bound text: '{top_tech}'")
    page.eval_on_selector(".kpi-grid", "el => el.scrollIntoView({block:'start'})")
    page.wait_for_timeout(800)
    box = page.evaluate("() => { const r = document.querySelector('.kpi-grid').getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; }")
    clip = {"x": max(0, box["x"]-8), "y": max(0, box["y"]-8), "width": min(1440, box["w"]+16), "height": min(900, box["h"]+16)}
    page.screenshot(path=str(OUT / "tech_tree_kpi_fixed.png"), clip=clip, animations="disabled", timeout=60000)
    print(f"→ {OUT / 'tech_tree_kpi_fixed.png'}")
    browser.close()
