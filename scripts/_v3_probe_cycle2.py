from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    page = b.new_context(viewport={"width":1500,"height":1100}).new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="networkidle")
    page.wait_for_selector("#globe-stage canvas", timeout=15000)
    page.wait_for_timeout(2500)
    info = page.evaluate(r"""
() => {
  const ac = window.__allCities || [];
  const seoul = ac.find(c => c.city === 'Seoul');
  const irvine = ac.find(c => c.city === 'Irvine');
  // domSeoul: is there a DOM dot for Seoul?
  const dom = Array.from(document.querySelectorAll('.globe-city-dot'));
  const domSeoul = dom.find(d => d.dataset.cityKey === 'Seoul|South Korea');
  return {
    allCitiesHasSeoul: !!seoul,
    seoulEntry: seoul ? {city: seoul.city, country: seoul.country, lat: seoul.lat, lon: seoul.lon, n: seoul.n_companies, cos: seoul.companies && seoul.companies.length} : null,
    irvineEntry: irvine ? {city: irvine.city, country: irvine.country, lat: irvine.lat, lon: irvine.lon, n: irvine.n_companies} : null,
    domHasSeoul: !!domSeoul,
    domSeoulInnerHTML: domSeoul ? domSeoul.innerHTML.slice(0, 200) : null,
    domDotsTotal: dom.length,
    domDotsWithCycle: dom.filter(d => d.classList.contains('cycle-label')).length,
  };
}
""")
    import json
    print(json.dumps(info, ensure_ascii=False, indent=2))
    b.close()
