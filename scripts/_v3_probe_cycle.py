from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={"width":1500,"height":1100}).new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="networkidle")
    page.wait_for_selector("#globe-stage canvas", timeout=15000)
    page.wait_for_timeout(2500)
    info = page.evaluate(r"""
() => {
  const cg = window.__cycleGroups || {};
  const cc = window.__cycleCities || [];
  const ac = window.__allCities || [];
  const dotKeys = new Set(
    Array.from(document.querySelectorAll('.globe-city-dot'))
      .map(d => d.dataset.cityKey)
      .filter(k => k)
  );
  const cycleKeys = Object.keys(cg);
  const missing = cycleKeys.filter(k => !dotKeys.has(k));
  const present = cycleKeys.filter(k => dotKeys.has(k));
  return {
    cycleGroupsLen: cycleKeys.length,
    cycleCitiesLen: cc.length,
    allCitiesLen: ac.length,
    domDotKeysLen: dotKeys.size,
    presentInDom: present.length,
    missingFromDom: missing.length,
    missingSample: missing.slice(0, 8),
    presentSample: present.slice(0, 5),
    allCityFirst5: ac.slice(0,5).map(c => ({key: c.city+'|'+c.country, n: c.n_companies})),
  };
}
""")
    import json
    print(json.dumps(info, ensure_ascii=False, indent=2))
    b.close()
