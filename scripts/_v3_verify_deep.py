"""Headless render check for new v3 pages. Loads each URL, collects console
errors, asserts key DOM nodes exist, and screenshots. HTTP 200 != rendered."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "audits" / "v3_deep_verify"
OUT.mkdir(parents=True, exist_ok=True)
BASE = "http://localhost:8765/v3/"

# (name, url, [css selectors that must have >=1 element with content])
CHECKS = [
    ("deep-dive", "deep-dive.html", ["#sb-svg .sb-arc", "#focus-card h3", "#mc-l1 .mc-item", "#finding-cards .editorial-block"]),
    ("cross-analysis", "cross-analysis.html", ["#lens1-grid .xa-cell", "#pivot-matrix .pv-cell, #pivot-wrap", "#lens2-grid"]),
    ("companies-filtered", "companies.html?track=EBD&ownership=Private", ["#co-tbody tr.co-row"]),
]


def main():
    fails = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, url, selectors in CHECKS:
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            errors = []
            page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
            page.on("pageerror", lambda e: errors.append("PAGEERROR: " + str(e)))
            try:
                page.goto(BASE + url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(1400)
            except Exception as e:
                fails.append(f"[{name}] goto failed: {e}")
                page.close(); continue
            for sel in selectors:
                try:
                    n = page.eval_on_selector_all(sel.split(",")[0], "els => els.length")
                except Exception:
                    n = 0
                if not n:
                    fails.append(f"[{name}] selector empty: {sel}")
            real_errors = [e for e in errors if "favicon" not in e.lower()]
            if real_errors:
                fails.append(f"[{name}] console errors: {real_errors[:4]}")
            page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
            print(f"  [{name}] arcs/checks done · errors={len(real_errors)}")
            page.close()
        browser.close()
    print("\n" + ("ALL OK" if not fails else "FAILURES:\n  " + "\n  ".join(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
