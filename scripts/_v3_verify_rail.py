"""Verify left rail after evidence/MDR entries were removed."""
from playwright.sync_api import sync_playwright
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
OUT.mkdir(exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1600, "height": 1000}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector("#rail .rail-section", timeout=8000)
    page.wait_for_timeout(800)

    sections = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('#rail .rail-section')).map(sec => ({
            title: sec.querySelector('.rail-section-title')?.textContent || '',
            items: Array.from(sec.querySelectorAll('a')).map(a => ({
                zh: a.querySelector('span')?.textContent?.trim() || a.textContent.trim(),
                count: a.querySelector('small')?.textContent || '',
                href: a.getAttribute('href'),
            })),
        }));
    }""")
    print("=== Rail sections ===")
    for s in sections:
        print(f"[{s['title']}]")
        for it in s["items"]:
            print(f"  · {it['zh']:40}  count={it['count']:8}  href={it['href']}")

    has_evidence = any("证据库" in it["zh"] for s in sections for it in s["items"])
    has_mdr = any("MDR" in it["zh"] for s in sections for it in s["items"])
    print()
    print(f"证据库 入口存在: {'✗ STILL PRESENT' if has_evidence else '✓ removed'}")
    print(f"MDR/CE 入口存在: {'✗ STILL PRESENT' if has_mdr else '✓ removed'}")

    rail_box = page.evaluate("(() => { const r = document.getElementById('rail').getBoundingClientRect(); return {x:r.x,y:r.y,w:r.width,h:r.height}; })()")
    page.screenshot(path=str(OUT / "rail_after_evidence_removed.png"),
                    clip={"x": rail_box["x"], "y": rail_box["y"], "width": rail_box["w"] + 4, "height": min(900, rail_box["h"])})
    print(f"\n→ {OUT / 'rail_after_evidence_removed.png'}")
    browser.close()
