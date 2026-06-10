"""Aggregate official_indication_evidence into the v3 Indications page feed.

Output: web/v3/v3-indications.js → window.V3_INDICATIONS_DATA with:

  summary             — totals (evidence, products, companies, buckets)
  indications         — list per bucket: n_records / n_products / n_companies /
                        top_brands / top_l1 / top_tech / top_countries
  ind_x_tech          — indication × technology_path_l1 cross-tab
  ind_x_l1            — indication × commercial L1 (inverted from tracks page)
  ind_x_country       — indication × top countries
  top_brands_per_ind  — top brands serving each indication
  findings            — derived editorial findings
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-indications.js"
NON_CLINICAL_BUCKETS = {"待补具体适应症", "其他官方适应症"}


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
          oie.id, oie.product_id, oie.company, oie.brand, oie.product,
          oie.country, oie.regulator, oie.pathway, oie.year, oie.buckets,
          pm.commercial_path_l1, pm.commercial_path_l2,
          pm.technology_path_l1, pm.technology_path_l2,
          pm.material_or_energy_source
        FROM official_indication_evidence oie
        LEFT JOIN product_master pm ON pm.product_id = oie.product_id
        WHERE oie.buckets IS NOT NULL AND oie.buckets != ''
        """
    ).fetchall()
    dashboard_product_total = conn.execute("SELECT COUNT(*) FROM product_master").fetchone()[0] or 1
    conn.close()

    # Real regulator allowlist — drop Codex placeholder rows like
    # "Official product/IFU/source text" or "厂家 IFU" so they don't pollute
    # the new Indication × Regulator heatmap.
    REAL_REGULATORS = {
        "FDA", "NMPA", "CE", "CE/MDR", "MDR", "EU-MDR",
        "MFDS", "KFDA", "PMDA", "TGA", "MHRA", "ANVISA",
        "Health Canada", "HSA", "INVIMA", "COFEPRIS",
        "Swissmedic", "ROSZDRAV", "Saudi FDA", "SFDA",
    }
    def normalise_regulator(raw: str) -> str:
        rw = clean(raw)
        if not rw:
            return ""
        if rw in REAL_REGULATORS:
            return rw
        # "FDA 510(k)" / "CE-MDR" / "MFDS 의료기기" → take first uppercase token
        first = rw.split()[0]
        if first.isupper() and 2 <= len(first) <= 6:
            return first
        return ""  # not a real regulator → exclude from ind × regulator matrix

    # Explode comma-separated buckets so each (record × bucket) becomes one row
    expanded = []
    for r in rows:
        for bucket in [b.strip() for b in clean(r["buckets"]).split(",") if b.strip()]:
            expanded.append({
                "id": r["id"],
                "product_id": r["product_id"],
                "company": clean(r["company"]),
                "brand": clean(r["brand"]),
                "product": clean(r["product"]),
                "country": clean(r["country"]),
                "regulator": clean(r["regulator"]),
                "regulator_norm": normalise_regulator(r["regulator"]),
                "year": clean(r["year"]),
                "indication": bucket,
                "l1": clean(r["commercial_path_l1"]) or "未知",
                "l2": clean(r["commercial_path_l2"]),
                "tech_l1": clean(r["technology_path_l1"]) or clean(r["material_or_energy_source"]),
            })

    total_records = len(rows)
    total_buckets = len({e["indication"] for e in expanded})
    total_products = len({r["product_id"] for r in rows if r["product_id"]})
    total_companies = len({clean(r["company"]) for r in rows if r["company"]})

    # ---- Per-indication aggregates ----
    indications = []
    ind_groups = defaultdict(list)
    for e in expanded:
        ind_groups[e["indication"]].append(e)

    for ind, items in sorted(
        ind_groups.items(),
        key=lambda kv: (kv[0] in NON_CLINICAL_BUCKETS, -len(kv[1]), kv[0]),
    ):
        brands = Counter(e["brand"] for e in items if e["brand"]).most_common(5)
        techs = Counter(e["tech_l1"] for e in items if e["tech_l1"]).most_common(5)
        l1s = Counter(e["l1"] for e in items if e["l1"] and e["l1"] != "未知").most_common(5)
        countries = Counter(e["country"] for e in items if e["country"]).most_common(5)
        products = {e["product_id"] for e in items if e["product_id"]}
        companies = {e["company"] for e in items if e["company"]}

        indications.append({
            "indication": ind,
            "n_records": len(items),
            "n_products": len(products),
            "n_companies": len(companies),
            "n_techs": len({e["tech_l1"] for e in items if e["tech_l1"]}),
            "top_brands": [{"name": b, "n": n} for b, n in brands],
            "top_techs": [{"name": t, "n": n} for t, n in techs],
            "top_l1": [{"l1": l, "n": n} for l, n in l1s],
            "top_countries": [{"country": c, "n": n} for c, n in countries],
            "is_clinical_bucket": ind not in NON_CLINICAL_BUCKETS,
        })

    # ---- Indication × Tech matrix (top 8 indications × top 6 techs) ----
    top_inds_for_matrix = [i["indication"] for i in indications[:8]]
    all_techs = Counter(e["tech_l1"] for e in expanded if e["tech_l1"]).most_common(6)
    top_techs_global = [t for t, _ in all_techs]
    ind_x_tech_rows = []
    for ind in top_inds_for_matrix:
        ind_items = ind_groups[ind]
        tech_counts = Counter(e["tech_l1"] for e in ind_items if e["tech_l1"])
        ind_x_tech_rows.append({
            "indication": ind,
            "values": {t: tech_counts.get(t, 0) for t in top_techs_global},
            "total": sum(tech_counts.values()),
        })

    # ---- Indication × L1 cross-tab ----
    all_l1s = Counter(e["l1"] for e in expanded if e["l1"] and e["l1"] != "未知").most_common(6)
    top_l1s_global = [l for l, _ in all_l1s]
    ind_x_l1_rows = []
    for ind in top_inds_for_matrix:
        ind_items = ind_groups[ind]
        l1_counts = Counter(e["l1"] for e in ind_items if e["l1"] and e["l1"] != "未知")
        ind_x_l1_rows.append({
            "indication": ind,
            "values": {l: l1_counts.get(l, 0) for l in top_l1s_global},
            "total": sum(l1_counts.values()),
        })

    # ---- Indication × Regulator cross-tab ----
    # Top regulators across the whole evidence corpus (after normalisation,
    # which already drops placeholder rows). Show up to top 7 columns so the
    # row still fits a 1200-1400px container without horizontal scroll.
    all_regs = Counter(e["regulator_norm"] for e in expanded if e["regulator_norm"]).most_common(7)
    top_regs_global = [r for r, _ in all_regs]
    # Always show all 15 buckets here (not just top 8) so the user can see
    # 监管覆盖盲区 — long-tail indications where no regulator has any record.
    bucket_order = [i["indication"] for i in indications]
    ind_x_regulator_rows = []
    for ind in bucket_order:
        ind_items = ind_groups[ind]
        reg_counts = Counter(e["regulator_norm"] for e in ind_items if e["regulator_norm"])
        total = sum(reg_counts.values())
        if total == 0:
            continue  # skip buckets with zero real-regulator evidence
        ind_x_regulator_rows.append({
            "indication": ind,
            "values": {r: reg_counts.get(r, 0) for r in top_regs_global},
            "total": total,
        })

    # ---- Findings ----
    clinical_indications = [i for i in indications if i["is_clinical_bucket"]]
    unresolved_records = sum(i["n_records"] for i in indications if not i["is_clinical_bucket"])
    most_served = clinical_indications[0] if clinical_indications else (indications[0] if indications else None)
    multi_tech_inds = [i for i in clinical_indications if i["n_techs"] >= 3]
    mono_tech_inds = [i for i in clinical_indications if i["n_techs"] == 1 and i["n_records"] >= 3]

    findings = [
        {
            "stamp": "Finding · 01",
            "lead": "<em>{0}</em> 是头部适应症 — <em>{1}</em> 条官方证据。".format(
                most_served["indication"] if most_served else "—",
                most_served["n_records"] if most_served else 0,
            ),
            "num_pair": {
                "num": most_served["n_records"] if most_served else 0,
                "unit": "official evidence",
            },
            "body": "「<em>{ind}</em>」由 <em>{p}</em> 款产品 × <em>{c}</em> 家公司 × <em>{t}</em> 种技术覆盖。头部品牌 {brands}。这是医美最被「数据化承诺」的一个适应症。".format(
                ind=most_served["indication"] if most_served else "—",
                p=most_served["n_products"] if most_served else 0,
                c=most_served["n_companies"] if most_served else 0,
                t=most_served["n_techs"] if most_served else 0,
                brands=" / ".join(b["name"] for b in most_served["top_brands"][:3]) if most_served else "—",
            ),
            "wash": "w-rose-deep",
        },
        {
            "stamp": "Finding · 02",
            "lead": "<em>{0}</em> 个适应症是「多技术竞争」格局。".format(len(multi_tech_inds)),
            "num_pair": {
                "num": len(multi_tech_inds),
                "unit": "multi-tech indications",
            },
            "body": "<em>{n}</em> 个适应症同时被 ≥3 种技术服务（HA / PLLA / PCL / Botox / CaHA / Polynucleotide 等）— 患者有真选择，品牌有真竞争。这些是最 commodity 的赛道，价格战已经发生。".format(
                n=len(multi_tech_inds),
            ),
            "wash": "w-apricot",
        },
        {
            "stamp": "Finding · 03",
            "lead": "数据稀疏 — 只覆盖 <em>{0}</em> 款产品 / <em>{1}</em> 家公司。".format(total_products, total_companies),
            "num_pair": {
                "num": "{0}%".format(round(100 * total_products / dashboard_product_total, 1)),
                "unit": "product coverage",
            },
            "body": "<em>{p}</em> / {total} 款产品有官方适应症证据 ({pct}% 覆盖率)。其中 <em>{unresolved}</em> 条已识别为待补具体正文，不再混入临床适应症排行。下一轮 official_indication_evidence 数据采集应优先补回 EBD 大厂的 510(k) clearance 适应症描述。".format(
                p=total_products,
                total=dashboard_product_total,
                pct=round(100 * total_products / dashboard_product_total, 1),
                unresolved=unresolved_records,
            ),
            "wash": "w-plum",
        },
    ]

    payload = {
        "summary": {
            "total_records": total_records,
            "total_buckets": total_buckets,
            "total_products": total_products,
            "total_companies": total_companies,
            "top_indication": most_served["indication"] if most_served else "",
            "top_indication_n": most_served["n_records"] if most_served else 0,
            "multi_tech_count": len(multi_tech_inds),
            "coverage_pct": round(100 * total_products / dashboard_product_total, 1),
            "dashboard_product_total": dashboard_product_total,
            "unresolved_records": unresolved_records,
        },
        "indications": indications,
        "ind_x_tech": {
            "columns": top_techs_global,
            "rows": ind_x_tech_rows,
        },
        "ind_x_l1": {
            "columns": top_l1s_global,
            "rows": ind_x_l1_rows,
        },
        "ind_x_regulator": {
            "columns": top_regs_global,
            "rows": ind_x_regulator_rows,
        },
        "findings": findings,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "// auto-generated by scripts/_v3_build_indications.py — do not hand-edit\n"
        f"// {total_records} records / {total_buckets} buckets / {total_products} products\n"
        f"window.V3_INDICATIONS_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} · {total_records} records · {total_buckets} buckets · {total_products} products · {total_companies} companies · {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
