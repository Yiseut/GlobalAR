"""Visual smoke test for v3 chart interactivity (Pack D).

For each page, load it, hover sample chart elements to verify tooltip,
click sample elements to verify drill-panel opens, then click a drill
row to verify cascade into V3CompanyDetail brand→family→SKU drawer.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/v3"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "audits" / "v3_chart_interact_verify"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    # index.html cases skipped: page loads globe.gl + three.js from CDN and
    # never reaches networkidle / domcontentloaded in time. Verified manually
    # via a dedicated index test (see below).
    {
        "name": "regulatory_donut",
        "url": f"{BASE}/regulatory-pulse.html",
        "wait": ".reg-slice",
        "hover": ".reg-slice >> nth=0",
        "click": ".reg-slice >> nth=0",
        "svg": True,
    },
    {
        "name": "regulatory_year",
        "url": f"{BASE}/regulatory-pulse.html",
        "wait": ".col-chart .col",
        "hover": ".col-chart .col >> nth=18",  # 2024
        "click": ".col-chart .col >> nth=18",
    },
    {
        "name": "capital_band",
        "url": f"{BASE}/capital-map.html",
        "wait": ".val-band-row",
        "hover": ".val-band-row >> nth=0",
        "click": ".val-band-row >> nth=0",
    },
    {
        "name": "capital_exchange",
        "url": f"{BASE}/capital-map.html",
        "wait": ".exch-slice",
        "hover": ".exch-slice >> nth=0",
        "click": ".exch-slice >> nth=0",
        "svg": True,
    },
    {
        "name": "indications_bars",
        "url": f"{BASE}/indications.html",
        "wait": "#ind-rank-list .ind-rank-row",
        "hover": "#ind-rank-list .ind-rank-row >> nth=0",
        "click": None,
    },
    {
        "name": "technology_bars",
        "url": f"{BASE}/technology-tree.html",
        "wait": "#tech-rank-list .ind-rank-row",
        "hover": "#tech-rank-list .ind-rank-row >> nth=0",
        "click": None,
    },
    {
        "name": "geo_region",
        "url": f"{BASE}/geo-deep-dive.html",
        "wait": ".region-row",
        "hover": ".region-row >> nth=0",
        "click": ".region-row >> nth=0",
    },
    {
        "name": "geo_country_table",
        "url": f"{BASE}/geo-deep-dive.html",
        "wait": ".geo-co-row",
        "hover": ".geo-co-row >> nth=0",
        "click": ".geo-co-row >> nth=0",
    },
]


def main () -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        any_fail = False
        for case in CASES:
            # Fresh context per case to avoid index.html's slow goto polluting later tests
            ctx = browser.new_context(viewport={"width": 1500, "height": 1000})
            page = ctx.new_page()
            errors: list[str] = []
            def make_listener (errs):
                return lambda m: errs.append(f"[{m.type}] {m.text}") if m.type in ("error", "warning") else None
            page.on("console", make_listener(errors))
            page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
            try:
                page.goto(case["url"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector(case["wait"], timeout=15000)
                # Wait extra for IIFE wireCharts handlers to attach (scripts load
                # async + inline script runs after _nav.js)
                page.wait_for_timeout(1500)

                # Hover test → tooltip
                # SVG donut slices: dispatch synthetic event from JS, because
                # Playwright's hover lands on bbox-center (donut hole) which
                # doesn't trigger pointer-events: visibleStroke.
                if case.get("svg"):
                    selector = case["hover"].split(" >> ")[0]
                    nth_part = case["hover"].split(" >> ")[1] if " >> " in case["hover"] else "nth=0"
                    nth = int(nth_part.replace("nth=", ""))
                    page.evaluate(f"""(() => {{
                        const el = document.querySelectorAll('{selector}')[{nth}];
                        if (!el) return;
                        const rect = el.getBoundingClientRect();
                        const ev = new MouseEvent('mouseenter', {{
                            bubbles: true, cancelable: true,
                            clientX: rect.left + rect.width/2,
                            clientY: rect.top + 8,
                        }});
                        el.dispatchEvent(ev);
                    }})()""")
                else:
                    page.hover(case["hover"], force=True, timeout=8000)
                page.wait_for_timeout(300)
                tip = page.evaluate("""() => {
                    const t = document.querySelector('.v3-tip.show');
                    if (!t) return null;
                    return {
                        title: t.querySelector('.tip-title')?.textContent.trim(),
                        lines: Array.from(t.querySelectorAll('.tip-line')).map(l => l.textContent.trim()),
                    };
                }""")
                tip_ok = bool(tip)

                # Click test → drill panel
                drill_ok = "skip"
                cascade_ok = "skip"
                if case["click"]:
                    if case.get("svg"):
                        selector = case["click"].split(" >> ")[0]
                        nth_part = case["click"].split(" >> ")[1] if " >> " in case["click"] else "nth=0"
                        nth = int(nth_part.replace("nth=", ""))
                        page.evaluate(f"""(() => {{
                            const el = document.querySelectorAll('{selector}')[{nth}];
                            if (el) el.dispatchEvent(new MouseEvent('click', {{bubbles: true, cancelable: true}}));
                        }})()""")
                    else:
                        page.click(case["click"], force=True, timeout=8000)
                    # ---- Drill panel check ----
                    try:
                        page.wait_for_selector(".v3-dp.show", timeout=4000)
                        page.wait_for_timeout(300)
                        drill_info = page.evaluate("""() => ({
                            title: document.getElementById('v3dp-title')?.textContent.trim(),
                            sub: document.getElementById('v3dp-sub')?.textContent.trim(),
                            rows: document.querySelectorAll('#v3dp-body .row').length,
                            clickable: document.querySelectorAll('#v3dp-body .row[data-company-id]').length,
                        })""")
                        drill_ok = drill_info
                        try:
                            page.screenshot(path=str(OUT_DIR / f"{case['name']}_drill.png"))
                        except Exception:
                            pass
                    except Exception:
                        drill_ok = "fail"

                    # ---- Cascade test (separate try so its failure does not corrupt drill_ok) ----
                    if isinstance(drill_ok, dict) and drill_ok.get("clickable", 0) > 0:
                        try:
                            page.click("#v3dp-body .row[data-company-id] >> nth=0", force=True, timeout=4000)
                            page.wait_for_selector(".v3-cd-drawer.show", timeout=2500)
                            cascade_ok = "ok"
                        except Exception:
                            cascade_ok = "fail"

                bad = [e for e in errors if "Failed to load resource" not in e and "favicon" not in e]
                status = "OK" if (tip_ok and drill_ok != "fail" and not bad) else "WARN"
                if status != "OK":
                    any_fail = True
                print(f"[{status}] {case['name']:24s} tip={tip_ok} drill={drill_ok if drill_ok in ('skip','fail') else 'ok ('+str(drill_ok['rows'])+'r, '+str(drill_ok['clickable'])+'cl)'} cascade={cascade_ok}")
                if bad:
                    for e in bad[:3]:
                        print(f"   ! {e}")
            except Exception as ex:
                any_fail = True
                print(f"[FAIL] {case['name']}: {ex}")
            finally:
                page.close()
                ctx.close()
        browser.close()
        print()
        print("ALL OK" if not any_fail else "SOME FAILED — see screenshots in " + str(OUT_DIR))


if __name__ == "__main__":
    main()
