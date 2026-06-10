"""Build the company × material-L2 matrix payload for companies-matrix.html.

Schema:
  window.V3_COMPANY_MATRIX = {
    generated_at,
    columns: [ { name, n_products }, ... ],     # top N material_taxonomy_l2_cn
    rows: [
      {
        company_id, name, country, ownership, primary_track,
        total_products,            # across ALL material l2 (incl. tail)
        in_matrix_products,        # products falling into one of the shown columns
        track_count_l2,            # # distinct material_l2 covered (across all)
        track_count_l1,            # # distinct material_l1 covered
        cells: { "<col name>": {n, products: ["A", "B", ...up to 6]} }
      }
    ],
    summary: { companies_total, columns_total, default_min_tracks }
  }

Design choices (2026-06-04, per user spec):
  - dimension = material_taxonomy_l2_cn (the Chinese material taxonomy that
    the user explicitly called "材料赛道")
  - columns = top 14 buckets by product count (covers ≈ 90% of products,
    keeps matrix horizontally readable)
  - default filter: track_count_l2 >= 3 (≈ 62 companies — enough to compare,
    not so many it's noise; user can drop to 2 via UI slider)
  - sort default: track_count_l2 DESC, then total_products DESC
  - per-cell sample product names: cap at 6 (rest get "+N more")
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-company-matrix.js"

TOP_COLUMNS = 24            # show N material_l2 buckets as columns (was 14)
DEFAULT_MIN_TRACKS = 3      # default filter (UI can override)
MIN_L1_PRODUCTS_FOR_ANCHOR = 1   # L1s with fewer products are not forced

# Industry-natural order for the column group divider. Each material_l2 column
# is assigned to its dominant commercial_path_l1 (most products fall into).
# Groups are then rendered in this order, with product-count DESC within each.
L1_ORDER = [
    "Injectables", "EBD", "Regenerative", "Implants",
    "Skincare", "Consumables", "Pharma", "Diagnostics",
    "Surgical", "Services",
]


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"db not found: {DB}")
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # ---- Pull products with material taxonomy ----
    rows = conn.execute("""
        SELECT pm.product_id, pm.company_id, pm.company,
               pm.standard_product_name, pm.core_product, pm.brand,
               pm.registered_name,
               pm.material_taxonomy_l1_cn, pm.material_taxonomy_l2_cn,
               pm.commercial_path_l1,
               c.hq_country, c.ownership, c.primary_track
          FROM product_master pm
          LEFT JOIN companies c ON c.company = pm.company
         WHERE pm.company_id IS NOT NULL AND pm.company_id <> ''
    """).fetchall()

    # Tier 1 / Tier 2 flags (same logic as other v3 builds) — so the cell
    # drawer can show ⊘/· markers per product.
    FLAG_SQL = """
    SELECT product_id, registered_name, intended_use
      FROM registration_evidence
     WHERE product_id IS NOT NULL AND product_id <> ''
    """
    missing_name, no_indication = set(), set()
    for pid, reg_name, intended in conn.execute(FLAG_SQL):
        pid = clean(pid)
        if not pid:
            continue
        if not clean(reg_name):
            missing_name.add(pid)
        elif "unavailable_verified" in clean(intended).lower():
            no_indication.add(pid)
    flags: dict[str, str] = {pid: "tier1" for pid in missing_name}
    for pid in no_indication:
        flags.setdefault(pid, "tier2")
    conn.close()

    # ---- Column ranking — "smart top-N" with per-L1 anchor guarantee ----
    # First count every material_l2 bucket + which commercial L1 it falls in
    col_counter = Counter()
    col_l1_counter: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        l2 = clean(r["material_taxonomy_l2_cn"])
        c1 = clean(r["commercial_path_l1"])
        if l2:
            col_counter[l2] += 1
            if c1:
                col_l1_counter[l2][c1] += 1

    def dominant_l1(m2: str) -> str:
        c = col_l1_counter.get(m2)
        return c.most_common(1)[0][0] if c else ""

    # Bucket every material_l2 under its dominant L1, sorted desc.
    all_l2_sorted = [name for name, _ in col_counter.most_common()]
    by_l1: dict[str, list[str]] = defaultdict(list)
    for m2 in all_l2_sorted:
        by_l1[dominant_l1(m2) or "其他"].append(m2)

    # Anchor pass: include the top-1 material_l2 for every L1 that has any
    # product (guarantees the matrix shows ALL commercial L1 groups —
    # otherwise Consumables / Diagnostics / Surgical / Pharma fall off the
    # cutoff and the user thinks they're missing).
    chosen: list[str] = []
    for l1 in L1_ORDER + [k for k in by_l1 if k not in L1_ORDER]:
        if by_l1.get(l1):
            top1 = by_l1[l1][0]
            if col_counter[top1] >= MIN_L1_PRODUCTS_FOR_ANCHOR and top1 not in chosen:
                chosen.append(top1)
    # Fill the remaining slots from the global top, skipping those already in.
    for m2 in all_l2_sorted:
        if len(chosen) >= TOP_COLUMNS:
            break
        if m2 not in chosen:
            chosen.append(m2)

    col_total_n = {name: col_counter[name] for name in chosen}
    col_dom_l1 = {m2: dominant_l1(m2) for m2 in chosen}
    top_cols_set = set(chosen)
    l1_rank = {name: idx for idx, name in enumerate(L1_ORDER)}
    def col_key(m2: str):
        l1 = col_dom_l1.get(m2, "")
        return (l1_rank.get(l1, 99), -col_total_n[m2], m2)
    top_cols = sorted(chosen, key=col_key)

    # ---- Per-company aggregation ----
    by_co: dict[str, dict] = {}
    for r in rows:
        cid = clean(r["company_id"])
        if not cid:
            continue
        co = by_co.setdefault(cid, {
            "company_id":    cid,
            "name":          clean(r["company"]),
            "country":       clean(r["hq_country"]),
            "ownership":     clean(r["ownership"]),
            "primary_track": clean(r["primary_track"]),
            "_l1_set":       set(),
            "_l2_set":       set(),
            "_total":        0,
            "_cells":        defaultdict(list),  # col -> [ {product dict}, ... ]
        })
        l1 = clean(r["material_taxonomy_l1_cn"])
        l2 = clean(r["material_taxonomy_l2_cn"])
        if l1:
            co["_l1_set"].add(l1)
        if l2:
            co["_l2_set"].add(l2)
        co["_total"] += 1
        prod_name = (clean(r["standard_product_name"])
                     or clean(r["core_product"])
                     or clean(r["brand"]) or "(unnamed)")
        if l2 and l2 in top_cols_set:
            pid = clean(r["product_id"])
            prod = {
                "id":    pid,
                "name":  prod_name,
                "brand": clean(r["brand"]),
            }
            reg = clean(r["registered_name"])
            if reg and reg != prod_name:
                prod["registered_name"] = reg
            f = flags.get(pid)
            if f:
                prod["flag"] = f
            co["_cells"][l2].append(prod)

    # ---- Flatten + sort ----
    out_rows = []
    for cid, co in by_co.items():
        cells = {}
        in_matrix = 0
        in_matrix_tracks = 0
        for col, prods in co["_cells"].items():
            in_matrix += len(prods)
            if len(prods) > 0:
                in_matrix_tracks += 1
            # Full product list (no 6-cap) — needed for cell drawer.
            # Sort by name for deterministic order.
            cells[col] = {
                "n":        len(prods),
                "products": sorted(prods, key=lambda p: p["name"]),
            }
        out_rows.append({
            "company_id":              co["company_id"],
            "name":                    co["name"],
            "country":                 co["country"],
            "ownership":               co["ownership"],
            "primary_track":           co["primary_track"],
            "total_products":          co["_total"],
            "in_matrix_products":      in_matrix,
            # FULL coverage across all material_l2 (incl. long-tail buckets)
            "track_count_l2_all":      len(co["_l2_set"]),
            "track_count_l1":          len(co["_l1_set"]),
            # VISIBLE coverage in the matrix (matches what the user actually sees)
            "track_count_in_matrix":   in_matrix_tracks,
            "cells":                   cells,
        })

    # Default sort: track_count_in_matrix DESC → total_products DESC → name ASC.
    # Switched from track_count_l2_all so the displayed sort matches the badge
    # the user reads (fixes the "Allergan shows 10 but I count 5" confusion).
    out_rows.sort(key=lambda r: (-r["track_count_in_matrix"], -r["total_products"], r["name"]))

    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "columns": [
            {
                "name":       c,
                "n_products": col_total_n[c],
                "group_l1":   col_dom_l1.get(c, ""),
            }
            for c in top_cols
        ],
        "rows": out_rows,
        "summary": {
            "companies_total":      len(out_rows),
            "columns_total":        len(top_cols),
            "default_min_tracks":   DEFAULT_MIN_TRACKS,
            "max_track_in_matrix":  max((r["track_count_in_matrix"] for r in out_rows), default=0),
            "max_track_all":        max((r["track_count_l2_all"]    for r in out_rows), default=0),
            "max_products":         max((r["total_products"]        for r in out_rows), default=0),
            "l1_order":             L1_ORDER,
        },
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "// auto-generated by scripts/_v3_build_company_matrix.py — do not hand-edit\n"
        f"// {len(out_rows)} companies × {len(top_cols)} material-L2 cols · "
        f"default filter min_tracks={DEFAULT_MIN_TRACKS}\n"
        f"window.V3_COMPANY_MATRIX = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )
    OUT.write_text(body, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} · "
        f"{len(out_rows)} companies × {len(top_cols)} cols · "
        f"{OUT.stat().st_size/1024:.1f} KB"
    )


if __name__ == "__main__":
    main()
