"""Visual smoke test for v3 cross-analysis page.

Loads the page, screenshots each lens, clicks sample cells, verifies the
drill-down side panel opens, captures console errors.
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/v3"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "audits" / "v3_cross_analysis_verify"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("console", lambda m: errors.append(f"[{m.type}] {m.text}")
                if m.type in ("error", "warning") else None)
        page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))

        page.goto(f"{BASE}/cross-analysis.html", wait_until="domcontentloaded", timeout=15000)
        # Don't wait for networkidle — Google Fonts streams keep network busy

        # Wait for grids to render
        page.wait_for_selector("#lens1-grid .xa-cell.has-data", timeout=10000)
        page.wait_for_selector("#lens2-grid .ry-cell.has-data", timeout=10000)
        page.wait_for_selector("#lens3-list .ir-cell[data-bucket]", timeout=10000)

        # Initial full-page screenshot
        full_shot = OUT_DIR / "full_page.png"
        page.screenshot(path=str(full_shot), full_page=True)
        print(f"[OK] full page screenshot · {full_shot.relative_to(ROOT)}")

        # ---- Section 1 closeup ----
        page.evaluate("document.querySelectorAll('#lens1-grid')[0].scrollIntoView({block:'start'})")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT_DIR / "lens1.png"), full_page=False)

        # Click a Lens 1 cell (should be South Korea × Injectables, the densest)
        cells = page.evaluate("""() => {
            const cells = Array.from(document.querySelectorAll('#lens1-grid .xa-cell.has-data'));
            return cells.slice(0, 3).map(c => ({
                country: c.dataset.country,
                track: c.dataset.track,
                v: c.querySelector('.v')?.textContent
            }));
        }""")
        print(f"  Lens 1 sample cells: {cells}")
        page.click("#lens1-grid .xa-cell.has-data >> nth=0")
        page.wait_for_selector(".xa-drill.show", timeout=4000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT_DIR / "lens1_drill.png"), full_page=False)
        drill_info = page.evaluate("""() => ({
            title: document.getElementById('drill-title').textContent.trim(),
            sub: document.getElementById('drill-sub').textContent.trim(),
            rows: document.querySelectorAll('#drill-body .row').length
        })""")
        print(f"  Lens 1 drill: {drill_info}")
        page.click(".xa-drill .close-btn")
        page.wait_for_timeout(300)

        # ---- Section 2 ----
        page.evaluate("document.querySelector('#lens2-grid').scrollIntoView({block:'start'})")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT_DIR / "lens2.png"), full_page=False)

        page.click("#lens2-grid .ry-cell.has-data >> nth=0")
        page.wait_for_selector(".xa-drill.show", timeout=4000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT_DIR / "lens2_drill.png"), full_page=False)
        drill_info2 = page.evaluate("""() => ({
            title: document.getElementById('drill-title').textContent.trim(),
            sub: document.getElementById('drill-sub').textContent.trim(),
            rows: document.querySelectorAll('#drill-body .row').length
        })""")
        print(f"  Lens 2 drill: {drill_info2}")
        page.click(".xa-drill .close-btn")
        page.wait_for_timeout(300)

        # ---- Section 3 ----
        page.evaluate("document.querySelector('#lens3-list').scrollIntoView({block:'start'})")
        page.wait_for_timeout(200)
        page.screenshot(path=str(OUT_DIR / "lens3.png"), full_page=False)

        page.click("#lens3-list .ir-cell[data-bucket] >> nth=0")
        page.wait_for_selector(".xa-drill.show", timeout=4000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(OUT_DIR / "lens3_drill.png"), full_page=False)
        drill_info3 = page.evaluate("""() => ({
            title: document.getElementById('drill-title').textContent.trim(),
            sub: document.getElementById('drill-sub').textContent.trim(),
            rows: document.querySelectorAll('#drill-body .row').length
        })""")
        print(f"  Lens 3 drill: {drill_info3}")

        # ---- Test that drill row click opens shared company-detail drawer ----
        row_count = page.evaluate("document.querySelectorAll('#drill-body .row').length")
        if row_count > 0:
            page.click("#drill-body .row:first-child")
            try:
                page.wait_for_selector(".v3-cd-drawer.show", timeout=2000)
                page.wait_for_timeout(400)
                page.screenshot(path=str(OUT_DIR / "lens3_drill_to_company.png"), full_page=False)
                detail_info = page.evaluate("""() => ({
                    title: document.querySelector('.v3-cd-title')?.textContent.trim(),
                    brands: document.querySelectorAll('.v3-cd-brand').length,
                })""")
                print(f"  → company drawer cascade: {detail_info}")
            except Exception:
                print(f"  ! company drawer did not open from drill row")

        # Filter out harmless errors
        bad = [e for e in errors if "Failed to load resource" not in e and "favicon" not in e]
        print()
        if bad:
            print("CONSOLE ERRORS:")
            for e in bad[:10]:
                print(f"  ! {e}")
        else:
            print("CONSOLE: clean")

        browser.close()


if __name__ == "__main__":
    main()
