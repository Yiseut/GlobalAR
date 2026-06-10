"""Hunt English-text overflow on v3 index.html cards."""
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

    # Check overflow on every English label in KPI cells, editorial blocks, and section-heads
    overflow = page.evaluate("""() => {
        const out = [];
        const selectors = [
            { sel: '.kpi-cell .label .en',          group: 'KPI label EN' },
            { sel: '.kpi-cell .delta',              group: 'KPI delta' },
            { sel: '.section-head .en',             group: 'section-head EN' },
            { sel: '.editorial-block .stamp',       group: 'editorial stamp' },
            { sel: '.editorial-block .num-pair .unit', group: 'editorial unit' },
            { sel: '.editorial-block .cta',         group: 'editorial CTA' },
            { sel: '.h1-en',                        group: 'h1 EN' },
            { sel: '.lede',                         group: 'page-hero lede' },
            { sel: '.globe-stat-strip .lab',        group: 'globe strip lab' },
            { sel: '.flat-map-stat-strip .k',       group: 'flat strip k' },
        ];
        selectors.forEach(({ sel, group }) => {
            document.querySelectorAll(sel).forEach((el, i) => {
                const cs = getComputedStyle(el);
                const wOverflow = el.scrollWidth > el.clientWidth + 1;
                const hOverflow = el.scrollHeight > el.clientHeight + 1;
                if (wOverflow || hOverflow) {
                    out.push({
                        group,
                        sel,
                        idx: i,
                        text: (el.textContent || '').trim().slice(0, 60),
                        scrollW: el.scrollWidth, clientW: el.clientWidth,
                        scrollH: el.scrollHeight, clientH: el.clientHeight,
                        fontSize: cs.fontSize,
                        fontFamily: cs.fontFamily.split(',')[0],
                        whiteSpace: cs.whiteSpace,
                        wordBreak: cs.wordBreak,
                    });
                }
            });
        });
        return out;
    }""")
    print("=== Overflowing English text on v3/index.html ===")
    if not overflow:
        print("  (none detected — all texts fit)")
    else:
        for o in overflow:
            print(f"  [{o['group']:24}] #{o['idx']:2}  '{o['text']}'")
            print(f"      scrollW={o['scrollW']} clientW={o['clientW']}  scrollH={o['scrollH']} clientH={o['clientH']}  fs={o['fontSize']} font={o['fontFamily']}")

    # Also screenshot the KPI grid + editorial section as a reference
    for name, sel in [("kpi_grid", ".kpi-grid"), ("editorial_row", ".editorial-row"), ("page_hero", ".page-hero")]:
        el = page.locator(sel)
        if el.count() > 0:
            try:
                el.first.scroll_into_view_if_needed(timeout=4000)
                page.wait_for_timeout(500)
                box = el.first.bounding_box()
                if box:
                    page.screenshot(
                        path=str(OUT / f"overflow_{name}.png"),
                        clip={"x": max(0, box["x"] - 8), "y": max(0, box["y"] - 8), "width": min(1440, box["width"] + 16), "height": min(900, box["height"] + 16)},
                        animations="disabled",
                        timeout=30000,
                    )
                    print(f"  → screenshot overflow_{name}.png")
            except Exception as e:
                print(f"  ! {name}: {e}")

    browser.close()
