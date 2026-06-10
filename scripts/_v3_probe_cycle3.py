from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={"width":1500,"height":1100}).new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="networkidle")
    page.wait_for_selector("#globe-stage canvas", timeout=15000)
    page.wait_for_timeout(3000)
    info = page.evaluate(r"""
() => {
  const bc = window.__buildCounter || {};
  const keys = bc.keys || [];
  const ac = (window.__allCities || []);
  const allKeys = new Set(ac.map(c => c.city + '|' + c.country));
  const builtKeys = new Set(keys);
  const inAcNotBuilt = Array.from(allKeys).filter(k => !builtKeys.has(k));
  const seoulBuildCount = keys.filter(k => k === 'Seoul|South Korea').length;
  return {
    buildCalls: bc.calls,
    distinctBuildKeys: builtKeys.size,
    allCitiesLen: ac.length,
    inAcNotBuilt: inAcNotBuilt.length,
    inAcNotBuiltSample: inAcNotBuilt.slice(0, 10),
    seoulBuildCount,
  };
}
""")
    import json
    print(json.dumps(info, ensure_ascii=False, indent=2))
    b.close()
