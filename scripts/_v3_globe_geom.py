"""Measure globe-section bounding box vs viewport, main.content, and rail."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    for vw in (1440, 1600):
        ctx = browser.new_context(viewport={"width": vw, "height": 900}, locale="zh-CN")
        page = ctx.new_page()
        page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
        page.wait_for_selector(".globe-section", timeout=8000)
        page.wait_for_timeout(1200)
        geom = page.evaluate("""() => {
            const get = sel => {
                const e = document.querySelector(sel);
                if (!e) return null;
                const r = e.getBoundingClientRect();
                return { left: r.left, right: r.right, width: r.width };
            };
            return {
                viewport: window.innerWidth,
                html: document.documentElement.getBoundingClientRect().right,
                body: get('body'),
                shell: get('.shell'),
                rail: get('.rail'),
                main: get('main.content'),
                pageHero: get('.page-hero'),
                globeSection: get('.globe-section'),
                kpiGrid: get('.kpi-grid'),
                flatMap: get('.flat-map-section'),
            };
        }""")
        print(f"\n=== viewport {vw}px ===")
        for k, v in geom.items():
            print(f"  {k:15} {v}")
        ctx.close()
    browser.close()
