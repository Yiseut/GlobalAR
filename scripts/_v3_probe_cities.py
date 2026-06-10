"""Quick probe: top cities by company count via Playwright, no bash interpolation."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={"width":1500,"height":1100}).new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="networkidle")
    page.wait_for_selector("#globe-stage canvas", timeout=15000)
    page.wait_for_timeout(2500)
    info = page.evaluate(r"""
() => {
  const co = (window.GLOBAL_AESTHETICS_DATA||{}).geo_companies || [];
  const map = new Map();
  co.forEach(c => {
    const k = (c.city || '—').trim() + '|' + c.country;
    if (!map.has(k)) map.set(k, {city: c.city, country: c.country, lat: c.lat, lon: c.lon, n: 0});
    map.get(k).n++;
  });
  const arr = Array.from(map.values()).sort((a,b) => b.n - a.n);
  return {total_keys: map.size, top12: arr.slice(0,12), bottom5_of_top40: arr.slice(35,40)};
}
""")
    print("total unique city keys:", info["total_keys"])
    print("top 12:")
    for c in info["top12"]:
        print(" ", c)
    print()
    print("rank 35-40 (still in top 40):")
    for c in info["bottom5_of_top40"]:
        print(" ", c)
    b.close()
