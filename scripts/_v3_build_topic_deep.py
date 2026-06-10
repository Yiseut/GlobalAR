"""Generate web/v3/v3-topic-deep.js — per-L1 deep-dive metrics for topic.html.

For each L1 commercial track we compute:

  concentration      CR5, CR10, HHI from per-company product counts in this L1
  value_chain        business_role mix (Manufacturer / Brand Owner / R&D-OEM / Biotech / etc.)
  lifecycle          per L2: x = recent-3yr momentum %, y = companies, size = products
  indication_heatmap top indication buckets × {FDA, CE/EU, NMPA, KFDA, Other}
  recent_entrants    companies with first L1 approval in last 24 months
  country_l2_matrix  top 8 countries × top L2 (sub-track penetration)
  top_companies      top 12 by product count, with company_id for drawer cascade

The script writes ~50 KB.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-topic-deep.js"

L1_ORDER = ["EBD", "Injectables", "Skincare", "Regenerative", "Consumables",
            "Implants", "Diagnostics", "Surgical", "Pharma"]

REG_BUCKET = {
    "FDA": "FDA",
    "EUDAMED / European Commission": "CE/EU",
    "Notified Body / Manufacturer": "CE/EU",
    "CE/MDR": "CE/EU",
    "NMPA": "NMPA",
}
REG_ORDER = ["FDA", "CE/EU", "NMPA", "KFDA", "Other"]


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def norm_reg(r: str) -> str:
    if r in REG_BUCKET:
        return REG_BUCKET[r]
    rl = (r or "").lower()
    if "fda" in rl and "kfda" not in rl:
        return "FDA"
    if "ce" in rl or "eudamed" in rl or "european" in rl or "notified body" in rl:
        return "CE/EU"
    if "nmpa" in rl or "cfda" in rl:
        return "NMPA"
    if "kfda" in rl or "korea" in rl or "mfds" in rl:
        return "KFDA"
    if not rl:
        return "Other"
    return "Other"


def parse_buckets(s: str) -> list[str]:
    if not s:
        return []
    parts = [p.strip() for p in s.replace("，", ",").split(",")]
    return [p for p in parts if p]


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # ===== Load everything we need into memory =====
    products = list(conn.execute("""
        SELECT pm.product_id, pm.company_id, pm.company,
               pm.commercial_path_l1 AS l1, pm.commercial_path_l2 AS l2,
               c.hq_country AS country, c.region, c.ownership, c.business_role
        FROM product_master pm
        LEFT JOIN companies c ON c.company = pm.company
        WHERE pm.commercial_path_l1 IS NOT NULL AND pm.commercial_path_l1 != ''
    """))

    reg_rows = list(conn.execute("""
        SELECT product_id, company_id, company, regulator, approval_date
        FROM registration_evidence
        WHERE product_id IS NOT NULL
    """))

    ind_rows = list(conn.execute("""
        SELECT product_id, regulator, buckets
        FROM official_indication_evidence
        WHERE buckets IS NOT NULL AND buckets != ''
    """))

    companies_rows = list(conn.execute("SELECT * FROM companies"))
    co_by_name = {clean(c["company"]): dict(c) for c in companies_rows}
    name_to_cid = {clean(p["company"]): clean(p["company_id"]) for p in products
                   if clean(p["company"]) and clean(p["company_id"])}

    conn.close()

    # product_id → L1 / L2 lookup
    pid_to_l1l2 = {clean(p["product_id"]): (clean(p["l1"]), clean(p["l2"]))
                   for p in products if clean(p["product_id"])}
    pid_to_company = {clean(p["product_id"]): {
        "company": clean(p["company"]),
        "company_id": clean(p["company_id"]),
        "country": clean(p["country"]),
        "region": clean(p["region"]),
    } for p in products if clean(p["product_id"])}

    # Approval years per (company, L1)
    company_l1_first_approval = defaultdict(lambda: defaultdict(list))
    for r in reg_rows:
        pid = clean(r["product_id"])
        l1l2 = pid_to_l1l2.get(pid)
        if not l1l2:
            continue
        l1, _l2 = l1l2
        date = clean(r["approval_date"])
        year = date[:4] if date and date[:4].isdigit() else None
        if year:
            try:
                company_l1_first_approval[clean(r["company"])][l1].append(int(year))
            except ValueError:
                pass

    # ===== Loop over L1 tracks =====
    per_l1 = {}
    today = datetime(2026, 5, 26)  # locked snapshot date
    cutoff_24m = today - timedelta(days=730)

    for L1 in L1_ORDER:
        l1_products = [p for p in products if clean(p["l1"]) == L1]
        if not l1_products:
            continue

        # ---- 1. CONCENTRATION ----
        co_counts = Counter(clean(p["company"]) for p in l1_products if clean(p["company"]))
        total_prod = sum(co_counts.values())
        sorted_co = co_counts.most_common()
        cr5 = sum(n for _, n in sorted_co[:5]) / total_prod * 100 if total_prod else 0
        cr10 = sum(n for _, n in sorted_co[:10]) / total_prod * 100 if total_prod else 0
        # HHI normalized 0-10000
        hhi = sum((n / total_prod * 100) ** 2 for _, n in sorted_co) if total_prod else 0
        # Show top 10 companies' share for bar chart
        top10 = [
            {
                "company": co,
                "products": n,
                "share_pct": round(n / total_prod * 100, 1) if total_prod else 0,
                "company_id": name_to_cid.get(co, ""),
                "country": clean(co_by_name.get(co, {}).get("hq_country", "")),
                "ownership": clean(co_by_name.get(co, {}).get("ownership", "")),
            }
            for co, n in sorted_co[:10]
        ]
        concentration = {
            "n_companies": len(co_counts),
            "n_products": total_prod,
            "cr5": round(cr5, 1),
            "cr10": round(cr10, 1),
            "hhi": round(hhi, 0),
            "hhi_class": (
                "fragmented" if hhi < 1500 else
                "moderate" if hhi < 2500 else
                "concentrated"
            ),
            "top10": top10,
        }

        # ---- 2. VALUE CHAIN ----
        # business_role from companies table, weighted by company (one per company), not product
        vc_counter = Counter()
        seen_companies = set()
        for p in l1_products:
            co = clean(p["company"])
            if co in seen_companies:
                continue
            seen_companies.add(co)
            role = clean(p["business_role"]) or "Unknown"
            vc_counter[role] += 1
        value_chain = [{"role": r, "n": n} for r, n in vc_counter.most_common()]

        # ---- 3. LIFECYCLE (per L2) ----
        # For each L2 in this L1: collect approval years; momentum = approvals in last 3y / total approvals
        l2_data = defaultdict(lambda: {"products": set(), "companies": set(),
                                       "company_ids": set(),
                                       "sample_brands": set(),
                                       "approvals": [], "approvals_recent_3y": 0})
        for p in l1_products:
            l2 = clean(p["l2"]) or "未分类"
            pid = clean(p["product_id"])
            l2_data[l2]["products"].add(pid)
            if clean(p["company"]):
                l2_data[l2]["companies"].add(clean(p["company"]))
            try:
                cid = clean(p["company_id"])
            except (IndexError, KeyError):
                cid = ""
            if cid:
                l2_data[l2]["company_ids"].add(cid)
            # brand isn't in the original query — leave sample_brands empty here
            # (tracks-side seg.sample_brands is the one rendered by topic.html)
        for r in reg_rows:
            pid = clean(r["product_id"])
            l1l2 = pid_to_l1l2.get(pid)
            if not l1l2 or l1l2[0] != L1:
                continue
            l2 = l1l2[1] or "未分类"
            date = clean(r["approval_date"])
            if not date or not date[:4].isdigit():
                continue
            year = int(date[:4])
            l2_data[l2]["approvals"].append(year)
            if year >= 2023:  # last 3 years
                l2_data[l2]["approvals_recent_3y"] += 1
        lifecycle = []
        for l2, d in l2_data.items():
            total_appr = len(d["approvals"])
            momentum = (d["approvals_recent_3y"] / total_appr * 100) if total_appr else None
            lifecycle.append({
                "l2": l2,
                "products": len(d["products"]),
                "companies": len(d["companies"]),
                "company_ids": sorted(d["company_ids"]),
                "sample_brands": sorted(d["sample_brands"])[:6],
                "approvals_total": total_appr,
                "approvals_recent_3y": d["approvals_recent_3y"],
                "momentum_pct": round(momentum, 1) if momentum is not None else None,
                "latest_year": max(d["approvals"]) if d["approvals"] else None,
            })
        lifecycle.sort(key=lambda x: -x["products"])

        # ---- 4. INDICATION × REGULATOR heatmap (within L1) ----
        bucket_reg = defaultdict(lambda: defaultdict(int))
        bucket_total = Counter()
        bucket_pids = defaultdict(lambda: defaultdict(list))
        for r in ind_rows:
            pid = clean(r["product_id"])
            l1l2 = pid_to_l1l2.get(pid)
            if not l1l2 or l1l2[0] != L1:
                continue
            reg = norm_reg(clean(r["regulator"]))
            for b in parse_buckets(clean(r["buckets"])):
                bucket_reg[b][reg] += 1
                bucket_total[b] += 1
                bucket_pids[b][reg].append(pid)
        # Top 8 buckets for this L1
        top_buckets = [b for b, _ in bucket_total.most_common(8)]
        indication_heatmap = {
            "buckets": top_buckets,
            "regulators": REG_ORDER,
            "rows": [
                {
                    "bucket": b,
                    "total": bucket_total[b],
                    "values": {reg: bucket_reg[b].get(reg, 0) for reg in REG_ORDER},
                    "product_ids": {
                        reg: [
                            {
                                "product_id": pid,
                                "company": pid_to_company.get(pid, {}).get("company", ""),
                                "company_id": pid_to_company.get(pid, {}).get("company_id", ""),
                                "country": pid_to_company.get(pid, {}).get("country", ""),
                            }
                            for pid in bucket_pids[b].get(reg, [])
                        ][:25]
                        for reg in REG_ORDER
                    },
                }
                for b in top_buckets
            ],
        }

        # ---- 5. RECENT ENTRANTS (last 24 months — 12m too sparse) ----
        # For each company in this L1, find their min approval year
        company_min_year = {}
        company_last_24m = defaultdict(list)
        for r in reg_rows:
            pid = clean(r["product_id"])
            l1l2 = pid_to_l1l2.get(pid)
            if not l1l2 or l1l2[0] != L1:
                continue
            co = clean(r["company"])
            date = clean(r["approval_date"])
            if not date or len(date) < 7:
                continue
            try:
                dt = datetime.strptime(date[:10], "%Y-%m-%d")
            except ValueError:
                try:
                    dt = datetime.strptime(date[:7], "%Y-%m")
                except ValueError:
                    continue
            if dt < cutoff_24m:
                # still track for "min year" calculation
                pass
            if dt >= cutoff_24m:
                company_last_24m[co].append({
                    "date": date[:10],
                    "product_id": pid,
                    "regulator": clean(r["regulator"]),
                })
            cur_min = company_min_year.get(co)
            if cur_min is None or dt < cur_min:
                company_min_year[co] = dt
        # Companies whose FIRST approval was in last 24 months = new entrants
        new_entrants = []
        for co, first_dt in company_min_year.items():
            if first_dt >= cutoff_24m:
                meta = co_by_name.get(co, {})
                new_entrants.append({
                    "company": co,
                    "company_id": name_to_cid.get(co, ""),
                    "country": clean(meta.get("hq_country", "")),
                    "first_approval": first_dt.strftime("%Y-%m-%d"),
                    "approvals_24m": len(company_last_24m.get(co, [])),
                    "ownership": clean(meta.get("ownership", "")),
                })
        new_entrants.sort(key=lambda x: x["first_approval"], reverse=True)
        # Also: companies with the most recent activity in this L1 (not necessarily new)
        recent_active = []
        for co, hits in sorted(company_last_24m.items(), key=lambda x: -len(x[1]))[:10]:
            meta = co_by_name.get(co, {})
            latest = max(h["date"] for h in hits)
            recent_active.append({
                "company": co,
                "company_id": name_to_cid.get(co, ""),
                "country": clean(meta.get("hq_country", "")),
                "approvals_24m": len(hits),
                "latest_date": latest,
                "ownership": clean(meta.get("ownership", "")),
                "is_new_entrant": company_min_year.get(co, datetime(1900, 1, 1)) >= cutoff_24m,
            })

        # ---- 6. COUNTRY × L2 cross-matrix ----
        cl_counter = defaultdict(int)
        cl_company_ids = defaultdict(set)
        for p in l1_products:
            country = clean(p["country"])
            l2 = clean(p["l2"]) or "未分类"
            if not country:
                continue
            cl_counter[(country, l2)] += 1
            cl_company_ids[(country, l2)].add(clean(p["company_id"]))
        countries = sorted(set(c for c, _ in cl_counter.keys()),
                           key=lambda c: -sum(cl_counter.get((c, l), 0)
                                              for l in {l for _, l in cl_counter.keys()}))[:8]
        l2s_for_matrix = [s["l2"] for s in lifecycle[:6]]
        country_l2_matrix = {
            "countries": countries,
            "l2s": l2s_for_matrix,
            "cells": [
                {
                    "country": c,
                    "values": {
                        l2: {
                            "n": cl_counter.get((c, l2), 0),
                            "company_ids": [cid for cid in cl_company_ids.get((c, l2), set()) if cid],
                        }
                        for l2 in l2s_for_matrix
                    },
                }
                for c in countries
            ],
        }

        per_l1[L1] = {
            "concentration": concentration,
            "value_chain": value_chain,
            "lifecycle": lifecycle,
            "indication_heatmap": indication_heatmap,
            "new_entrants": new_entrants[:15],
            "recent_active": recent_active,
            "country_l2_matrix": country_l2_matrix,
        }

    payload = {
        "generated_at": "2026-05-26",
        "per_l1": per_l1,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "// auto-generated by scripts/_v3_build_topic_deep.py — do not hand-edit\n"
        f"// per-L1 deep-dive for {len(per_l1)} tracks\n"
        f"window.V3_TOPIC_DEEP_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} · {OUT.stat().st_size/1024:.1f} KB")
    for L1, d in per_l1.items():
        print(f"  {L1:14s} CR5={d['concentration']['cr5']}% HHI={d['concentration']['hhi']:.0f} "
              f"({d['concentration']['hhi_class']:13s}) · "
              f"{len(d['lifecycle'])} L2 · "
              f"{len(d['indication_heatmap']['buckets'])} ind buckets · "
              f"{len(d['new_entrants'])} new entrants 24m · "
              f"{len(d['country_l2_matrix']['countries'])} countries")


if __name__ == "__main__":
    main()
