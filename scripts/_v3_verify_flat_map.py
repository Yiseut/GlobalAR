"""v3 flat-map + globe-on-top verification.

Checks:
1. index.html 顺序：page-hero → globe-section → KPI → 编辑视角 → flat-map-section → ...
2. Leaflet flat-map 容器加载到 tile 并有 circleMarker（>= 10）
3. flat-map-section stat strip 不为 "—"（有数字）
4. 其它共享 styles.css 的页面没回归：regulatory-pulse / companies / deep-dive 顶部 h1 可见
"""
import sys
import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright not installed. pip install playwright && playwright install chromium")
    sys.exit(1)

BASE = "http://127.0.0.1:8790"
SCREENSHOT_DIR = Path(__file__).resolve().parent.parent / "_v3_verify_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1440, "height": 2400}, locale="zh-CN")
        page = ctx.new_page()

        # ====== 1. index.html — overview ======
        print("\n[1/4] /v3/index.html — 总览页 (globe 上移 + flat-map 新增)")
        page.goto(f"{BASE}/v3/index.html", wait_until="networkidle", timeout=30000)
        # Wait for flat-map markers to render
        try:
            page.wait_for_selector(".flat-map-stage .leaflet-marker-pane", timeout=15000)
            page.wait_for_function(
                "document.querySelectorAll('.flat-map-stage path.flat-city-dot').length > 5",
                timeout=15000,
            )
        except Exception as e:
            print(f"  WARN: flat-map markers didn't appear in time ({e})")

        # Check section order — first .block in main should now be globe-section
        order = page.evaluate("""() => {
            const blocks = Array.from(document.querySelectorAll('main.content > section.block, main.content > .page-hero'));
            return blocks.map(b => ({
                cls: b.className,
                heading: (b.querySelector('h1, h2') || {}).textContent || ''
            }));
        }""")
        print("  Section order:")
        for i, b in enumerate(order):
            print(f"    {i+1}. {b['heading'].strip()[:30]:30}  ·  {b['cls']}")

        # Verify globe-section is now first .block after page-hero
        blocks_after_hero = [b for b in order if "page-hero" not in b["cls"]]
        if blocks_after_hero and "globe-section" in blocks_after_hero[0]["cls"]:
            print("  ✓ globe-section 已移到首 .block (page-hero 之后)")
        else:
            first_block = blocks_after_hero[0]["cls"] if blocks_after_hero else "(none)"
            print(f"  ✗ globe-section 不是首 .block (是 {first_block})")

        # Verify flat-map-section exists
        has_flat = any("flat-map-section" in b["cls"] for b in order)
        flat_index = next((i for i, b in enumerate(order) if "flat-map-section" in b["cls"]), -1)
        print(f"  {'✓' if has_flat else '✗'} flat-map-section 存在 (index #{flat_index + 1})")

        # Count circleMarkers + check stat strip
        markers = page.evaluate("document.querySelectorAll('.flat-map-stage path.flat-city-dot').length")
        companies_stat = page.locator("#flatMapCompanies").inner_text()
        cities_stat = page.locator("#flatMapCities").inner_text()
        countries_stat = page.locator("#flatMapCountries").inner_text()
        products_stat = page.locator("#flatMapProducts").inner_text()
        print(f"  Markers rendered: {markers}")
        print(f"  KPI strip: Companies={companies_stat} · Cities={cities_stat} · Countries={countries_stat} · Products={products_stat}")
        if markers >= 50 and companies_stat != "—":
            print("  ✓ flat-map 圆点和 KPI 渲染正常")
        else:
            print("  ✗ flat-map 渲染未达预期")

        # Tile layer check
        tiles = page.evaluate("document.querySelectorAll('.flat-map-stage img.leaflet-tile').length")
        print(f"  CARTO tiles loaded: {tiles}")

        page.screenshot(path=str(SCREENSHOT_DIR / "index_overview.png"), full_page=True)
        print(f"  → screenshot: {SCREENSHOT_DIR / 'index_overview.png'}")

        # ====== 2-4. Sibling pages — make sure shared styles.css didn't break them ======
        for name in ["regulatory-pulse", "companies", "deep-dive"]:
            print(f"\n[{2 if name == 'regulatory-pulse' else 3 if name == 'companies' else 4}/4] /v3/{name}.html — 回归检查")
            page.goto(f"{BASE}/v3/{name}.html", wait_until="domcontentloaded", timeout=20000)
            time.sleep(1.0)
            h1 = page.locator("h1").first
            try:
                h1_text = h1.inner_text(timeout=5000).strip()[:40]
                visible = h1.is_visible()
                print(f"  h1: '{h1_text}' visible={visible}")
                if visible:
                    print(f"  ✓ {name} 顶部 h1 仍可见")
                else:
                    print(f"  ✗ {name} h1 不可见!")
            except Exception as e:
                print(f"  ✗ {name} h1 检测失败: {e}")
            page.screenshot(path=str(SCREENSHOT_DIR / f"{name}.png"), clip={"x": 0, "y": 0, "width": 1440, "height": 1200})

        browser.close()
    print(f"\nAll screenshots saved to {SCREENSHOT_DIR}")


if __name__ == "__main__":
    main()
