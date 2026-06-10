"""Export brand -> family -> SKU 3-level product tree, indexed by company_id,
to web/v3/v3-product-tree.js.

Used by the v3 dashboard's shared company-detail drawer (loaded on every page
that lists companies, not just the globe). The drawer renders a real
hierarchical view of a company's portfolio:

  Brand A
    Family A1
      SKU A1.a  (model_or_sku, technology, material, differentiator)
      SKU A1.b
    Family A2
  Brand B
    ...

Source tables (v4 standardized DB):
  - product_family_master  967 rows  (brand, family, L1/L2, tech, countries)
  - product_sku_master      977 rows  (family_id, sku_id)
  - product_master          977 rows  (sku_id == product_id)  - has narrative
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-product-tree.js"


FAMILY_SQL = """
SELECT
  product_family_id, company_id, company, brand, brand_type,
  product_family, category_l1, category_l2, tech_type, material_or_energy_source,
  countries, regulatory_channels, sku_candidate_count
FROM product_family_master
WHERE company_id IS NOT NULL AND company_id != ''
"""

SKU_SQL = """
SELECT
  s.sku_id, s.product_family_id, s.company_id,
  s.brand, s.product_family, s.model_or_sku, s.sku_candidate_name,
  s.category_l1, s.category_l2, s.tech_type, s.country,
  m.standard_product_name, m.core_product, m.registered_name,
  m.technology_path_l2, m.material_or_energy_source,
  m.verified_differentiator, m.feature_tags, m.brand_role
FROM product_sku_master s
LEFT JOIN product_master m ON m.product_id = s.sku_id
WHERE s.company_id IS NOT NULL AND s.company_id != ''
"""


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
    """Return {product_id: 'tier1'|'tier2'} for products needing a marker.

    tier1 — has reg evidence but at least one row missing registered_name
    tier2 — all reg names filled but at least one row has
            intended_use = unavailable_verified_* (no public indication)
    """
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
    flags = compute_product_flags(conn)

    # ---- 1. Index families by family_id ----
    families: dict[str, dict] = {}
    for row in conn.execute(FAMILY_SQL):
        (fid, cid, company, brand, brand_type, family, l1, l2, tech, mat,
         countries, reg_channels, sku_ct) = row
        if not fid:
            continue
        families[fid] = {
            "family_id": fid,
            "company_id": clean(cid),
            "brand": clean(brand),
            "brand_role": clean(brand_type),
            "family": clean(family),
            "l1": clean(l1),
            "l2": clean(l2),
            "tech": clean(tech),
            "material": clean(mat),
            "countries": clean(countries),
            "regulatory_channels": clean(reg_channels),
            "skus": [],
        }

    # ---- 2. Attach SKUs ----
    orphan_skus = 0
    total_skus = 0
    for row in conn.execute(SKU_SQL):
        (sku_id, fid, cid, brand, family, model_or_sku, sku_cand_name,
         l1, l2, tech, country,
         std_name, core_product, registered_name,
         tech_l2, material, differentiator, feature_tags, brand_role) = row
        total_skus += 1
        name = clean(std_name) or clean(core_product) or clean(sku_cand_name) or clean(family) or "未命名"
        sku = {
            "sku_id": clean(sku_id),
            "name": name,
            "model_or_sku": clean(model_or_sku),
            "registered_name": clean(registered_name),
            "tech_l2": clean(tech_l2),
            "material": clean(material),
            "differentiator": clean(differentiator),
            "tags": clean(feature_tags),
            "country": clean(country),
        }
        # Tier 1 / Tier 2 flag for v3 drawer markers (only emit when set).
        flag = flags.get(clean(sku_id))
        if flag:
            sku["flag"] = flag
        # If we have a family_id, push under it. Otherwise drop into a synthetic
        # "(unfiled)" family for that brand on that company.
        if fid and fid in families:
            families[fid]["skus"].append(sku)
        else:
            orphan_skus += 1
            # Build a synthetic family key per (company_id, brand)
            syn_fid = f"orphan::{clean(cid)}::{clean(brand)}"
            if syn_fid not in families:
                families[syn_fid] = {
                    "family_id": syn_fid,
                    "company_id": clean(cid),
                    "brand": clean(brand),
                    "brand_role": clean(brand_role),
                    "family": clean(brand) or "Misc",
                    "l1": clean(l1),
                    "l2": clean(l2),
                    "tech": clean(tech),
                    "material": "",
                    "countries": clean(country),
                    "regulatory_channels": "",
                    "skus": [],
                }
            families[syn_fid]["skus"].append(sku)

    # ---- 3. Group by company → brand → families ----
    tree_by_company: dict[str, list[dict]] = {}
    for fid, fam in families.items():
        cid = fam["company_id"]
        if not cid:
            continue
        bucket = tree_by_company.setdefault(cid, {})
        brand_key = fam["brand"] or "(no brand)"
        if brand_key not in bucket:
            bucket[brand_key] = {
                "brand": fam["brand"],
                "brand_role": fam["brand_role"],
                "families": [],
            }
        bucket[brand_key]["families"].append({
            k: fam[k]
            for k in ("family_id","family","l1","l2","tech","material",
                      "countries","regulatory_channels","skus")
        })

    # ---- 4. Flatten brand buckets into ordered lists; compute counts ----
    final: dict[str, list[dict]] = {}
    for cid, brand_map in tree_by_company.items():
        brand_list = []
        for brand_key, brand_obj in brand_map.items():
            fams = brand_obj["families"]
            sku_n = sum(len(f["skus"]) for f in fams)
            # Sort families by skus desc, then name
            fams.sort(key=lambda f: (-len(f["skus"]), f["family"]))
            # Sort SKUs within each family by name
            for f in fams:
                f["skus"].sort(key=lambda s: s["name"])
                f["sku_count"] = len(f["skus"])
            brand_list.append({
                "brand": brand_obj["brand"],
                "brand_role": brand_obj["brand_role"],
                "family_count": len(fams),
                "sku_count": sku_n,
                "families": fams,
            })
        # Sort brands by sku_count desc
        brand_list.sort(key=lambda b: (-b["sku_count"], b["brand"] or ""))
        final[cid] = brand_list

    conn.close()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(final, ensure_ascii=False, separators=(",", ":"))
    total_brands = sum(len(v) for v in final.values())
    total_fams = sum(len(b["families"]) for v in final.values() for b in v)
    total_sku_kept = sum(b["sku_count"] for v in final.values() for b in v)
    OUT.write_text(
        "// auto-generated by scripts/_v3_build_product_tree.py — do not hand-edit\n"
        f"// {len(final):,} companies · {total_brands:,} brands · {total_fams:,} families · {total_sku_kept:,} SKUs\n"
        f"// (orphan SKUs without family_master link: {orphan_skus:,})\n"
        f"window.V3_PRODUCT_TREE_BY_COMPANY = {payload};\n",
        encoding="utf-8",
    )
    print(
        f"wrote {OUT.relative_to(ROOT)} · "
        f"{len(final):,} cos · {total_brands:,} brands · "
        f"{total_fams:,} fams · {total_sku_kept:,}/{total_skus:,} SKUs · "
        f"{OUT.stat().st_size/1024:.1f} KB"
    )


if __name__ == "__main__":
    main()
