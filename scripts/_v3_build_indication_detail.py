"""Build compact per-indication-bucket payload for the indications.html drawer.

Schema:
  window.V3_INDICATION_DETAIL = {
    "<bucket name>": [
      {
        company_id, name, country, ownership, business_role,
        brands: [
          { brand, brand_role,
            products: [
              { product_id, name, registered_name, flag,
                indication_evidence: [
                  {regulator, country, year, indication_text, source_url}
                ],
                registrations: [
                  {regulator, jurisdiction, number, date, pathway, status}
                ]
              }
            ]
          }
        ]
      }
    ]
  }

Drives V3IndicationDrawer ("点击适应症桶 → 抽屉里看哪几家公司什么产品做这个 indication").

Reuses the Tier 1 / Tier 2 flag logic from _v3_build_products.py /
_v3_build_l2_detail.py so the drawer can render the same chip/dot markers.
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-indication-detail.js"


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


FLAG_SQL = """
SELECT product_id, registered_name, intended_use
  FROM registration_evidence
 WHERE product_id IS NOT NULL AND product_id <> ''
"""


def compute_product_flags(conn) -> dict[str, str]:
    missing_name: set[str] = set()
    no_indication: set[str] = set()
    for pid, reg_name, intended in conn.execute(FLAG_SQL):
        pid = clean(pid)
        if not pid:
            continue
        if not clean(reg_name):
            missing_name.add(pid)
        elif "unavailable_verified" in clean(intended).lower():
            no_indication.add(pid)
    out: dict[str, str] = {}
    for pid in missing_name:
        out[pid] = "tier1"
    for pid in no_indication:
        if pid not in out:
            out[pid] = "tier2"
    return out


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"db not found: {DB}")
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    flags = compute_product_flags(conn)

    # company meta
    co_meta: dict[str, dict] = {}
    for r in conn.execute("""
        SELECT company_id, canonical_name, hq_country, ownership, business_role
          FROM company_master
    """):
        cid = clean(r["company_id"])
        if not cid:
            continue
        co_meta[cid] = {
            "name":          clean(r["canonical_name"]),
            "country":       clean(r["hq_country"]),
            "ownership":     clean(r["ownership"]),
            "business_role": clean(r["business_role"]),
        }

    # product master meta (for product/brand/company resolution)
    pm_meta: dict[str, dict] = {}
    for r in conn.execute("""
        SELECT product_id, company_id, company, brand, brand_role,
               standard_product_name, core_product, registered_name
          FROM product_master
         WHERE product_id IS NOT NULL AND product_id <> ''
    """):
        pid = clean(r["product_id"])
        pm_meta[pid] = {
            "company_id":    clean(r["company_id"]),
            "company_name":  clean(r["company"]),
            "brand":         clean(r["brand"]) or "(no brand)",
            "brand_role":    clean(r["brand_role"]),
            "name":          clean(r["standard_product_name"])
                              or clean(r["core_product"])
                              or clean(r["brand"]) or "(unnamed)",
            "registered_name": clean(r["registered_name"]),
        }

    # registrations per product (compact) — same filter as _v3_build_l2_detail
    REAL_REGULATORS = {
        "FDA", "NMPA", "CE", "MDR", "EU-MDR", "CE/MDR",
        "MFDS", "KFDA", "PMDA", "TGA", "MHRA", "ANVISA",
        "Health Canada", "HSA", "INVIMA", "COFEPRIS", "FOPH",
        "Swissmedic", "ROSZDRAV", "Russia", "Saudi FDA", "SFDA",
    }
    def is_real_reg(reg_word: str, number: str) -> bool:
        rw = clean(reg_word)
        if not rw:
            return False
        if rw in REAL_REGULATORS:
            return True
        first = rw.split()[0]
        if first.isupper() and 2 <= len(first) <= 6 and number:
            return True
        return False

    regs_by_pid: dict[str, list[dict]] = defaultdict(list)
    for r in conn.execute("""
        SELECT product_id, regulator, jurisdiction, registration_no,
               approval_date, regulatory_pathway, status
          FROM registration_evidence
         WHERE product_id IS NOT NULL AND product_id <> ''
         ORDER BY approval_date DESC
    """):
        pid = clean(r["product_id"])
        if not pid:
            continue
        regulator = clean(r["regulator"])
        number = clean(r["registration_no"])
        if not is_real_reg(regulator, number):
            continue
        regs_by_pid[pid].append({
            "regulator":    regulator,
            "jurisdiction": clean(r["jurisdiction"]),
            "number":       number,
            "date":         (clean(r["approval_date"]) or "")[:10],
            "pathway":      clean(r["regulatory_pathway"]),
            "status":       clean(r["status"]),
        })

    # official indication evidence — explode comma-separated buckets
    # ind_per_product: {product_id: {bucket: [evidence_row, ...]}}
    ind_per_product: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in conn.execute("""
        SELECT product_id, indication, buckets, regulator, country, year, source_url, source_label
          FROM official_indication_evidence
         WHERE buckets IS NOT NULL AND buckets <> ''
    """):
        pid = clean(r["product_id"])
        if not pid:
            continue
        buckets_str = clean(r["buckets"])
        for bucket in [b.strip() for b in buckets_str.split(",") if b.strip()]:
            ind_per_product[pid][bucket].append({
                "regulator":       clean(r["regulator"]),
                "country":         clean(r["country"]),
                "year":            clean(r["year"]),
                "indication_text": clean(r["indication"])[:200],
                "source_url":      clean(r["source_url"]),
            })

    conn.close()

    # ---- Group: bucket → company_id → brand → product ----
    # Iterate every (product, bucket) pair and bucket up.
    tree: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    # tree[bucket][company_id] = {meta..., "_brands": {brand: {brand, brand_role, products: []}}}
    for pid, by_bucket in ind_per_product.items():
        meta = pm_meta.get(pid)
        if not meta:
            continue
        cid = meta["company_id"]
        if not cid:
            continue
        for bucket, ind_evidence_rows in by_bucket.items():
            co_node = tree[bucket].get(cid)
            if not co_node:
                cm = co_meta.get(cid, {})
                co_node = {
                    "company_id":    cid,
                    "name":          cm.get("name") or meta["company_name"],
                    "country":       cm.get("country", ""),
                    "ownership":     cm.get("ownership", ""),
                    "business_role": cm.get("business_role", ""),
                    "_brands":       {},
                }
                tree[bucket][cid] = co_node
            brand = meta["brand"]
            brand_node = co_node["_brands"].setdefault(brand, {
                "brand":      brand,
                "brand_role": meta["brand_role"],
                "products":   [],
            })
            prod = {
                "product_id":         pid,
                "name":               meta["name"],
                "registered_name":    meta["registered_name"],
                "indication_evidence": ind_evidence_rows,
                "registrations":      regs_by_pid.get(pid, []),
            }
            flag = flags.get(pid)
            if flag:
                prod["flag"] = flag
            brand_node["products"].append(prod)

    # ---- Flatten ----
    out_tree: dict[str, list[dict]] = {}
    n_buckets = 0
    n_co_rows = 0
    n_prods = 0
    for bucket, co_map in tree.items():
        company_list = []
        for cid, co in co_map.items():
            brands = list(co["_brands"].values())
            brands.sort(key=lambda b: -len(b["products"]))
            for b in brands:
                b["products"].sort(key=lambda x: x["name"])
                n_prods += len(b["products"])
            company_list.append({
                "company_id":    co["company_id"],
                "name":          co["name"],
                "country":       co["country"],
                "ownership":     co["ownership"],
                "business_role": co["business_role"],
                "brands":        brands,
            })
        company_list.sort(key=lambda c: -sum(len(b["products"]) for b in c["brands"]))
        out_tree[bucket] = company_list
        n_buckets += 1
        n_co_rows += len(company_list)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(out_tree, ensure_ascii=False, separators=(",", ":"))
    body = (
        "// auto-generated by scripts/_v3_build_indication_detail.py — do not hand-edit\n"
        "// bucket → company → brand → product → indication evidence + reg evidence\n"
        f"// {n_buckets} buckets · {n_co_rows} co-rows · {n_prods:,} products\n"
        f"window.V3_INDICATION_DETAIL = {payload};\n"
    )
    OUT.write_text(body, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} · "
        f"{n_buckets} buckets · {n_co_rows} co-rows · {n_prods:,} prods · "
        f"{OUT.stat().st_size/1024:.1f} KB"
    )


if __name__ == "__main__":
    main()
