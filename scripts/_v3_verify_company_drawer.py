"""Visual smoke test for v3 company-detail drawer integration.

For each page that lists companies, loads it in a headless browser, simulates
the click that opens the drawer, and captures: (a) console errors, (b) drawer
DOM presence, (c) screenshot of the drawer.

Usage: python scripts/_v3_verify_company_drawer.py
"""
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8765/v3"
ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "audits" / "v3_drawer_verify"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# (page, action description, action js, expected drawer visible after action)
CASES = [
    {
        "name": "companies",
        "url": f"{BASE}/companies.html",
        "trigger": "await page.wait_for_selector('#co-tbody tr.co-row', timeout=10000); await page.click('#co-tbody tr.co-row:first-child');",
    },
    {
        "name": "regulatory-pulse",
        "url": f"{BASE}/regulatory-pulse.html",
        "trigger": "await page.wait_for_selector('.table-card tbody tr.co-row', timeout=10000); await page.click('.table-card tbody tr.co-row:first-child');",
    },
    {
        "name": "capital-map",
        "url": f"{BASE}/capital-map.html",
        "trigger": "await page.wait_for_selector('.table-card tbody tr.co-row', timeout=10000); await page.click('.table-card tbody tr.co-row:first-child');",
    },
    {
        "name": "topic-injectables",
        "url": f"{BASE}/topic.html?segment=injectables",
        "trigger": "await page.wait_for_selector('#topco-tbody tr.co-row', timeout=10000); await page.click('#topco-tbody tr.co-row:first-child');",
    },
]


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 900})

        all_ok = True
        for case in CASES:
            page = ctx.new_page()
            errors: list[str] = []
            page.on("console", lambda msg: errors.append(f"[{msg.type}] {msg.text}") if msg.type in ("error", "warning") else None)
            page.on("pageerror", lambda e: errors.append(f"[pageerror] {e}"))
            try:
                page.goto(case["url"], wait_until="domcontentloaded", timeout=15000)
                page.wait_for_load_state("networkidle", timeout=15000)

                # Pre-click screenshot
                shot_before = OUT_DIR / f"{case['name']}_before.png"
                page.screenshot(path=str(shot_before), full_page=False)

                # Trigger drawer
                trigger_js = case["trigger"]
                # Execute trigger as a sync action sequence
                # We rebuild the trigger inline (it's all await page.* calls)
                # so we do it via page.evaluate of plain JS where possible.
                # Actually simpler: parse manually.
                if "tr.co-row" in trigger_js:
                    # Strategy: wait for first .co-row in DOM, then click
                    pass

                # Manually replicate trigger:
                if case["name"] == "companies":
                    page.wait_for_selector("#co-tbody tr.co-row", timeout=10000)
                    page.click("#co-tbody tr.co-row:first-child")
                elif case["name"] == "regulatory-pulse":
                    page.wait_for_selector(".table-card tbody tr.co-row", timeout=10000)
                    page.click(".table-card tbody tr.co-row:first-child")
                elif case["name"] == "capital-map":
                    page.wait_for_selector(".table-card tbody tr.co-row", timeout=10000)
                    page.click(".table-card tbody tr.co-row:first-child")
                elif case["name"] == "topic-injectables":
                    page.wait_for_selector("#topco-tbody tr.co-row", timeout=10000)
                    page.click("#topco-tbody tr.co-row:first-child")

                page.wait_for_selector(".v3-cd-drawer.show", timeout=5000)
                page.wait_for_timeout(400)  # allow css transition + content render

                drawer_info = page.evaluate("""() => {
                    const d = document.querySelector('.v3-cd-drawer');
                    if (!d) return {ok: false, err: 'no drawer'};
                    const title = d.querySelector('.v3-cd-title')?.textContent.trim();
                    const brandCount = d.querySelectorAll('.v3-cd-brand').length;
                    const familyCount = d.querySelectorAll('.v3-cd-family').length;
                    const skuCount = d.querySelectorAll('.v3-cd-sku').length;
                    return {ok: true, title, brandCount, familyCount, skuCount};
                }""")

                shot_after = OUT_DIR / f"{case['name']}_after.png"
                page.screenshot(path=str(shot_after), full_page=False)

                # Print row separator
                bad_errors = [e for e in errors if "Failed to load resource" not in e
                              and "favicon" not in e]
                status = "OK" if (drawer_info["ok"] and not bad_errors) else "FAIL"
                if status == "FAIL":
                    all_ok = False
                print(f"[{status}] {case['name']}")
                print(f"   title={drawer_info.get('title')!r}, "
                      f"brands={drawer_info.get('brandCount')}, "
                      f"families={drawer_info.get('familyCount')}, "
                      f"SKUs={drawer_info.get('skuCount')}")
                if bad_errors:
                    for e in bad_errors[:5]:
                        print(f"   ! {e}")
                print(f"   shot: {shot_after.relative_to(ROOT)}")
            except Exception as ex:
                all_ok = False
                print(f"[FAIL] {case['name']}: {ex}")
                try:
                    page.screenshot(path=str(OUT_DIR / f"{case['name']}_error.png"))
                except Exception:
                    pass
            finally:
                page.close()

        browser.close()
        print()
        print("ALL OK" if all_ok else "SOME FAILED — see screenshots in " + str(OUT_DIR))


if __name__ == "__main__":
    main()
