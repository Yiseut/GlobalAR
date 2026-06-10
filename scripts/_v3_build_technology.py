"""Aggregate product_master + registration_evidence into the v3 Technology Tree page feed.

This is the INVERSE of the tracks page — tech-led view instead of commercial-led.
For each technology / material / energy source, show:
  - which commercial L1 it serves (cross-tab)
  - which products use it (via company / brand)
  - launch / approval year span (maturity)

Output: web/v3/v3-technology.js → window.V3_TECHNOLOGY_DATA
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-technology.js"

# Hand-curated tech family grouping — clusters the raw 235 tech values into ~8 families
TECH_FAMILIES = {
    "Material · HA 族": {
        "tags": ["Hyaluronic Acid", "HA Crosslinked", "HA Non-crosslinked", "HA Hybrid"],
        "color": "#6B5A75",   # Injectables purple
    },
    "Material · 神经毒素": {
        "tags": ["Botulinum Toxin A", "Botulinum Toxin B", "Botulinum Toxin", "Neurotoxin"],
        "color": "#8C7B91",
    },
    "Material · 生物刺激物": {
        "tags": ["PLLA", "PCL", "CaHA", "Polynucleotide", "Collagen", "Polypeptides", "PDLLA"],
        "color": "#A8B59A",
    },
    "Material · 干细胞 / 再生": {
        "tags": ["Stem Cell", "Exosome", "PRP", "PRF", "Growth Factor", "Cell Therapy"],
        "color": "#C8B8D0",
    },
    "Energy · 激光": {
        "tags": ["Diode Laser", "CO2 Laser", "Picosecond Laser", "Erbium Laser", "Nd:YAG",
                 "Alexandrite Laser", "Long-pulsed Laser", "Fractional Laser", "Q-Switched Laser",
                 "Pulsed Dye Laser", "Excimer Laser"],
        "color": "#8E3A3A",   # EBD oxblood
    },
    "Energy · 射频 (RF)": {
        "tags": ["Radiofrequency", "Fractional RF", "Bipolar RF", "Monopolar RF", "RF Microneedling"],
        "color": "#C76B68",
    },
    "Energy · 超声": {
        "tags": ["HIFU", "LIPUS", "MFU", "Ultrasound"],
        "color": "#D9AE91",
    },
    "Energy · 光 / 其他": {
        "tags": ["IPL", "LED Therapy", "Cryotherapy", "EMS", "Electroporation", "Plasma"],
        "color": "#EC9B73",
    },
    "Mechanical · 表面 / 介入": {
        "tags": ["Microneedling", "Chemical Peel", "Thread Lift", "PDO Thread", "Cog Thread", "Microdermabrasion"],
        "color": "#CFB58E",
    },
    "Hybrid · 中胚层 / 综合": {
        "tags": ["Mesotherapy", "Mesotherapy Cocktail", "Skin Booster"],
        "color": "#5A6878",
    },
}


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def assign_family(tech: str) -> str | None:
    """Return the family name a tech belongs to, or None if not mapped."""
    t = tech.strip()
    for family, spec in TECH_FAMILIES.items():
        for tag in spec["tags"]:
            if tag.lower() == t.lower() or tag.lower() in t.lower():
                return family
    return None


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    products = conn.execute(
        """
        SELECT
          pm.product_id, pm.company_id, pm.company, pm.brand,
          pm.standard_product_name,
          pm.commercial_path_l1, pm.commercial_path_l2,
          pm.technology_path_l1, pm.technology_path_l2,
          pm.material_or_energy_source
        FROM product_master pm
        WHERE COALESCE(pm.commercial_path_l1, '') NOT IN ('Services', '')
        """
    ).fetchall()

    # Join with registration_evidence for launch year
    appr = conn.execute(
        "SELECT product_id, substr(approval_date,1,4) AS yr FROM registration_evidence "
        "WHERE approval_date IS NOT NULL AND approval_date != ''"
    ).fetchall()
    conn.close()

    product_years = defaultdict(list)
    for pid, yr in appr:
        try:
            product_years[pid].append(int(yr))
        except (TypeError, ValueError):
            pass

    rows = []
    for r in products:
        tech = clean(r["material_or_energy_source"]) or clean(r["technology_path_l1"])
        if not tech or tech == "未分类":
            continue
        l1 = clean(r["commercial_path_l1"])
        l2 = clean(r["commercial_path_l2"])
        years = product_years.get(r["product_id"], [])
        rows.append({
            "tech": tech,
            "family": assign_family(tech),
            "company_id": r["company_id"],
            "company": clean(r["company"]),
            "brand": clean(r["brand"]),
            "product": clean(r["standard_product_name"]),
            "l1": l1,
            "l2": l2,
            "tech_l2": clean(r["technology_path_l2"]),
            "first_year": min(years) if years else None,
            "last_year":  max(years) if years else None,
        })

    # ---- Tech ranking ----
    tech_counts = Counter(r["tech"] for r in rows).most_common()
    total_products = len(rows)
    total_techs = len(tech_counts)

    # ---- Top 15 techs with extra detail ----
    top_techs = []
    for tech, n in tech_counts[:15]:
        bucket = [r for r in rows if r["tech"] == tech]
        l1_counts = Counter(r["l1"] for r in bucket if r["l1"]).most_common(3)
        l2_counts = Counter(r["l2"] for r in bucket if r["l2"]).most_common(3)
        companies = {r["company_id"] for r in bucket if r["company_id"]}
        brands = {r["brand"] for r in bucket if r["brand"]}
        years = [y for r in bucket for y in [r["first_year"]] if y]
        last_years = [y for r in bucket for y in [r["last_year"]] if y]
        top_techs.append({
            "tech": tech,
            "family": assign_family(tech),
            "n_products": n,
            "n_companies": len(companies),
            "n_brands": len(brands),
            "top_l1": [{"l1": l, "n": c} for l, c in l1_counts],
            "top_l2": [{"l2": l, "n": c} for l, c in l2_counts],
            "first_year": min(years) if years else None,
            "last_year":  max(last_years) if last_years else None,
            "covered": bool(years),
        })

    # ---- Tech family rollup ----
    family_rollup = []
    for family, spec in TECH_FAMILIES.items():
        bucket = [r for r in rows if r["family"] == family]
        if not bucket:
            continue
        member_counts = Counter(r["tech"] for r in bucket).most_common()
        l1_counts = Counter(r["l1"] for r in bucket if r["l1"]).most_common(3)
        companies = {r["company_id"] for r in bucket if r["company_id"]}
        family_rollup.append({
            "family": family,
            "color": spec["color"],
            "n_products": len(bucket),
            "n_companies": len(companies),
            "n_techs": len(member_counts),
            "members": [{"name": t, "n": n} for t, n in member_counts],
            "top_l1": [{"l1": l, "n": c} for l, c in l1_counts],
        })
    family_rollup.sort(key=lambda f: -f["n_products"])

    # ---- Tech × L1 matrix (top 10 techs × top 6 L1) ----
    matrix_techs = [t for t, _ in tech_counts[:10]]
    matrix_l1s = [l for l, _ in Counter(r["l1"] for r in rows if r["l1"]).most_common(6)]
    tech_x_l1 = []
    for t in matrix_techs:
        l1_in_tech = Counter(r["l1"] for r in rows if r["tech"] == t and r["l1"]).most_common()
        l1_dict = dict(l1_in_tech)
        total = sum(l1_dict.values())
        tech_x_l1.append({
            "tech": t,
            "values": {l: l1_dict.get(l, 0) for l in matrix_l1s},
            "total": total,
        })

    # ---- Maturity buckets — based on first / last approval year ----
    NEW_YEAR_THRESH = 2018
    LEGACY_YEAR_THRESH = 2010
    tech_maturity = {"emerging": [], "established": [], "legacy": [], "unverified": []}
    for tech_info in top_techs:
        if not tech_info["covered"]:
            tech_maturity["unverified"].append(tech_info)
            continue
        first = tech_info["first_year"]
        last = tech_info["last_year"]
        if first and first >= NEW_YEAR_THRESH:
            tech_maturity["emerging"].append(tech_info)
        elif last and last >= 2020 and first and first < NEW_YEAR_THRESH:
            tech_maturity["established"].append(tech_info)
        elif last and last < 2018:
            tech_maturity["legacy"].append(tech_info)
        else:
            tech_maturity["established"].append(tech_info)

    # ---- Findings ----
    top1 = tech_counts[0] if tech_counts else ("HA", 184)
    top1_share = round(100 * top1[1] / total_products, 1)
    # multi-application techs: serves >=3 commercial L1
    cross_app_techs = [
        t for t in top_techs
        if len([l for l in t["top_l1"] if l["n"] > 0]) >= 3
    ]
    largest_family = family_rollup[0] if family_rollup else None

    findings = [
        {
            "stamp": "Finding · 01",
            "lead": "<em>{0}</em> 一项技术占全行业 <em>{1}%</em>。".format(top1[0], top1_share),
            "num_pair": {"num": "{0}%".format(top1_share), "unit": "{0} share".format(top1[0])},
            "body": "<em>{t}</em> 在 <em>{n}</em> 款产品里被采用 — 远超第二名 <em>{t2}</em>（<em>{n2}</em> 款）。这意味着「<em>{t}</em>」不只是一种材料，而是注射赛道事实上的「平台技术」。其他技术都在抢「不靠 HA 的市场」。".format(
                t=top1[0], n=top1[1],
                t2=tech_counts[1][0] if len(tech_counts) > 1 else "—",
                n2=tech_counts[1][1] if len(tech_counts) > 1 else 0,
            ),
            "wash": "w-rose-deep",
        },
        {
            "stamp": "Finding · 02",
            "lead": "<em>{0}</em> 种技术跨多个商业赛道。".format(len(cross_app_techs)),
            "num_pair": {"num": len(cross_app_techs), "unit": "cross-application techs"},
            "body": "Top 15 技术里 <em>{n}</em> 种被 ≥3 个商业 L1 采用（如 Microneedling 既在 EBD 又在 Cosmeceutical 也在 Regenerative）。这些是「平台型技术」 — 一种技术撑多个商业赛道，是上游公司的护城河资产。".format(n=len(cross_app_techs)),
            "wash": "w-apricot",
        },
        {
            "stamp": "Finding · 03",
            "lead": "<em>{0}</em> 是产品数最多的技术族。".format(largest_family["family"] if largest_family else "—"),
            "num_pair": {
                "num": largest_family["n_products"] if largest_family else 0,
                "unit": "products in family",
            },
            "body": "<em>{f}</em> 涵盖 <em>{n}</em> 款产品 / <em>{c}</em> 家公司 / <em>{t}</em> 种子技术。族内主要服务 <em>{l1}</em> 赛道。把同族技术放在一起看，比单看 \"HA 184\" 这种点数据更能识别「公司能在哪个技术族里平行扩张」。".format(
                f=largest_family["family"] if largest_family else "—",
                n=largest_family["n_products"] if largest_family else 0,
                c=largest_family["n_companies"] if largest_family else 0,
                t=largest_family["n_techs"] if largest_family else 0,
                l1=", ".join(l["l1"] for l in largest_family["top_l1"][:2]) if largest_family else "—",
            ),
            "wash": "w-plum",
        },
    ]

    payload = {
        "summary": {
            "total_products": total_products,
            "total_techs": total_techs,
            "total_families": len(family_rollup),
            "top_tech": top1[0],
            "top_tech_n": top1[1],
            "top_tech_share": top1_share,
            "cross_app_count": len(cross_app_techs),
            "covered_with_year": sum(1 for r in rows if r["first_year"]),
        },
        "top_techs": top_techs,
        "family_rollup": family_rollup,
        "tech_x_l1": {
            "columns": matrix_l1s,
            "rows": tech_x_l1,
        },
        "maturity": {
            "emerging":    [t["tech"] for t in tech_maturity["emerging"]],
            "established": [t["tech"] for t in tech_maturity["established"]],
            "legacy":      [t["tech"] for t in tech_maturity["legacy"]],
            "unverified":  [t["tech"] for t in tech_maturity["unverified"]],
        },
        "findings": findings,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "// auto-generated by scripts/_v3_build_technology.py — do not hand-edit\n"
        f"// {total_products} products / {total_techs} distinct techs / {len(family_rollup)} families\n"
        f"window.V3_TECHNOLOGY_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} · {total_products} products · {total_techs} techs · {len(family_rollup)} families · {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
