"""Aggregate company_master + company_geo + company_capital_structure into the
v3 Companies page feed.

Output: web/v3/v3-companies.js exposing window.V3_COMPANIES_DATA with:

  summary               — totals (companies, listed, private, corporate families)
  companies             — full list with table fields (filterable / sortable)
  business_role_mix     — Manufacturer / Brand Owner / R&D-OEM / Biotech / ...
  ownership_mix         — Public / Private / Subsidiary
  region_mix            — Asia-Pacific / Europe / North America / ...
  corporate_families    — ultimate_parent groups with > 1 subsidiary (M&A tree)
  country_x_ownership   — top countries × ownership type matrix
  top_companies         — top 12 by product count for the leaderboard card
  findings              — 3 editorial findings derived from aggregates
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-companies.js"


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
          cm.company_id, cm.canonical_name, cm.aliases,
          cm.hq_country, cm.region, cm.location_full,
          cm.ownership, cm.business_role, cm.status,
          cm.parent_company, cm.ultimate_parent,
          cm.acquisition_status,
          cm.stock_code, cm.exchange, cm.ticker_symbol, cm.listing_country,
          cm.isin, cm.product_count, cm.brand_count, cm.primary_track,
          cm.priority_rank,
          cg.lat, cg.lon, cg.city,
          c.fda_products, c.nmpa_products
        FROM company_master cm
        LEFT JOIN company_geo cg ON cg.company_id = cm.company_id
        LEFT JOIN companies c ON c.company = cm.canonical_name
        """
    ).fetchall()
    conn.close()

    companies = []
    for r in rows:
        comp = {
            "company_id": r["company_id"],
            "name": clean(r["canonical_name"]),
            "country": clean(r["hq_country"]),
            "region": clean(r["region"]),
            "city": clean(r["city"]),
            "ownership": clean(r["ownership"]),
            "business_role": clean(r["business_role"]) or "Manufacturer",
            "primary_track": clean(r["primary_track"]),
            "parent": clean(r["parent_company"]),
            "ultimate_parent": clean(r["ultimate_parent"]),
            "stock_code": clean(r["stock_code"]),
            "exchange": clean(r["exchange"]),
            "ticker": clean(r["ticker_symbol"]),
            "products": r["product_count"] or 0,
            "brands": r["brand_count"] or 0,
            "fda": int(clean(r["fda_products"]) or 0),
            "rank": r["priority_rank"] or 999,
        }
        companies.append(comp)

    companies.sort(key=lambda c: (-c["products"], c["rank"]))

    # ---- Summary --------------------------------------------------------
    total = len(companies)
    listed_n = sum(1 for c in companies if c["ownership"] == "Public")
    private_n = sum(1 for c in companies if c["ownership"] == "Private")
    subsidiary_n = sum(1 for c in companies if c["ownership"] == "Subsidiary")

    # ---- Business role mix ---------------------------------------------
    business_role_mix = Counter(c["business_role"] for c in companies).most_common()

    # ---- Ownership mix --------------------------------------------------
    ownership_mix = Counter(c["ownership"] or "Unknown" for c in companies).most_common()

    # ---- Region mix -----------------------------------------------------
    region_mix = Counter(c["region"] or "Unknown" for c in companies).most_common()

    # ---- Corporate families (ultimate_parent with > 1 subsidiary) ------
    parent_groups = defaultdict(list)
    for c in companies:
        up = c["ultimate_parent"]
        if up and up != c["name"]:  # exclude self-parent (independent firms)
            parent_groups[up].append(c)
    corporate_families = []
    for parent, kids in sorted(parent_groups.items(), key=lambda kv: -len(kv[1])):
        if len(kids) < 2:
            continue
        total_products = sum(k["products"] for k in kids)
        total_brands = sum(k["brands"] for k in kids)
        corporate_families.append({
            "parent": parent,
            "subsidiaries": [
                {
                    "name": k["name"],
                    "country": k["country"],
                    "primary_track": k["primary_track"],
                    "products": k["products"],
                    "ownership": k["ownership"],
                }
                for k in kids
            ],
            "n_subsidiaries": len(kids),
            "total_products": total_products,
            "total_brands": total_brands,
        })

    # ---- Country × Ownership matrix (top 12 countries) ----------------
    country_total = Counter(c["country"] or "Unknown" for c in companies)
    top_countries = [c for c, _ in country_total.most_common(12)]
    co_matrix_rows = []
    for country in top_countries:
        bucket = [c for c in companies if c["country"] == country]
        co_matrix_rows.append({
            "country": country,
            "region": next((c["region"] for c in bucket if c["region"]), ""),
            "total": len(bucket),
            "public":     sum(1 for c in bucket if c["ownership"] == "Public"),
            "private":    sum(1 for c in bucket if c["ownership"] == "Private"),
            "subsidiary": sum(1 for c in bucket if c["ownership"] == "Subsidiary"),
            "fda":        sum(1 for c in bucket if c["fda"] > 0),
        })

    # ---- Top by products (leaderboard) ---------------------------------
    top_companies = companies[:12]

    # ---- Findings (derived from aggregates) ----------------------------
    manu_pct = round(100 * business_role_mix[0][1] / total, 1) if business_role_mix else 0
    public_pct = round(100 * listed_n / total, 1)
    family_companies = sum(f["n_subsidiaries"] for f in corporate_families)

    findings = [
        {
            "stamp": "Finding · 01",
            "lead": "<em>{0}%</em> 的上游是制造型，不是品牌型。".format(int(manu_pct)),
            "num_pair": {"num": "{0}%".format(int(manu_pct)), "unit": "Manufacturer"},
            "body": "全球医美上游 <em>{m}</em> 家公司里 <em>{n}</em> 家是 Manufacturer (生产型) — 远超 Brand Owner <em>{b}</em>、R&D-OEM <em>{r}</em>、Biotech <em>{bi}</em>。这是个「生产驱动」的行业，新进入者主要靠 OEM 代工切入，而不是从品牌切入。".format(
                m=total,
                n=business_role_mix[0][1] if business_role_mix else 0,
                b=next((n for r, n in business_role_mix if r == "Brand Owner"), 0),
                r=next((n for r, n in business_role_mix if r == "R&D/OEM"), 0),
                bi=next((n for r, n in business_role_mix if r == "Biotech"), 0),
            ),
            "wash": "w-rose-deep",
        },
        {
            "stamp": "Finding · 02",
            "lead": "上市率仅 <em>{0}%</em> — 行业整合空间巨大。".format(public_pct),
            "num_pair": {"num": "{0}%".format(public_pct), "unit": "public listed"},
            "body": "<em>{pub}</em> / <em>{tot}</em> 家公司公开上市。其余 <em>{pri}</em> 私营 + <em>{sub}</em> 子公司构成「暗股池」。低上市率意味着估值不透明、并购窗口长 — 但也意味着资本敏感度低，行业波动小。".format(
                pub=listed_n, tot=total, pri=private_n, sub=subsidiary_n,
            ),
            "wash": "w-apricot",
        },
        {
            "stamp": "Finding · 03",
            "lead": "实质性集团整合罕见。",
            "num_pair": {"num": len(corporate_families), "unit": "corporate families"},
            "body": "只有 <em>{n}</em> 个 ultimate_parent 拥有 ≥2 家子公司（El.En. 4 / Galderma 2 / Cynosure 2 / Apyx 2），合计仅 <em>{c}</em> 家子公司。行业整合处于早期 — AbbVie/Allergan、J&J/Mentor 这类经典并购在底库里没有形成大规模 group 结构。下一轮 backfill 应优先补全 acquisition_status。".format(
                n=len(corporate_families), c=family_companies,
            ),
            "wash": "w-plum",
        },
    ]

    payload = {
        "summary": {
            "total": total,
            "listed": listed_n,
            "private": private_n,
            "subsidiary": subsidiary_n,
            "manufacturer": next((n for r, n in business_role_mix if r == "Manufacturer"), 0),
            "brand_owner": next((n for r, n in business_role_mix if r == "Brand Owner"), 0),
            "r_and_d": next((n for r, n in business_role_mix if r == "R&D/OEM"), 0),
            "biotech": next((n for r, n in business_role_mix if r == "Biotech"), 0),
            "corporate_families": len(corporate_families),
            "top_company": companies[0]["name"] if companies else "",
            "top_company_products": companies[0]["products"] if companies else 0,
        },
        "companies": companies,
        "business_role_mix": [{"role": r, "n": n} for r, n in business_role_mix],
        "ownership_mix": [{"name": o, "n": n} for o, n in ownership_mix],
        "region_mix": [{"name": rg, "n": n} for rg, n in region_mix],
        "corporate_families": corporate_families,
        "country_x_ownership": co_matrix_rows,
        "top_companies": top_companies,
        "findings": findings,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "// auto-generated by scripts/_v3_build_companies.py — do not hand-edit\n"
        f"// {total} companies / {listed_n} listed / {len(corporate_families)} corporate families\n"
        f"window.V3_COMPANIES_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} · {total} companies · {listed_n} listed · {len(corporate_families)} families · {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
