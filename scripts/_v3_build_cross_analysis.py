"""Generate web/v3/v3-cross-analysis.js — the dataset that powers the
3-section "Cross Analysis" page.

Lenses
------
1. country × track × ownership (3D) + FDA hits as a 4th dim badge.
   Top 12 countries (by company count) × all 10 L1 tracks. Each cell:
     - companies (n)
     - products (n)
     - public_n / private_n / sub_n (ownership breakdown)
     - fda_hits (4th dim)
     - company_ids (drill-down)

2. company × regulator × year (3D) — regulatory rhythm of top 20 producers
   by total registration evidence count.
   For each (company, regulator, year) cell:
     - count
     - drill-down: registration_evidence row ids

3. indication_bucket × regulator × region (3D) — sparse but informative
   For each (bucket, regulator, region) cell:
     - count of products
     - drill-down: product_ids

The script writes ~80–200 KB of JSON so the page can render without further
fetches. All cell color logic & rendering happens in the HTML/JS.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-cross-analysis.js"

TOP_COUNTRY_LIMIT = 12
TOP_COMPANY_LIMIT = 20
TOP_INDICATION_LIMIT = 12

TRACKS = ["EBD", "Injectables", "Skincare", "Regenerative", "Implants",
          "Consumables", "Diagnostics", "Surgical", "Pharma", "Services"]


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"db not found: {DB}")
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # ============ Load companies into memory once ============
    companies = list(conn.execute(
        "SELECT * FROM companies"
    ))
    co_by_company = {clean(c["company"]): dict(c) for c in companies}

    # We also need company_id mapping (from product_master.company_id)
    co_id_map_rows = list(conn.execute(
        "SELECT DISTINCT company, company_id FROM product_master "
        "WHERE company_id IS NOT NULL AND company_id != ''"
    ))
    name_to_cid = {clean(r["company"]): clean(r["company_id"]) for r in co_id_map_rows}

    # ============ LENS 1 · country × track × ownership × FDA ============
    # Aggregate
    cube1 = defaultdict(lambda: {
        "companies": 0, "products": 0, "fda_hits": 0,
        "public": 0, "private": 0, "subsidiary": 0,
        "company_ids": [],
    })
    country_totals = defaultdict(int)
    for c in companies:
        country = clean(c["hq_country"])
        track = clean(c["primary_track"])
        ownership = clean(c["ownership"])
        if not country or not track:
            continue
        if track not in TRACKS:
            continue
        key = (country, track)
        cube1[key]["companies"] += 1
        cube1[key]["products"] += int(c["fda_products"] or 0)  # placeholder; will overwrite below
        # Ownership split
        own = ownership.lower()
        if "public" in own:
            cube1[key]["public"] += 1
        elif "sub" in own:
            cube1[key]["subsidiary"] += 1
        else:
            cube1[key]["private"] += 1
        # FDA hits (use fda_products > 0)
        if int(c["fda_products"] or 0) > 0:
            cube1[key]["fda_hits"] += 1
        cube1[key]["company_ids"].append(name_to_cid.get(clean(c["company"]), ""))
        country_totals[country] += 1

    # Compute real product counts per (country, track) from product_master
    prod_counts = defaultdict(int)
    for row in conn.execute(
        """
        SELECT c.hq_country AS country, p.commercial_path_l1 AS track,
               COUNT(*) AS n
        FROM product_master p
        JOIN companies c ON c.company = p.company
        WHERE c.hq_country IS NOT NULL AND p.commercial_path_l1 IS NOT NULL
        GROUP BY 1,2
        """
    ):
        prod_counts[(clean(row["country"]), clean(row["track"]))] = int(row["n"])

    for key, cell in cube1.items():
        cell["products"] = prod_counts.get(key, 0)

    top_countries = sorted(country_totals.items(), key=lambda x: -x[1])[:TOP_COUNTRY_LIMIT]
    top_country_names = [c[0] for c in top_countries]

    # Country meta — region for display
    country_meta = {}
    for c in companies:
        country = clean(c["hq_country"])
        if country in top_country_names and country not in country_meta:
            country_meta[country] = {
                "region": clean(c["region"]),
                "total_companies": country_totals[country],
            }

    lens1_rows = []
    for country in top_country_names:
        row = {
            "country": country,
            "region": country_meta.get(country, {}).get("region", ""),
            "total_companies": country_totals[country],
            "cells": [],
        }
        for track in TRACKS:
            cell = cube1.get((country, track))
            if cell is None:
                row["cells"].append({
                    "track": track, "companies": 0, "products": 0,
                    "public": 0, "private": 0, "subsidiary": 0,
                    "fda_hits": 0, "company_ids": [],
                })
            else:
                row["cells"].append({
                    "track": track,
                    "companies": cell["companies"],
                    "products": cell["products"],
                    "public": cell["public"],
                    "private": cell["private"],
                    "subsidiary": cell["subsidiary"],
                    "fda_hits": cell["fda_hits"],
                    "company_ids": [cid for cid in cell["company_ids"] if cid],
                })
        lens1_rows.append(row)

    # ============ LENS 2 · company × regulator × year ============
    # Normalize regulators into 4 buckets: FDA, CE/EU, NMPA, KFDA, Other
    def norm_reg(r: str) -> str:
        r = (r or "").lower()
        if "fda" in r and "kfda" not in r:
            return "FDA"
        if "ce" in r or "eudamed" in r or "european" in r or "notified body" in r:
            return "CE/EU"
        if "nmpa" in r or "cfda" in r:
            return "NMPA"
        if "kfda" in r or "korea" in r or "mfds" in r:
            return "KFDA"
        return "Other"

    YEARS = [str(y) for y in range(2017, 2027)]  # 2017..2026

    co_regyear = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    co_total = defaultdict(int)
    for row in conn.execute(
        """
        SELECT id, company, company_id, regulator, regulatory_pathway,
               approval_date, brand
        FROM registration_evidence
        WHERE company IS NOT NULL AND company != ''
        """
    ):
        co = clean(row["company"])
        reg = norm_reg(row["regulator"])
        date = clean(row["approval_date"])
        year = date[:4] if date and date[:4].isdigit() else "Unknown"
        co_regyear[co][reg][year].append({
            "id": row["id"],
            "company": co,
            "brand": clean(row["brand"]),
            "regulator": clean(row["regulator"]),
            "pathway": clean(row["regulatory_pathway"]),
            "approval_date": date,
            "company_id": clean(row["company_id"]),
        })
        co_total[co] += 1

    top_companies_reg = sorted(co_total.items(), key=lambda x: -x[1])[:TOP_COMPANY_LIMIT]
    lens2_rows = []
    for co_name, total in top_companies_reg:
        cid = name_to_cid.get(co_name, "")
        cube_meta = co_by_company.get(co_name, {})
        cells = []
        for yr in YEARS + ["Unknown"]:
            year_cell = {"year": yr, "fda": 0, "ce_eu": 0, "nmpa": 0, "kfda": 0, "other": 0, "total": 0,
                         "evidence_ids": []}
            for reg in ["FDA", "CE/EU", "NMPA", "KFDA", "Other"]:
                hits = co_regyear[co_name][reg][yr]
                n = len(hits)
                if reg == "FDA":
                    year_cell["fda"] = n
                elif reg == "CE/EU":
                    year_cell["ce_eu"] = n
                elif reg == "NMPA":
                    year_cell["nmpa"] = n
                elif reg == "KFDA":
                    year_cell["kfda"] = n
                else:
                    year_cell["other"] = n
                year_cell["total"] += n
                year_cell["evidence_ids"].extend([h["id"] for h in hits])
            cells.append(year_cell)
        lens2_rows.append({
            "company": co_name,
            "company_id": cid,
            "country": clean(cube_meta.get("hq_country", "")),
            "primary_track": clean(cube_meta.get("primary_track", "")),
            "total": total,
            "cells": cells,
        })

    # ============ LENS 3 · indication bucket × regulator × region ============
    # The buckets field is a comma-separated Chinese string. Split & normalize.
    region_for_country = {}
    for r in conn.execute("SELECT DISTINCT hq_country, region FROM companies"):
        region_for_country[clean(r["hq_country"])] = clean(r["region"])

    bucket_reg_region = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    bucket_totals = defaultdict(int)

    def parse_buckets(s: str) -> list[str]:
        if not s:
            return []
        # split by comma + Chinese comma, dedup, strip
        parts = [p.strip() for p in s.replace("，", ",").split(",")]
        return [p for p in parts if p]

    for row in conn.execute(
        """
        SELECT id, product_id, company, brand, product, country,
               regulator, buckets
        FROM official_indication_evidence
        WHERE buckets IS NOT NULL AND buckets != ''
        """
    ):
        buckets = parse_buckets(clean(row["buckets"]))
        country = clean(row["country"])
        # Try to map country → region
        region = ""
        for cn, rg in region_for_country.items():
            if cn and country and (cn in country or country in cn):
                region = rg
                break
        if not region:
            # rough fallback based on common ones
            cl = country.lower()
            if "us" in cl or "america" in cl:
                region = "N. America"
            elif "eu" in cl or "europe" in cl:
                region = "Europe"
            elif "asia" in cl or "china" in cl or "korea" in cl or "japan" in cl:
                region = "Asia-Pacific"
            else:
                region = "Other"
        reg = norm_reg(row["regulator"])

        for b in buckets:
            bucket_reg_region[b][reg][region].append({
                "id": row["id"],
                "product_id": clean(row["product_id"]),
                "company": clean(row["company"]),
                "brand": clean(row["brand"]),
                "product": clean(row["product"]),
                "country": country,
                "company_id": name_to_cid.get(clean(row["company"]), ""),
            })
            bucket_totals[b] += 1

    top_buckets = sorted(bucket_totals.items(), key=lambda x: -x[1])[:TOP_INDICATION_LIMIT]
    REGULATORS_L3 = ["FDA", "CE/EU", "NMPA", "KFDA", "Other"]
    REGIONS_L3 = ["N. America", "Europe", "Asia-Pacific", "Middle East", "Other"]

    lens3_rows = []
    for bucket, total in top_buckets:
        row = {"bucket": bucket, "total": total, "cells": []}
        for reg in REGULATORS_L3:
            for region in REGIONS_L3:
                hits = bucket_reg_region[bucket][reg][region]
                if not hits:
                    continue
                row["cells"].append({
                    "regulator": reg,
                    "region": region,
                    "count": len(hits),
                    "products": hits[:25],  # cap drill-down size per cell
                })
        lens3_rows.append(row)

    # ============ Summary ============
    summary = {
        "lens1_cells": sum(1 for r in lens1_rows for c in r["cells"] if c["companies"] > 0),
        "lens1_countries": len(lens1_rows),
        "lens1_tracks": len(TRACKS),
        "lens2_companies": len(lens2_rows),
        "lens2_years": len(YEARS),
        "lens2_total_regs": sum(co_total.values()),
        "lens3_buckets": len(lens3_rows),
        "lens3_evidence": sum(bucket_totals.values()),
    }

    payload = {
        "summary": summary,
        "lens1": {
            "countries": [r["country"] for r in lens1_rows],
            "tracks": TRACKS,
            "rows": lens1_rows,
        },
        "lens2": {
            "years": YEARS + ["Unknown"],
            "regulators": ["FDA", "CE/EU", "NMPA", "KFDA", "Other"],
            "rows": lens2_rows,
        },
        "lens3": {
            "regulators": REGULATORS_L3,
            "regions": REGIONS_L3,
            "rows": lens3_rows,
        },
    }

    conn.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "// auto-generated by scripts/_v3_build_cross_analysis.py — do not hand-edit\n"
        f"// summary: {json.dumps(summary, ensure_ascii=False)}\n"
        f"window.V3_CROSS_ANALYSIS_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} · {OUT.stat().st_size/1024:.1f} KB")
    print(f"  lens1: {summary['lens1_countries']} countries × {summary['lens1_tracks']} tracks, {summary['lens1_cells']} non-empty cells")
    print(f"  lens2: {summary['lens2_companies']} companies × {summary['lens2_years']}+1 years, {summary['lens2_total_regs']} total registrations")
    print(f"  lens3: {summary['lens3_buckets']} buckets, {summary['lens3_evidence']} evidence rows")


if __name__ == "__main__":
    main()
