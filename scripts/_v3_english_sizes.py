"""List all rendered English text on v3/index.html with effective font-size,
to find which cards have the over-large English."""
from playwright.sync_api import sync_playwright
import re

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1440, "height": 900}, locale="zh-CN").new_page()
    page.goto("http://127.0.0.1:8790/v3/index.html", wait_until="domcontentloaded", timeout=20000)
    page.wait_for_selector("#rail .rail-section", timeout=8000)
    page.wait_for_timeout(2500)

    # 找所有 ASCII-dominant 文本元素 + 字号 >= 18px
    items = page.evaluate("""() => {
        const isLatin = (s) => {
            const t = (s || '').replace(/[\\s·\\d\\.,\\-–—%/()]/g, '');
            if (!t) return false;
            return /^[A-Za-z]+$/.test(t.replace(/[A-Za-z]/g, '').length === 0 ? t : t);
        };
        const out = [];
        const seen = new Set();
        document.querySelectorAll('main h1, main h2, main h3, main p, main span, main em, main strong, main small, main button, main a, main article > *').forEach(el => {
            // Only leaves
            if (el.children.length > 0) {
                // text node check
                let direct = '';
                el.childNodes.forEach(n => { if (n.nodeType === 3) direct += n.textContent; });
                if (!direct.trim()) return;
            }
            const text = (el.textContent || '').trim();
            if (!text || text.length > 80) return;
            // English-dominant: more A-Za-z than CJK
            const latin = (text.match(/[A-Za-z]/g) || []).length;
            const cjk   = (text.match(/[\\u4e00-\\u9fff]/g) || []).length;
            if (latin <= cjk || latin < 3) return;
            const cs = getComputedStyle(el);
            const fs = parseFloat(cs.fontSize);
            if (fs < 16) return;
            const rect = el.getBoundingClientRect();
            // de-dup by text + size
            const key = `${text}|${cs.fontSize}|${cs.fontFamily.split(',')[0]}`;
            if (seen.has(key)) return;
            seen.add(key);
            out.push({
                text,
                tag: el.tagName.toLowerCase(),
                cls: el.className,
                fontSize: cs.fontSize,
                fontFamily: cs.fontFamily.split(',')[0],
                fontStyle: cs.fontStyle,
                width: Math.round(rect.width),
                rendered: el.scrollWidth > el.clientWidth + 1,
            });
        });
        return out.sort((a, b) => parseFloat(b.fontSize) - parseFloat(a.fontSize));
    }""")

    print("=== English-dominant texts ≥16px on v3/index.html (sorted by size) ===")
    print(f"{'fs':>6}  {'tag':>6}  {'oflow':>5}  {'text':<48}  class")
    for it in items:
        ov = "OFLOW" if it["rendered"] else ""
        print(f"  {it['fontSize']:>6}  {it['tag']:>6}  {ov:>5}  {it['text'][:48]:<48}  {it['cls'][:60]}")

    browser.close()
