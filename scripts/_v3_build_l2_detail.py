"""Build compact L2-detail payload for the topic.html L2 drawer.

Schema:
  window.V3_L2_DETAIL = {
    "<L1 name>": {
      "<L2 name>": [
        {
          company_id, name, country, ownership, business_role,
          brands: [
            {
              brand, brand_role,
              products: [
                {
                  product_id, name, registered_name, flag,
                  material, tech_l2,
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
  }

Drives the L2 in-place drawer ("点击 L2 卡片 → 抽屉里看哪几家公司、什么品牌、
什么产品、什么证") — replaces the page-jump nav.

Size: ~50-200 KB total (compact, only reg evidence we need).
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-l2-detail.js"


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


# Flag computed identical to _v3_build_products.py — tier1 = registered_name
# missing in any reg row, tier2 = all names there but at least one indication
# marked unavailable_verified.
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

    # ---- 1. Pull product_master rows with L1 / L2 ----
    products = list(conn.execute("""
        SELECT pm.product_id, pm.company_id, pm.company, pm.brand, pm.brand_role,
               pm.standard_product_name, pm.core_product, pm.registered_name,
               pm.commercial_path_l1 AS l1, pm.commercial_path_l2 AS l2,
               pm.technology_path_l2 AS tech_l2, pm.material_or_energy_source AS material
          FROM product_master pm
         WHERE pm.commercial_path_l1 IS NOT NULL AND pm.commercial_path_l1 != ''
           AND pm.company_id IS NOT NULL AND pm.company_id != ''
    """))

    # ---- 2. Pull registration_evidence keyed by product_id ----
    # Drop placeholder rows where `regulator` contains free text instead of
    # a real authority name (e.g. "Official product/IFU/source text") — those
    # are Codex-internal markers for "indication evidence exists but no public
    # cert". They confuse the drawer, so we hide them from display.
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
        # Match either the known regulator set OR something that contains an
        # uppercase 2-5 letter token at the start (e.g. "FDA 510(k)") AND has
        # a non-empty cert number.
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

    # ---- 3. Companies index for country/ownership/role ----
    co_meta: dict[str, dict] = {}
    for r in conn.execute("""
        SELECT cm.company_id, cm.canonical_name, cm.hq_country, cm.ownership, cm.business_role
          FROM company_master cm
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

    conn.close()

    # ---- 4. Group: L1 → L2 → company_id → brand → product list ----
    # Use ordered dicts via plain dict (py3.7+ preserves insertion order).
    tree: dict[str, dict[str, dict[str, dict]]] = {}
    for p in products:
        l1 = clean(p["l1"])
        l2 = clean(p["l2"]) or "未分类"
        cid = clean(p["company_id"])
        brand = clean(p["brand"]) or "(no brand)"
        if not l1 or not cid:
            continue
        prod_name = (clean(p["standard_product_name"])
                     or clean(p["core_product"])
                     or clean(p["brand"]) or "(unnamed)")
        pid = clean(p["product_id"])
        prod = {
            "product_id":     pid,
            "name":           prod_name,
            "registered_name": clean(p["registered_name"]),
            "material":       clean(p["material"]),
            "tech_l2":        clean(p["tech_l2"]),
            "registrations":  regs_by_pid.get(pid, []),
        }
        flag = flags.get(pid)
        if flag:
            prod["flag"] = flag

        l1_node = tree.setdefault(l1, {})
        l2_node = l1_node.setdefault(l2, {})
        co_node = l2_node.setdefault(cid, {
            "company_id":    cid,
            "name":          co_meta.get(cid, {}).get("name") or clean(p["company"]),
            "country":       co_meta.get(cid, {}).get("country", ""),
            "ownership":     co_meta.get(cid, {}).get("ownership", ""),
            "business_role": co_meta.get(cid, {}).get("business_role", ""),
            "_brands":       {},  # internal — flattened after
        })
        brand_node = co_node["_brands"].setdefault(brand, {
            "brand":      brand,
            "brand_role": clean(p["brand_role"]),
            "products":   [],
        })
        brand_node["products"].append(prod)

    # ---- 5. Flatten into JSON-friendly form (company.brands instead of _brands)
    out_tree: dict[str, dict[str, list[dict]]] = {}
    n_prods = 0
    n_regs = 0
    for l1, l2_map in tree.items():
        out_tree[l1] = {}
        for l2, co_map in l2_map.items():
            company_list = []
            for cid, co in co_map.items():
                brands = list(co["_brands"].values())
                # Sort brands by product count desc, products by name
                brands.sort(key=lambda b: -len(b["products"]))
                for b in brands:
                    b["products"].sort(key=lambda x: x["name"])
                    n_prods += len(b["products"])
                    for prod in b["products"]:
                        n_regs += len(prod.get("registrations", []))
                company_list.append({
                    "company_id":    co["company_id"],
                    "name":          co["name"],
                    "country":       co["country"],
                    "ownership":     co["ownership"],
                    "business_role": co["business_role"],
                    "brands":        brands,
                })
            company_list.sort(key=lambda c: -sum(len(b["products"]) for b in c["brands"]))
            out_tree[l1][l2] = company_list

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(out_tree, ensure_ascii=False, separators=(",", ":"))
    body = (
        "// auto-generated by scripts/_v3_build_l2_detail.py — do not hand-edit\n"
        "// L1 × L2 → company → brand → product → reg evidence (compact)\n"
        f"// {len(out_tree)} L1 · {sum(len(v) for v in out_tree.values())} L2 cells · "
        f"{n_prods:,} products · {n_regs:,} reg-rows\n"
        f"window.V3_L2_DETAIL = {payload};\n"
    )
    OUT.write_text(body, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} · "
        f"{len(out_tree)} L1 · {sum(len(v) for v in out_tree.values())} L2 cells · "
        f"{n_prods:,} prods · {n_regs:,} reg-rows · {OUT.stat().st_size/1024:.1f} KB"
    )


if __name__ == "__main__":
    main()
