"""Generate web/v3/v3-deep-dive.js — powers two consumers:

  window.V3_DEEP_DIVE_DATA  → deep-dive.html
     • material_tree   : 3-tier material taxonomy (L1→L2→L3, 8→32→68) with counts
     • commercial_tree : commercial L1→L2→technology (10→56→tech) with counts
     • summary

  window.V3_PIVOT_DATA      → cross-analysis.html (Lens 04) + deep-dive.html
     • facts   : one compact row per product (982), enriched with company attrs
     • dims    : registry of pivotable dimensions (label + type single|multi)
     • presets : 4 named row×col×stack configurations the user requested
     • colors  : per-dimension value→color hints for stable rendering

The page aggregates `facts` client-side, so the 4D pivot is fully switchable
without any further data fetch. Multi-valued dims (regulators, indications) are
exploded on the client.

Run:  python scripts/_v3_build_deep_dive.py
"""
from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-deep-dive.js"

TRACK_ORDER = ["EBD", "Injectables", "Skincare", "Regenerative", "Implants",
               "Consumables", "Diagnostics", "Surgical", "Pharma", "Thread Lift"]


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def norm_reg(r: str) -> str:
    r = (r or "").lower()
    if "fda" in r and "kfda" not in r and "mfds" not in r:
        return "FDA"
    if "ifu" in r:
        return "IFU"
    if "nmpa" in r or "cfda" in r:
        return "NMPA"
    if "mfds" in r or "kfda" in r or "korea" in r:
        return "KFDA"
    if ("ce" in r or "eudamed" in r or "european" in r or "notified" in r
            or "mdr" in r):
        return "CE/EU"
    return "Other"


def norm_role(r: str) -> str:
    r = clean(r)
    rl = r.lower()
    if "r&d" in rl or "oem" in rl:
        return "R&D/OEM"
    if "manufacturer" in rl and "brand" in rl:
        return "制造+品牌"
    if "manufacturer" in rl:
        return "Manufacturer"
    if "brand" in rl:
        return "Brand Owner"
    if "biotech" in rl:
        return "Biotech"
    return "Other"


def cap_band(exchange: str, ownership: str) -> str:
    ex = (exchange or "").upper().strip()
    if not ex:
        if ownership == "Public":
            return "已上市·其他"
        return "未上市/私营"
    if ex in ("NASDAQ", "NYSE", "OTC"):
        return "美股 NASDAQ/NYSE"
    if ex in ("KRX", "KOSDAQ", "KOSPI"):
        return "韩股 KRX"
    if ex in ("BORSA ITALIANA", "PA", "SIX", "AMS", "FRA", "LSE", "EPA"):
        return "欧股"
    if ex in ("SZSE", "SSE", "HKEX", "TW", "TWO", "T", "TA", "TYO"):
        return "亚太其他"
    return "其他上市"


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"db not found: {DB}")
    conn = sqlite3.connect(str(DB), timeout=60)
    conn.row_factory = sqlite3.Row

    # ---------- company attribute lookup (by canonical company name) ----------
    co_attr = {}
    for c in conn.execute("SELECT * FROM companies"):
        co_attr[clean(c["company"])] = {
            "region": clean(c["region"]) or "Other",
            "country": clean(c["hq_country"]) or "—",
            "ownership": clean(c["ownership"]) or "Private",
            "role": norm_role(c["business_role"]),
            "ptrack": clean(c["primary_track"]) or "—",
            "fda_products": int(c["fda_products"] or 0),
        }

    # company_id from product_master (authoritative id used by V3CompanyDetail)
    name_to_cid = {}
    for r in conn.execute(
        "SELECT DISTINCT company, company_id FROM product_master "
        "WHERE company_id IS NOT NULL AND company_id != ''"
    ):
        name_to_cid.setdefault(clean(r["company"]), clean(r["company_id"]))

    # ---------- regulator set per company (from registration_evidence) ----------
    co_regs = defaultdict(set)
    for r in conn.execute(
        "SELECT company, regulator FROM registration_evidence "
        "WHERE company IS NOT NULL AND company != ''"
    ):
        co_regs[clean(r["company"])].add(norm_reg(r["regulator"]))
    # add FDA flag from companies.fda_products
    for name, a in co_attr.items():
        if a["fda_products"] > 0:
            co_regs[name].add("FDA")

    # ---------- exchange per company (capital band) ----------
    co_exchange = {}
    for r in conn.execute(
        "SELECT company, exchange FROM listed_company_batch "
        "WHERE company IS NOT NULL AND company != ''"
    ):
        if clean(r["exchange"]):
            co_exchange.setdefault(clean(r["company"]), clean(r["exchange"]))

    # ---------- indication buckets per product ----------
    prod_ind = defaultdict(set)
    for r in conn.execute(
        "SELECT product_id, buckets FROM official_indication_evidence "
        "WHERE product_id IS NOT NULL AND product_id != '' AND buckets != ''"
    ):
        for part in clean(r["buckets"]).replace("，", ",").split(","):
            part = part.strip()
            if part and part != "其他官方适应症":
                prod_ind[clean(r["product_id"])].add(part)

    # ---------- enriched product fact table ----------
    facts = []
    mat_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))   # m1>m2>m3 counts
    com_tree = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))   # l1>l2>tech counts
    for p in conn.execute("SELECT * FROM product_master"):
        co = clean(p["company"])
        a = co_attr.get(co, {})
        l1 = clean(p["commercial_path_l1"]) or "—"
        l2 = clean(p["commercial_path_l2"]) or "—"
        m1 = clean(p["material_taxonomy_l1_cn"]) or "—"
        m2 = clean(p["material_taxonomy_l2_cn"]) or "—"
        m3 = clean(p["material_taxonomy_l3_cn"]) or "—"
        tech = clean(p["technology_path_l1"]) or clean(p["material_or_energy_source"]) or "—"
        own = a.get("ownership", "Private")
        cap = cap_band(co_exchange.get(co, ""), own)
        regs = sorted(co_regs.get(co, set())) or ["无证据"]
        pid = clean(p["product_id"])
        inds = sorted(prod_ind.get(pid, set())) or ["未标注"]
        facts.append({
            "p": pid,
            "co": co,
            "ci": name_to_cid.get(co, ""),
            "b": clean(p["brand"]) or clean(p["standard_product_name"]),
            "nm": clean(p["standard_product_name"]) or clean(p["brand"]) or co,
            "l1": l1, "l2": l2,
            "m1": m1, "m2": m2, "m3": m3,
            "t": tech,
            "rg": a.get("region", "Other"),
            "cy": a.get("country", "—"),
            "ow": own,
            "ro": a.get("role", "Other"),
            "pt": a.get("ptrack", "—"),
            "cap": cap,
            "reg": regs,
            "ind": inds,
        })
        # build hierarchy counts
        mat_tree[m1][m2][m3] += 1
        com_tree[l1][l2][tech] += 1

    # ---------- hierarchy → nested node lists (sorted by count desc) ----------
    def nest3(tree, top_leaf=12):
        out = []
        for k1, sub in sorted(tree.items(), key=lambda kv: -sum(
                sum(d.values()) for d in kv[1].values())):
            n1 = sum(sum(d.values()) for d in sub.values())
            ch1 = []
            for k2, leaves in sorted(sub.items(), key=lambda kv: -sum(kv[1].values())):
                n2 = sum(leaves.values())
                ch2 = [{"name": k3, "n": n}
                       for k3, n in sorted(leaves.items(), key=lambda kv: -kv[1])[:top_leaf]]
                ch1.append({"name": k2, "n": n2, "children": ch2})
            out.append({"name": k1, "n": n1, "children": ch1})
        return out

    material_tree = {"name": "材料分类", "children": nest3(mat_tree)}
    commercial_tree = {"name": "商业赛道", "children": nest3(com_tree, top_leaf=10)}

    # ---------- dimension registry for the pivot UI ----------
    dims = [
        {"key": "l1",  "cn": "商业赛道 L1", "en": "Track L1",     "type": "single"},
        {"key": "l2",  "cn": "子赛道 L2",   "en": "Sub-track L2", "type": "single"},
        {"key": "m1",  "cn": "材料 L1",     "en": "Material L1",  "type": "single"},
        {"key": "m2",  "cn": "材料 L2",     "en": "Material L2",  "type": "single"},
        {"key": "m3",  "cn": "材料 L3",     "en": "Material L3",  "type": "single"},
        {"key": "t",   "cn": "技术/材料源", "en": "Technology",   "type": "single"},
        {"key": "rg",  "cn": "地区",        "en": "Region",       "type": "single"},
        {"key": "cy",  "cn": "国家",        "en": "Country",      "type": "single"},
        {"key": "ow",  "cn": "所有制",      "en": "Ownership",    "type": "single"},
        {"key": "ro",  "cn": "价值链角色",  "en": "Role",         "type": "single"},
        {"key": "cap", "cn": "资本档",      "en": "Capital",      "type": "single"},
        {"key": "reg", "cn": "监管通道",    "en": "Regulator",    "type": "multi"},
        {"key": "ind", "cn": "适应症桶",    "en": "Indication",   "type": "multi"},
    ]

    presets = [
        {"id": "A", "name": "赛道 × 子赛道 × 地区 × 所有制",
         "row": "l1", "rowSub": "l2", "col": "rg", "stack": "ow",
         "hint": "每个赛道在各地区的公私结构 — 行可下钻到子赛道"},
        {"id": "B", "name": "材料 L1 × L2 × L3 × 监管",
         "row": "m1", "rowSub": "m2", "col": "reg", "stack": "m3",
         "hint": "三级材料分类的监管覆盖 — 行下钻到 L2，单元堆叠 L3"},
        {"id": "C", "name": "资本档 × 赛道 × 地区",
         "row": "cap", "rowSub": "", "col": "l1", "stack": "rg",
         "hint": "上市资本档在各赛道、各地区的分布"},
        {"id": "D", "name": "赛道 × 子赛道 × 适应症",
         "row": "l1", "rowSub": "l2", "col": "ind", "stack": "l2",
         "hint": "各赛道主攻的官方适应症（适应症数据较稀疏）"},
    ]

    summary = {
        "products": len(facts),
        "mat_l1": len(material_tree["children"]),
        "mat_l2": sum(len(n["children"]) for n in material_tree["children"]),
        "mat_l3": sum(len(c["children"]) for n in material_tree["children"] for c in n["children"]),
        "com_l1": len(commercial_tree["children"]),
        "com_l2": sum(len(n["children"]) for n in commercial_tree["children"]),
        "companies": len({f["co"] for f in facts if f["co"]}),
        "dims": len(dims),
    }

    deep = {
        "summary": summary,
        "material_tree": material_tree,
        "commercial_tree": commercial_tree,
    }
    pivot = {
        "facts": facts,
        "dims": dims,
        "presets": presets,
        "regOrder": ["FDA", "CE/EU", "NMPA", "KFDA", "IFU", "Other", "无证据"],
        "ownOrder": ["Public", "Private", "Subsidiary"],
        "regionOrder": ["North America", "Europe", "Asia-Pacific", "Middle East",
                        "Latin America", "Africa", "Other"],
        "trackOrder": TRACK_ORDER,
    }

    conn.close()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "// auto-generated by scripts/_v3_build_deep_dive.py — do not hand-edit\n"
        f"// summary: {json.dumps(summary, ensure_ascii=False)}\n"
        f"window.V3_DEEP_DIVE_DATA = {json.dumps(deep, ensure_ascii=False, separators=(',', ':'))};\n"
        f"window.V3_PIVOT_DATA = {json.dumps(pivot, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} · {OUT.stat().st_size/1024:.1f} KB")
    print(f"  material: {summary['mat_l1']} L1 · {summary['mat_l2']} L2 · {summary['mat_l3']} L3")
    print(f"  commercial: {summary['com_l1']} L1 · {summary['com_l2']} L2")
    print(f"  facts: {summary['products']} products · {summary['companies']} companies · {len(dims)} dims")


if __name__ == "__main__":
    main()
