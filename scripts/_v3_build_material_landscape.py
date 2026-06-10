"""Build the material-taxonomy landscape payload for index.html.

User wants a "phenomenon-level" view on the overview page that shows the raw
industry structure BEFORE the analytical conclusions: how many L1 material
groups, how many L2 sub-groups inside each, and the product count per L2.

Output: web/v3/v3-material-landscape.js → window.V3_MATERIAL_LANDSCAPE = {
  generated_at,
  summary: {
    total_products, l1_count, l2_count
  },
  l1_cards: [
    {
      name,                  # e.g. 能量设备
      n_products,            # 389
      l2_count,              # 8
      dom_commercial_l1,     # EBD / Injectables / ... (track color hook)
      l2_list: [
        { name, n_products },
        ...
      ]
    },
    ...
  ]
}

L1 cards are sorted by product count desc. L2 lists are sorted by product
count desc inside each card.
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-material-landscape.js"

# 2026-06-04: collapse misclassified material_l1 buckets that are conceptually
# L2-level into their proper parent L1. Zero data loss — the orphan L1 name
# becomes a new L2 under the parent, and the original L2 slides down to L3.
# Db itself is not touched; this is a v3-derived normalization only.
L1_NORMALIZATION_MAP = {
    "肉毒毒素":          "注射类",
    "透明质酸填充剂":   "注射类",
    "皮肤动能素/水光":  "注射类",
    "溶脂注射":          "注射类",
    "器械/给药设备":    "耗材/器械",
    "手术器械":          "耗材/器械",
    "皮肤管理设备":     "能量设备",
    "能量源设备":        "能量设备",
    # Kept independent (legitimate own L1):
    #   能量设备 / 注射类 / 功效性护肤品 / 耗材/器械 / 植入物 /
    #   埋线提升 / 诊断/影像 / 药品/皮肤科药物
}


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"db not found: {DB}")
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("""
        SELECT pm.product_id, pm.material_taxonomy_l1_cn AS m1,
               pm.material_taxonomy_l2_cn AS m2,
               pm.material_taxonomy_l3_cn AS m3,
               pm.commercial_path_l1 AS c1,
               pm.company_id, pm.company,
               pm.brand, pm.standard_product_name, pm.core_product,
               pm.registered_name,
               c.hq_country AS country
          FROM product_master pm
          LEFT JOIN companies c ON c.company = pm.company
         WHERE pm.material_taxonomy_l1_cn IS NOT NULL AND pm.material_taxonomy_l1_cn <> ''
    """).fetchall()
    total_products_all = conn.execute("SELECT COUNT(*) FROM product_master").fetchone()[0]
    conn.close()

    # l1 -> l2 -> {products, companies set, countries, l3, per-co counts, products_list}
    l1_l2: dict[str, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "products": 0,
        "companies": set(),
        "countries": set(),
        "l3": Counter(),
        "co_counts": Counter(),       # company_id -> n products in this l2
        "co_meta": {},                # company_id -> {name, country, ownership}
        "products_list": [],          # list of {product_id, name, brand, registered_name, company_id, company, l3}
    }))
    l1_total: Counter = Counter()
    l1_companies: dict[str, set] = defaultdict(set)
    l1_countries: dict[str, set] = defaultdict(set)
    l1_commercial: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        raw_l1 = clean(r["m1"])
        raw_l2 = clean(r["m2"])
        raw_l3 = clean(r["m3"])
        # Apply normalization: if raw_l1 is a misclassified orphan, slide:
        #   L1 ← parent, L2 ← raw_l1 (orphan name), L3 ← raw_l2 (or raw_l3 if l2 empty)
        if raw_l1 in L1_NORMALIZATION_MAP:
            l1 = L1_NORMALIZATION_MAP[raw_l1]
            l2 = raw_l1
            l3 = raw_l2 or raw_l3
        else:
            l1 = raw_l1
            l2 = raw_l2 or "(未分类)"
            l3 = raw_l3
        c1 = clean(r["c1"])
        cid = clean(r["company_id"])
        cname = clean(r["company"])
        country = clean(r["country"])
        node = l1_l2[l1][l2]
        node["products"] += 1
        if cid:
            node["companies"].add(cid)
            node["co_counts"][cid] += 1
            if cid not in node["co_meta"]:
                node["co_meta"][cid] = {"name": cname, "country": country}
        if country: node["countries"].add(country)
        if l3: node["l3"][l3] += 1
        pname = (clean(r["standard_product_name"])
                 or clean(r["core_product"])
                 or clean(r["brand"]) or "(unnamed)")
        node["products_list"].append({
            "product_id":     clean(r["product_id"]),
            "name":           pname,
            "brand":          clean(r["brand"]),
            "registered_name": clean(r["registered_name"]),
            "company_id":     cid,
            "company":        cname,
            "l3":             l3,
        })
        l1_total[l1] += 1
        if cid: l1_companies[l1].add(cid)
        if country: l1_countries[l1].add(country)
        if c1: l1_commercial[l1][c1] += 1

    l1_cards = []
    for l1, total in l1_total.most_common():
        l2_items = []
        for l2, node in sorted(l1_l2[l1].items(), key=lambda kv: -kv[1]["products"]):
            l3_items = [{"name": n, "n_products": v} for n, v in node["l3"].most_common()]
            # Companies sorted by n products desc (top 30, rest in "more")
            top_cos = []
            for cid, n in node["co_counts"].most_common(30):
                meta = node["co_meta"].get(cid, {})
                top_cos.append({
                    "company_id": cid,
                    "name":       meta.get("name", ""),
                    "country":    meta.get("country", ""),
                    "n_products": n,
                })
            more_companies = max(0, len(node["co_counts"]) - 30)
            # Products: keep all, sort by name. Strip empty registered_name.
            prods_clean = []
            for p in sorted(node["products_list"], key=lambda x: x["name"]):
                d = {
                    "id":         p["product_id"],
                    "name":       p["name"],
                    "company_id": p["company_id"],
                    "company":    p["company"],
                }
                if p["brand"] and p["brand"] != p["name"]:
                    d["brand"] = p["brand"]
                if p["registered_name"] and p["registered_name"] != p["name"]:
                    d["registered_name"] = p["registered_name"]
                if p["l3"]:
                    d["l3"] = p["l3"]
                prods_clean.append(d)
            l2_items.append({
                "name":          l2,
                "n_products":    node["products"],
                "n_companies":   len(node["companies"]),
                "n_countries":   len(node["countries"]),
                "share_pct":     round(node["products"] / total * 100, 1) if total else 0,
                "l3_list":       l3_items,
                "companies":     top_cos,
                "more_companies": more_companies,
                "products":      prods_clean,
            })
        dom_c1 = l1_commercial[l1].most_common(1)[0][0] if l1_commercial[l1] else ""
        l1_cards.append({
            "name":             l1,
            "n_products":       total,
            "n_companies":      len(l1_companies[l1]),
            "n_countries":      len(l1_countries[l1]),
            "l2_count":         len(l2_items),
            "dom_commercial_l1": dom_c1,
            "l2_list":          l2_items,
        })

    total_products_classified = sum(l1_total.values())
    total_l2 = sum(len(l1_l2[l1]) for l1 in l1_l2)
    payload = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "summary": {
            "total_products_all":        total_products_all,
            "total_products_classified": total_products_classified,
            "l1_count":                  len(l1_cards),
            "l2_count":                  total_l2,
        },
        "l1_cards": l1_cards,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "// auto-generated by scripts/_v3_build_material_landscape.py — do not hand-edit\n"
        f"// {len(l1_cards)} material L1 · {total_l2} L2 buckets · "
        f"{total_products_classified}/{total_products_all} products classified\n"
        f"window.V3_MATERIAL_LANDSCAPE = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )
    OUT.write_text(body, encoding="utf-8")
    print(
        f"wrote {OUT.relative_to(ROOT)} · "
        f"{len(l1_cards)} L1 · {total_l2} L2 · "
        f"{OUT.stat().st_size/1024:.1f} KB"
    )


if __name__ == "__main__":
    main()
