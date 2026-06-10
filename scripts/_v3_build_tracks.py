"""Aggregate product_master + companies into the v3 Track Structure page's data feed.

Produces web/v3/v3-tracks.js which exposes window.V3_TRACKS_DATA with these views:

  summary        — top-line numbers (L1 count, L2 count, dominant L1, etc.)
  l1_breakdown   — per L1: products, companies, brands, l2[], tech[], regions[], ownership_mix
  l1_x_l2        — for the L1×L2 matrix heatmap (rows × cols × value)
  l1_x_tech      — for the commercial × technology cross-tab (which techs feed each L1)
  tech_ranking   — top materials / energy sources by product count
  density        — products-per-company per L1 (consolidation signal)
  findings       — 3-4 editorial findings derived from the aggregates
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-tracks.js"

L1_ORDER = [
    "EBD", "Injectables", "Skincare", "Regenerative", "Consumables",
    "Implants", "Diagnostics", "Surgical", "Pharma",
    # "Services" excluded — different access mechanism + business model
]
L1_EXCLUDE = {"Services"}
L1_ALIASES = {  # normalize raw db values to canonical L1 labels
    "Injectables": "Injectables",
    "EBD": "EBD",
    "Skincare": "Skincare",
    "Regen": "Regenerative",
    "Regenerative": "Regenerative",
    "Consumables": "Consumables",
    "Implants": "Implants",
    "Diagnostics": "Diagnostics",
    "Surgical": "Surgical",
    "Pharma": "Pharma",
}


def display_l1(l1: str) -> str:
    return "Cosmeceutical" if l1 == "Skincare" else l1

def norm_l1(raw: str) -> str:
    if not raw:
        return ""
    return L1_ALIASES.get(raw.strip(), raw.strip())


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    products = conn.execute(
        """
        SELECT
          pm.product_id, pm.company_id, pm.brand, pm.standard_product_name,
          pm.commercial_path_l1, pm.commercial_path_l2,
          pm.technology_path_l1, pm.technology_path_l2,
          pm.material_or_energy_source,
          c.region, c.hq_country, c.ownership
        FROM product_master pm
        LEFT JOIN companies c ON c.company = pm.company
        """
    ).fetchall()
    conn.close()

    rows = []
    for r in products:
        l1 = norm_l1(clean(r["commercial_path_l1"]))
        if not l1 or l1 in L1_EXCLUDE:
            continue
        l2 = clean(r["commercial_path_l2"]) or "未分类"
        tech_l1 = clean(r["technology_path_l1"]) or "未分类"
        tech_l2 = clean(r["technology_path_l2"]) or ""
        material = clean(r["material_or_energy_source"]) or tech_l1
        rows.append({
            "product_id": r["product_id"],
            "company_id": r["company_id"],
            "brand": clean(r["brand"]),
            "name": clean(r["standard_product_name"]),
            "l1": l1, "l2": l2,
            "tech_l1": tech_l1, "tech_l2": tech_l2,
            "material": material,
            "region": clean(r["region"]),
            "country": clean(r["hq_country"]),
            "ownership": clean(r["ownership"]),
        })

    # ----- summary --------------------------------------------------------
    total = len(rows)
    l1_set = sorted({r["l1"] for r in rows if r["l1"]}, key=lambda x: L1_ORDER.index(x) if x in L1_ORDER else 999)
    l2_set = sorted({(r["l1"], r["l2"]) for r in rows if r["l2"]})
    tech_set = sorted({r["tech_l1"] for r in rows if r["tech_l1"]})
    material_set = sorted({r["material"] for r in rows if r["material"]})

    # ----- L1 breakdown ---------------------------------------------------
    l1_breakdown = []
    for l1 in l1_set:
        bucket = [r for r in rows if r["l1"] == l1]
        l2_counts = Counter(r["l2"] for r in bucket)
        tech_counts = Counter(r["tech_l1"] for r in bucket)
        material_counts = Counter(r["material"] for r in bucket)
        region_counts = Counter(r["region"] for r in bucket if r["region"])
        ownership_counts = Counter(r["ownership"] for r in bucket if r["ownership"])
        companies = {r["company_id"] for r in bucket if r["company_id"]}
        brands = {r["brand"] for r in bucket if r["brand"]}
        l1_breakdown.append({
            "l1": l1,
            "products": len(bucket),
            "companies": len(companies),
            "brands": len(brands),
            "l2_top": l2_counts.most_common(8),
            "tech_top": tech_counts.most_common(8),
            "material_top": material_counts.most_common(6),
            "region_mix": region_counts.most_common(6),
            "ownership_mix": ownership_counts.most_common(),
            "products_per_company": round(len(bucket) / max(1, len(companies)), 2),
        })

    # ----- L1 × L2 matrix (top N L2 per L1, used as stacked bar + card grid) --
    # Load approval years + indication counts via product_id JOIN
    conn2 = sqlite3.connect(str(DB))
    approval_by_pid = defaultdict(list)
    for pid, yr in conn2.execute(
        "SELECT product_id, substr(approval_date,1,4) FROM registration_evidence "
        "WHERE approval_date IS NOT NULL AND approval_date != ''"
    ):
        try:
            approval_by_pid[pid].append(int(yr))
        except (TypeError, ValueError):
            pass
    indication_by_pid = defaultdict(set)
    for pid, bk in conn2.execute(
        "SELECT product_id, buckets FROM official_indication_evidence "
        "WHERE buckets IS NOT NULL AND buckets != ''"
    ):
        for tag in [t.strip() for t in clean(bk).split(",") if t.strip()]:
            indication_by_pid[pid].add(tag)
    # Re-pull product_id per (l1, l2) since rows[] doesn't keep it
    rows_with_pid = list(conn2.execute(
        "SELECT product_id, company_id, brand, commercial_path_l1, commercial_path_l2 "
        "FROM product_master WHERE COALESCE(commercial_path_l1, '') NOT IN ('Services', '')"
    ))
    conn2.close()

    l1_x_l2 = []
    for entry in l1_breakdown:
        l1 = entry["l1"]
        bucket = [r for r in rows if r["l1"] == l1]
        l2_counts = Counter(r["l2"] for r in bucket).most_common()
        segments = []
        for l2, n in l2_counts:
            l2_rows = [r for r in bucket if r["l2"] == l2]
            l2_pids = [r2[0] for r2 in rows_with_pid
                       if norm_l1(clean(r2[3])) == l1 and (clean(r2[4]) or "未分类") == l2]
            brand_counts = Counter(r["brand"] for r in l2_rows if r["brand"])
            company_set = {r["company_id"] for r in l2_rows if r["company_id"]}
            brand_set = {r["brand"] for r in l2_rows if r["brand"]}
            all_years = [y for pid in l2_pids for y in approval_by_pid.get(pid, [])]
            ind_set = set()
            for pid in l2_pids:
                ind_set |= indication_by_pid.get(pid, set())
            segments.append({
                "l2": l2,
                "n": n,
                "companies": len(company_set),
                "company_ids": sorted(c for c in company_set if c),
                "brands": len(brand_set),
                "indications": len(ind_set),
                "latest_year": max(all_years) if all_years else None,
                "first_year": min(all_years) if all_years else None,
                "sample_brands": [b for b, _ in brand_counts.most_common(5)],
                "top_indications": sorted(ind_set)[:5] if ind_set else [],
            })
        l1_x_l2.append({
            "l1": l1,
            "total": entry["products"],
            "segments": segments,
        })

    # ----- L1 × Technology L1 cross-tab ----------------------------------
    l1_x_tech = []
    for entry in l1_breakdown:
        l1 = entry["l1"]
        bucket = [r for r in rows if r["l1"] == l1]
        tech_counts = Counter(r["tech_l1"] for r in bucket).most_common()
        l1_x_tech.append({
            "l1": l1,
            "total": entry["products"],
            "techs": [{"tech": t, "n": n} for t, n in tech_counts],
        })

    # ----- Tech / material ranking (global) ------------------------------
    tech_total = Counter(r["tech_l1"] for r in rows).most_common(20)
    material_total = Counter(r["material"] for r in rows).most_common(20)

    # ----- Density (products per company per L1) -------------------------
    density = [
        {"l1": e["l1"], "products": e["products"], "companies": e["companies"],
         "ppc": e["products_per_company"]}
        for e in l1_breakdown
    ]
    density.sort(key=lambda x: x["ppc"], reverse=True)

    # ----- Regulatory mix per L1 (join with registration_evidence) -------
    # Map regulator → bucket (FDA / CE-MDR / NMPA / IFU / other)
    REG_BUCKET = {
        "FDA": "FDA",
        "EUDAMED / European Commission": "CE-MDR",
        "Notified Body / Manufacturer": "CE-MDR",
        "CE/MDR": "CE-MDR",
        "NMPA": "NMPA",
        "Manufacturer IFU": "IFU",
    }
    REG_ORDER = ["FDA", "CE-MDR", "NMPA", "IFU", "Other"]
    product_l1_map = {r["product_id"]: r["l1"] for r in rows if r["product_id"]}
    conn = sqlite3.connect(str(DB))
    reg_rows = conn.execute("SELECT product_id, regulator FROM registration_evidence").fetchall()
    reg_per_l1 = defaultdict(lambda: defaultdict(int))
    for pid, regulator in reg_rows:
        l1 = product_l1_map.get(pid)
        if not l1:
            continue
        bucket = REG_BUCKET.get(clean(regulator), "Other")
        reg_per_l1[l1][bucket] += 1
    regulatory_mix = []
    for l1 in l1_set:
        per = reg_per_l1.get(l1, {})
        bucket_total = sum(per.values())
        regulatory_mix.append({
            "l1": l1,
            "total": bucket_total,
            "buckets": [{"name": b, "n": per.get(b, 0)} for b in REG_ORDER],
        })

    # ----- Indication mix per L1 (join with official_indication_evidence) -
    ind_rows = conn.execute(
        "SELECT product_id, buckets FROM official_indication_evidence WHERE buckets IS NOT NULL AND buckets != ''"
    ).fetchall()
    ind_per_l1 = defaultdict(Counter)
    ind_global = Counter()
    for pid, bk in ind_rows:
        l1 = product_l1_map.get(pid)
        if not l1:
            continue
        # buckets are comma-separated
        for tag in [t.strip() for t in clean(bk).split(",") if t.strip()]:
            ind_per_l1[l1][tag] += 1
            ind_global[tag] += 1
    top_indications = [t for t, _ in ind_global.most_common(10)]
    indication_heatmap = {
        "columns": top_indications,
        "rows": [
            {
                "l1": l1,
                "values": {ind: ind_per_l1.get(l1, {}).get(ind, 0) for ind in top_indications},
                "total": sum(ind_per_l1.get(l1, {}).get(ind, 0) for ind in top_indications),
            }
            for l1 in l1_set if sum(ind_per_l1.get(l1, {}).get(ind, 0) for ind in top_indications) > 0
        ],
    }

    # ----- Timeseries: approval_date by L1 × year ------------------------
    year_rows = conn.execute(
        "SELECT product_id, substr(approval_date,1,4) AS yr FROM registration_evidence WHERE approval_date IS NOT NULL AND approval_date != ''"
    ).fetchall()
    YEAR_MIN, YEAR_MAX = 2010, 2026   # focus on last 17 years
    ts_per_l1_year = defaultdict(lambda: defaultdict(int))
    for pid, yr in year_rows:
        try:
            y = int(yr)
        except (TypeError, ValueError):
            continue
        if y < YEAR_MIN or y > YEAR_MAX:
            continue
        l1 = product_l1_map.get(pid)
        if not l1:
            continue
        ts_per_l1_year[l1][y] += 1
    timeseries = {
        "years": list(range(YEAR_MIN, YEAR_MAX + 1)),
        "series": [
            {
                "l1": l1,
                "data": [ts_per_l1_year.get(l1, {}).get(y, 0) for y in range(YEAR_MIN, YEAR_MAX + 1)],
                "total": sum(ts_per_l1_year.get(l1, {}).values()),
            }
            for l1 in l1_set if sum(ts_per_l1_year.get(l1, {}).values()) > 0
        ],
    }
    conn.close()

    # ----- Findings (editorial — derived from aggregates) ----------------
    sorted_by_products = sorted(l1_breakdown, key=lambda x: -x["products"])
    top_l1 = sorted_by_products[0] if sorted_by_products else None
    second_l1 = sorted_by_products[1] if len(sorted_by_products) > 1 else None
    top_tech = tech_total[0] if tech_total else ("HA", 0)
    top_material = material_total[0] if material_total else ("HA", 0)
    most_dense = max(density, key=lambda x: x["ppc"]) if density else None
    most_fragmented = min((x for x in density if x["companies"] > 5),
                         key=lambda x: x["ppc"], default=None)
    # cross-tab insights: EBD has many technologies (Diode/HIFU/RF/CO2/etc)
    ebd_entry = next((e for e in l1_x_tech if e["l1"] == "EBD"), None)
    ebd_tech_spread = len(ebd_entry["techs"]) if ebd_entry else 0
    inj_entry = next((e for e in l1_x_tech if e["l1"] == "Injectables"), None)
    inj_top_tech_share = (
        round(100 * inj_entry["techs"][0]["n"] / inj_entry["total"], 1)
        if inj_entry and inj_entry["total"] else 0
    )

    findings = [
        {
            "stamp": "Finding · 01",
            "lead": "光电 (EBD) 不是单一技术，是 <em>{0}</em> 条技术路线的混战。".format(ebd_tech_spread),
            "num_pair": {"num": ebd_tech_spread, "unit": "tech families in EBD"},
            "body": "EBD <em>{ebd_n}</em> 款产品分散在 <em>{n}</em> 条技术路线（Diode / HIFU / RF / CO2 / IPL / Nd:YAG ...）— 没有任何单一技术占主导。这意味着「EBD」更像一个赛道集合而不是一个赛道，下钻必须按 technology_path 切分。".format(
                ebd_n=ebd_entry["total"] if ebd_entry else 0,
                n=ebd_tech_spread,
            ),
            "wash": "w-rose-deep",
        },
        {
            "stamp": "Finding · 02",
            "lead": "注射赛道高度技术集中。",
            "num_pair": {"num": "{0}%".format(inj_top_tech_share), "unit": "Injectables · top tech share"},
            "body": "注射类 <em>{n}</em> 款产品里，光是头部一项技术 ({tech}) 就占 <em>{share}</em>%。剩下分给 PLLA / PCL / CaHA / Botulinum / PRP 等。注射赛道有清晰的「技术霸主」，跟 EBD 完全相反。".format(
                n=inj_entry["total"] if inj_entry else 0,
                tech=inj_entry["techs"][0]["tech"] if inj_entry and inj_entry["techs"] else "—",
                share=inj_top_tech_share,
            ),
            "wash": "w-apricot",
        },
        {
            "stamp": "Finding · 03",
            "lead": "{0} 的「产品/公司密度」最高。".format(display_l1(most_dense["l1"]) if most_dense else "—"),
            "num_pair": {
                "num": "{0:.1f}".format(most_dense["ppc"]) if most_dense else "—",
                "unit": "products per company",
            },
            "body": "在 <em>{l1}</em> 赛道，平均每家公司做 <em>{ppc}</em> 款产品 — 远高于全行业平均 <em>{avg:.1f}</em>。这暗示该赛道里有「平台型公司」(单家做多款)而非「单品型公司」。".format(
                l1=display_l1(most_dense["l1"]) if most_dense else "—",
                ppc=most_dense["ppc"] if most_dense else 0,
                avg=total / max(1, len({r["company_id"] for r in rows if r["company_id"]})),
            ),
            "wash": "w-plum",
        },
    ]

    payload = {
        "summary": {
            "total_products": total,
            "l1_count": len(l1_set),
            "l2_count": len(l2_set),
            "tech_count": len(tech_set),
            "material_count": len(material_set),
            "top_l1": top_l1["l1"] if top_l1 else "",
            "top_l1_products": top_l1["products"] if top_l1 else 0,
            "top_tech": top_tech[0],
            "top_tech_products": top_tech[1],
            "top_material": top_material[0],
            "top_material_products": top_material[1],
            "avg_products_per_company": round(
                total / max(1, len({r["company_id"] for r in rows if r["company_id"]})), 2
            ),
        },
        "l1_breakdown": l1_breakdown,
        "l1_x_l2": l1_x_l2,
        "l1_x_tech": l1_x_tech,
        "tech_ranking": [{"name": t, "n": n} for t, n in tech_total],
        "material_ranking": [{"name": m, "n": n} for m, n in material_total],
        "density": density,
        "regulatory_mix": regulatory_mix,
        "indication_heatmap": indication_heatmap,
        "timeseries": timeseries,
        "findings": findings,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "// auto-generated by scripts/_v3_build_tracks.py — do not hand-edit\n"
        "// {total} products / {n_l1} L1 / {n_l2} L2 / {n_tech} tech\n"
        "window.V3_TRACKS_DATA = {payload};\n"
    ).format(
        total=total,
        n_l1=len(l1_set),
        n_l2=len(l2_set),
        n_tech=len(tech_set),
        payload=json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} · {total:,} products · {len(l1_set)} L1 · {len(l2_set)} L2 · {len(tech_set)} tech · {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
