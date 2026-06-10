"""Diagnose why globe-section margin -56 doesn't actually bleed."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector(".globe-section", timeout=8000)
    page.wait_for_timeout(1200)
    info = page.evaluate("""() => {
        const el = document.querySelector('.globe-section');
        const main = document.querySelector('main.content');
        const cs = getComputedStyle(el);
        const csMain = getComputedStyle(main);
        return {
            globe: {
                marginLeft:  cs.marginLeft,
                marginRight: cs.marginRight,
                paddingLeft: cs.paddingLeft,
                paddingRight: cs.paddingRight,
                width: cs.width,
                maxWidth: cs.maxWidth,
                boxSizing: cs.boxSizing,
                display: cs.display,
                overflow: cs.overflow,
                clientW: el.clientWidth,
                offsetW: el.offsetWidth,
            },
            main: {
                paddingLeft: csMain.paddingLeft,
                paddingRight: csMain.paddingRight,
                maxWidth: csMain.maxWidth,
                overflow: csMain.overflow,
                width: csMain.width,
                clientW: main.clientWidth,
            },
        };
    }""")
    import json
    print(json.dumps(info, indent=2))
    browser.close()
