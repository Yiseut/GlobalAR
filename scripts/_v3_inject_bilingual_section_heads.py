"""One-shot edit: add `<span class="en">EN</span>` after every
`<span class="cn">CN-subtitle</span>` whose parent `<section class="block">`
section-head is missing it.

Reads a hand-curated translation map keyed by either:
  - exact section CN H2 text (preferred)
  - or (cn-h2, cn-subtitle) pair fallback

For each html file under web/v3/, finds blocks of the form:

    <h2>{cn-h2}</h2>
    <span class="cn">{cn-sub}</span>          # already there
    (NOT followed by <span class="en">…)

…and inserts:

    <span class="en">{en}</span>

Idempotent: skips sections that already have an `.en` span.

Run with: PYTHONUTF8=1 python scripts/_v3_inject_bilingual_section_heads.py
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
V3 = ROOT / "web" / "v3"

# CN H2 text → EN equivalent. When a CN h2 appears in multiple pages with the
# same English meaning, one mapping covers all. For ambiguous CN, append the
# .cn-subtitle as a key tuple. Order doesn't matter; both forms are tried.
EN_MAP: dict[str, str] = {
    # Core / cross-cutting
    "核心读数":           "Headline numbers",
    "核心指标":           "Core metrics",
    "解读":               "Interpretation",
    "解读与下钻":         "Interpretation & drill-down",
    "编辑视角":           "Editorial · new lenses",
    "全球分布":           "Global footprint",

    # companies.html
    "价值链定位":         "Value chain positioning",
    "集团结构":           "Corporate families",
    "国家 × 上市状态":    "Country × listing status",
    "公司全表":           "Company directory",

    # companies-matrix.html
    "企业 × 材料赛道矩阵": "Companies × material tracks",

    # tracks.html
    "材料 taxonomy 全景": "Material taxonomy landscape",
    "L1 × L2 分布":       "L1 × L2 distribution",
    "L1 内部技术构成":     "Tech mix per L1",
    "监管准入分布":        "Regulatory pathway mix",
    "适应症 × 赛道":      "Indication × track",
    "各赛道时间发展":      "Track evolution timeline",
    "全球技术排名":        "Top technologies · global",
    "产品密度":           "Products per company",

    # indications.html
    "适应症排名":          "Indication ranking",
    "适应症 × 技术 矩阵":  "Indication × technology",
    "适应症 × 商业赛道":   "Indication × commercial L1",
    "适应症 × 监管机构":   "Indication × Regulator",

    # technology-tree.html
    "技术族":             "Technology families",
    "Top 15 技术排名":     "Top 15 technologies",
    "技术 × 商业 矩阵":    "Tech × commercial cross-tab",
    "技术成熟度":          "Tech maturity",

    # regulatory-pulse.html
    "年度时间线":          "Annual timeline",
    "监管通道分类":        "Regulatory pathway breakdown",
    "头部企业":            "Top companies",

    # geo-deep-dive.html
    "韩国画像":            "Korea profile",
    "区域 × 赛道分布":     "Region × track distribution",
    "国家排名":            "Country ranking",

    # capital-map.html
    "估值带分布":          "Valuation bands",
    "交易所分布":          "Exchange distribution",
    "头部已上市主体":       "Top listed entities",
    "财务快照 · 16 家":    "Financial snapshot · 16 cos",
    "集团树":              "Corporate family tree",

    # cross-analysis.html
    "国家 × 赛道 × 资本结构 × FDA 命中":
        "Country × Track × Ownership × FDA",
    "公司 × 监管通道 × 年份":
        "Company × Pathway × Year",
    "适应症桶 × 监管机构 × 区域":
        "Indication × Regulator × Region",
    "可切换 4D 透视矩阵":
        "Switchable 4D pivot",

    # deep-dive.html
    "材料三级分类 · 旭日下钻": "Material 3-level · sunburst drill",
    "商业路线逐列下钻":         "Commercial path · column drill",

    # topic.html (some are template-literal containing ${esc(displayL1)} etc.)
    "集中度":                  "Concentration · CR5 / CR10 / HHI",
    "价值链位置":               "Value chain position",
    "子赛道生命周期":            "Sub-track lifecycle",
    "官方适应症 × 监管机构":     "Official indication × Regulator",
    "近 24 月新进入者 + 活跃者":  "New entrants + active · last 24 mo",
    "头部公司":                 "Top companies",
    "技术构成":                 "Tech composition",
    "国家分布":                 "Country distribution",
    "国家 × L2 子赛道":         "Country × L2",
    "L2 子赛道":                "L2 sub-tracks",

    # Already-bilingual on index.html — listed for completeness so re-runs
    # would be no-ops if anyone ever stripped the en spans.
    "赛道格局":   "Track structure",
    "全球医美企业星图": "Global enterprise atlas",
    "国家分布":   "Country distribution",
    "区域分布":   "Region mix",
    "适应症 Top 12": "Top 12 indications",
    "赛道分布":   "Track share",
}

# Pattern: <h2>...</h2> then ANY whitespace, then <span class="cn">...</span>
# but NOT immediately (within same section-head block) followed by class="en".
SECTION_HEAD_PAT = re.compile(
    r'(<h2>(?P<h2>[^<]+)</h2>\s*<span class="cn">(?P<sub>[^<]*)</span>)'
    r'(?P<tail>\s*(?!<span\s+class="en"))',
    re.S,
)


def process_file(path: Path) -> tuple[int, int]:
    """Return (n_already_bilingual, n_injected)."""
    text = path.read_text(encoding="utf-8")
    n_inj = 0
    n_skipped = 0

    def repl(m: re.Match) -> str:
        nonlocal n_inj, n_skipped
        h2 = m.group("h2").strip()
        en = EN_MAP.get(h2)
        if not en:
            # Strip template-literal junk: topic.html templates contain
            # ${esc(displayL1)} or similar — try the bare CN before $.
            base = re.split(r"\$\{|\s+·", h2)[0].strip()
            en = EN_MAP.get(base)
        if not en:
            n_skipped += 1
            return m.group(0)
        n_inj += 1
        head = m.group(1)
        tail = m.group("tail")
        return f'{head}<span class="en">{en}</span>{tail}'

    # First count rows that already have an .en — those won't match the
    # negative lookahead so they don't increase n_inj.
    new_text = SECTION_HEAD_PAT.sub(repl, text)

    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
    return n_skipped, n_inj


def main() -> None:
    files = sorted(V3.glob("*.html"))
    files = [p for p in files if not p.name.startswith("_")]  # skip private demos
    total_inj = 0
    for f in files:
        try:
            skipped, injected = process_file(f)
        except Exception as e:
            print(f"  ! {f.name}  FAILED: {e}")
            continue
        if injected or skipped:
            note = []
            if injected: note.append(f"+{injected} en")
            if skipped:  note.append(f"skip {skipped}")
            print(f"  {f.name:30s}  {' · '.join(note)}")
        total_inj += injected
    print()
    print(f"injected {total_inj} EN spans across {len(files)} files")


if __name__ == "__main__":
    main()
