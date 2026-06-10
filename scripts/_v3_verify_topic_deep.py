"""Visual smoke test for v3 topic.html deep-dive sections across all 8 segments.

For each segment: load page, screenshot full page, verify the 6 new sections
render (concentration grid, value chain bars, lifecycle scatter, indication
heatmap, recent entrants lists, country × L2 matrix), click sample cells,
confirm topic drill-down + cascade to company drawer, capture console errors.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/v3"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "audits" / "v3_topic_deep_verify"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SEGMENTS = ["ebd", "injectables", "skincare", "regenerative",
            "consumables", "implants", "diagnostics", "surgical", "pharma"]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1500, "height": 1000})
        all_ok = True
        for seg in SEGMENTS:
            page = ctx.new_page()
            errors: list[str] = []
            page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}")
                    if m.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
            try:
                page.goto(f"{BASE}/topic.html?segment={seg}",
                          wait_until="domcontentloaded", timeout=15000)
                # Don't networkidle — Google Fonts streams
                page.wait_for_selector("#conc-grid .conc-card", timeout=8000)
                page.wait_for_timeout(400)  # let dynamic JS finish

                info = page.evaluate("""() => ({
                    conc: document.querySelectorAll('#conc-grid .conc-card').length,
                    top10: document.querySelectorAll('#conc-top10 .row').length,
                    vc: document.querySelectorAll('#vc-bars .vc-bar').length,
                    lc_dots: document.querySelectorAll('#lc-scatter .lc-dot').length,
                    ih_cells: document.querySelectorAll('#ind-heatmap .ir-mini-cell').length,
                    ih_has: document.querySelectorAll('#ind-heatmap .ir-mini-cell.has').length,
                    new_entrants: document.querySelectorAll('#new-entrants-list .e-row').length,
                    recent_active: document.querySelectorAll('#recent-active-list .e-row').length,
                    cl_cells: document.querySelectorAll('#cl-matrix-wrap .cl-cell.has-data').length,
                })""")
                # Trigger IntersectionObserver fade-in for all blocks by force-
                # applying .in-view to them (otherwise full-page screenshots are
                # mostly blank).
                page.evaluate("""() => {
                    document.querySelectorAll('.block, .page-hero, .kpi-cell, .editorial-block, .l1-card')
                        .forEach(el => el.classList.add('in-view'));
                }""")
                page.wait_for_timeout(200)
                shot = OUT_DIR / f"{seg}.png"
                page.screenshot(path=str(shot), full_page=True)

                # Also capture each new section at viewport scale for visual review
                for sect_id, label in [
                    ("conc-grid", "1_concentration"),
                    ("vc-bars", "2_value_chain"),
                    ("lc-scatter", "3_lifecycle"),
                    ("ind-heatmap", "4_indication"),
                    ("new-entrants-list", "5_entrants"),
                    ("cl-matrix-wrap", "6_country_l2"),
                ]:
                    try:
                        el = page.locator(f"#{sect_id}")
                        # scroll the section's parent .block into view
                        page.evaluate(f"document.getElementById('{sect_id}').closest('.block').scrollIntoView({{block:'start'}})")
                        page.wait_for_timeout(150)
                        block = page.evaluate_handle(f"document.getElementById('{sect_id}').closest('.block')")
                        block.as_element().screenshot(path=str(OUT_DIR / f"{seg}_{label}.png"))
                    except Exception as e:
                        pass

                # If any concentration top10 row exists, click it to verify drill into shared drawer
                drawer_ok = "skip"
                if info["top10"] > 0:
                    page.click("#conc-top10 .row >> nth=0")
                    try:
                        page.wait_for_selector(".v3-cd-drawer.show", timeout=3000)
                        drawer_ok = "ok"
                        page.click(".v3-cd-drawer .v3-cd-close")
                        page.wait_for_timeout(300)
                    except Exception:
                        drawer_ok = "fail"

                # If lifecycle has dots, click one → topic drill
                lc_drill = "skip"
                if info["lc_dots"] > 0:
                    page.click("#lc-scatter .lc-dot >> nth=0")
                    try:
                        page.wait_for_selector("#td-drill.show", timeout=2500)
                        lc_drill = "ok"
                        page.evaluate("document.querySelector('#td-drill .close-btn').click()")
                        page.wait_for_timeout(300)
                    except Exception:
                        lc_drill = "fail"

                bad = [e for e in errors if "Failed to load resource" not in e
                       and "favicon" not in e]
                status = "OK" if not bad else "WARN"
                print(f"[{status}] {seg:14s} conc={info['conc']} top10={info['top10']} vc={info['vc']} "
                      f"lc_dots={info['lc_dots']} ih={info['ih_has']}/{info['ih_cells']} "
                      f"new={info['new_entrants']} active={info['recent_active']} cl={info['cl_cells']} "
                      f"· drawer={drawer_ok} · lc_drill={lc_drill}")
                if bad:
                    for e in bad[:3]:
                        print(f"   ! {e}")
                    all_ok = False
            except Exception as ex:
                all_ok = False
                print(f"[FAIL] {seg}: {ex}")
                try:
                    page.screenshot(path=str(OUT_DIR / f"{seg}_error.png"))
                except Exception:
                    pass
            finally:
                page.close()
        browser.close()
        print()
        print("ALL OK" if all_ok else "SOME WARNINGS — check screenshots in " + str(OUT_DIR))


if __name__ == "__main__":
    main()
