#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
MATCH_CSV = AUDIT_DIR / "nmpa_registration_project_match_latest.csv"
PRODUCT_MASTER_CSV = DATA_DIR / "product_master.csv"
LATEST_HTML = AUDIT_DIR / "nmpa_registration_project_review_latest.html"

COMPANY_GROUPS = [
    (["q-med", "q med", "科医"], ["Galderma", "Q-Med AB"]),
    (["ipsen"], ["Galderma", "Ipsen"]),
]

TRACK_HINTS = {
    "ha": ["透明质酸", "HA", "hyaluronic"],
    "plla": ["PLLA", "聚乳酸", "Sculptra"],
    "caha": ["CaHA", "羟基磷灰石", "Radiesse"],
    "botulinum": ["肉毒", "toxin", "BoNT"],
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def ascii_norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", norm(value).casefold()).strip()


def tokens(value: Any) -> set[str]:
    text = ascii_norm(value)
    return {token for token in text.split() if len(token) >= 2}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def product_label(product: dict[str, str]) -> str:
    return " ".join(
        norm(product.get(field))
        for field in [
            "company",
            "brand",
            "standard_product_name",
            "registered_name",
            "core_product",
            "legal_manufacturer",
            "marketing_holder",
            "local_holder",
            "manufactured_by",
            "material_taxonomy_path_cn",
            "commercial_path_l1",
            "commercial_path_l2",
        ]
    )


def row_company_text(row: dict[str, str]) -> str:
    return " ".join(
        norm(row.get(field))
        for field in [
            "matched_company",
            "nmpa_registrant",
            "nmpa_manufacturer_group",
            "nmpa_product_name",
            "official_product_name",
        ]
    )


def row_product_text(row: dict[str, str]) -> str:
    return " ".join(
        norm(row.get(field))
        for field in [
            "nmpa_brand",
            "nmpa_aliases",
            "nmpa_product_name",
            "official_product_name",
            "official_scope",
            "track",
        ]
    )


def company_candidates_from_text(text: str, products: list[dict[str, str]]) -> set[str]:
    out: set[str] = set()
    normalized = ascii_norm(text)
    for needles, companies in COMPANY_GROUPS:
        if any(needle in normalized for needle in needles):
            out.update(companies)
    for product in products:
        company = norm(product.get("company"))
        if company and ascii_norm(company) in normalized:
            out.add(company)
        for field in ["legal_manufacturer", "marketing_holder", "local_holder", "manufactured_by"]:
            value = norm(product.get(field))
            if value and len(ascii_norm(value)) >= 4 and ascii_norm(value) in normalized:
                out.add(company)
    return out


def track_score(row: dict[str, str], product: dict[str, str]) -> int:
    track = ascii_norm(row.get("track"))
    text = product_label(product).casefold()
    score = 0
    for key, hints in TRACK_HINTS.items():
        if key in track:
            if any(hint.casefold() in text for hint in hints):
                score += 35
            else:
                score -= 12
    return score


def build_candidates(
    row: dict[str, str],
    products: list[dict[str, str]],
    company_hints: set[str],
) -> list[dict[str, Any]]:
    row_tokens = tokens(row_product_text(row))
    exact_product_id = norm(row.get("matched_product_id"))
    scored: list[tuple[int, dict[str, str], list[str]]] = []

    for product in products:
        score = 0
        reasons: list[str] = []
        product_id = norm(product.get("product_id"))
        company = norm(product.get("company"))
        product_tokens = tokens(product_label(product))

        if exact_product_id and product_id == exact_product_id:
            score += 180
            reasons.append("系统原始候选")
        if company and company in company_hints:
            score += 80
            reasons.append("同公司/同集团")
        overlap = sorted((row_tokens & product_tokens) - {"injection", "gel", "medical", "device", "product"})
        if overlap:
            score += min(60, 15 * len(overlap))
            reasons.append("名称线索：" + " / ".join(overlap[:4]))
        score += track_score(row, product)
        if score > 0 and (company_hints or exact_product_id or row.get("decision") == "review"):
            scored.append((score, product, reasons))

    scored.sort(key=lambda item: (item[0], norm(item[1].get("company")), norm(item[1].get("brand"))), reverse=True)
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, product, reasons in scored:
        product_id = norm(product.get("product_id"))
        if not product_id or product_id in seen:
            continue
        seen.add(product_id)
        candidates.append(
            {
                "product_id": product_id,
                "company": norm(product.get("company")),
                "brand": norm(product.get("brand")),
                "product": norm(product.get("standard_product_name")) or norm(product.get("core_product")),
                "registered_name": norm(product.get("registered_name")),
                "material_path": norm(product.get("material_taxonomy_path_cn")),
                "commercial_path": " > ".join(
                    part
                    for part in [norm(product.get("commercial_path_l1")), norm(product.get("commercial_path_l2"))]
                    if part
                ),
                "score": score,
                "reasons": reasons[:4],
            }
        )
        if len(candidates) >= 18:
            break
    return candidates


def load_review_rows() -> list[dict[str, Any]]:
    products = load_csv(PRODUCT_MASTER_CSV)
    rows = load_csv(MATCH_CSV)
    review_rows: list[dict[str, Any]] = []
    for row in rows:
        company_hints = company_candidates_from_text(row_company_text(row), products)
        if norm(row.get("matched_company")):
            company_hints.add(norm(row.get("matched_company")))
        candidates = build_candidates(row, products, company_hints)
        needs_user = row.get("decision") == "review" or (row.get("decision") == "skip_no_match" and bool(company_hints))
        if not needs_user:
            continue
        enriched = dict(row)
        enriched["candidate_products"] = candidates
        enriched["candidate_companies"] = sorted({item["company"] for item in candidates if item.get("company")})
        review_rows.append(enriched)
    return review_rows


def write_html(rows: list[dict[str, Any]]) -> Path:
    summary = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "rows": len(rows),
        "with_candidates": sum(1 for row in rows if row["candidate_products"]),
        "without_candidates": sum(1 for row in rows if not row["candidate_products"]),
        "by_reason": dict(Counter(row.get("review_reason") or row.get("decision") for row in rows)),
    }
    payload = json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False).replace("<", "\\u003c")
    html_doc = HTML_TEMPLATE.replace("__PAYLOAD__", payload)
    LATEST_HTML.write_text(html_doc, encoding="utf-8")
    return LATEST_HTML


HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NMPA 全球产品匹配审核</title>
  <style>
    :root { color-scheme: light; --bg:#eef2f6; --panel:#fff; --ink:#172033; --muted:#647183; --line:#d9e0e8; --soft:#f6f8fb; --accent:#176b87; --ok:#166534; --warn:#9a6a10; --bad:#a33b34; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--ink); font:14px/1.6 "Microsoft YaHei","PingFang SC","Segoe UI",Arial,sans-serif; }
    header { background:#fff; border-bottom:1px solid var(--line); padding:22px 28px 16px; }
    h1 { margin:0 0 8px; font-size:28px; letter-spacing:0; }
    p { margin:0; color:var(--muted); }
    .stats { display:flex; flex-wrap:wrap; gap:10px; margin-top:16px; }
    .stat { min-width:130px; border:1px solid var(--line); background:var(--soft); border-radius:8px; padding:10px 12px; }
    .stat b { display:block; font-size:22px; line-height:1.1; }
    .stat span { color:var(--muted); font-size:12px; }
    .notice { margin:14px 28px 0; border:1px solid #f0d38b; background:#fff7df; border-radius:8px; padding:12px 14px; color:#513a05; }
    .toolbar { display:grid; grid-template-columns:1fr .7fr .7fr auto auto; gap:10px; padding:14px 28px; background:#fff; border-bottom:1px solid var(--line); }
    input, select, textarea, button { min-height:38px; border:1px solid var(--line); border-radius:7px; background:#fff; color:var(--ink); font:inherit; }
    input, select, textarea { width:100%; padding:8px 10px; }
    textarea { min-height:74px; resize:vertical; }
    button { padding:8px 12px; cursor:pointer; font-weight:700; white-space:nowrap; }
    button.primary { background:var(--accent); color:#fff; border-color:var(--accent); }
    .layout { display:grid; grid-template-columns:390px minmax(0,1fr); gap:16px; padding:16px 28px 28px; }
    .list { display:grid; gap:10px; }
    .record { border:1px solid var(--line); border-radius:8px; background:#fff; padding:12px; cursor:pointer; }
    .record.active { border-color:var(--accent); box-shadow:0 0 0 2px #e7f3f6; }
    .record.done { border-color:#9bd3aa; background:#fbfffc; }
    .title { font-weight:800; line-height:1.4; }
    .meta { margin-top:6px; color:var(--muted); font-size:12px; line-height:1.45; }
    .badge { display:inline-flex; border-radius:999px; padding:3px 8px; font-size:12px; font-weight:700; background:#edf5f7; color:var(--accent); }
    .panel { border:1px solid var(--line); border-radius:8px; background:#fff; overflow:hidden; }
    .section { padding:16px; border-bottom:1px solid var(--line); }
    .section h2 { margin:0 0 8px; font-size:22px; letter-spacing:0; }
    .section h3 { margin:0 0 10px; font-size:16px; }
    .grid2 { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
    .box { border:1px solid var(--line); border-radius:8px; background:var(--soft); padding:12px; min-width:0; }
    .label { color:var(--muted); font-size:12px; font-weight:700; margin-bottom:5px; }
    .candidates { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:10px; }
    .candidate { border:1px solid var(--line); border-radius:8px; padding:10px; background:#fff; cursor:pointer; }
    .candidate.selected { border-color:var(--accent); box-shadow:0 0 0 2px #e7f3f6; }
    .candidate input { width:auto; min-height:auto; margin-right:7px; }
    .decision { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
    .full { grid-column:1 / -1; }
    .empty { padding:24px; border:1px dashed var(--line); border-radius:8px; background:#fff; text-align:center; color:var(--muted); }
    dialog { width:min(960px,calc(100vw - 32px)); border:1px solid var(--line); border-radius:10px; }
    dialog textarea { min-height:360px; }
    @media (max-width:1100px) { .toolbar,.layout,.grid2,.decision { grid-template-columns:1fr; } .full { grid-column:auto; } }
  </style>
</head>
<body>
  <header>
    <h1>NMPA 全球产品匹配：逐条做决定</h1>
    <p>每条 NMPA 注册记录都给出官方信息、同公司候选产品和你的三个选择：关联、不关联、新增产品。</p>
    <div class="stats">
      <div class="stat"><b id="total">0</b><span>待判断记录</span></div>
      <div class="stat"><b id="withCandidates">0</b><span>有候选产品</span></div>
      <div class="stat"><b id="withoutCandidates">0</b><span>无候选产品</span></div>
      <div class="stat"><b id="doneCount">0</b><span>已处理</span></div>
    </div>
  </header>
  <div class="notice"><b>你要做什么：</b>如果候选产品列表里有正确全球产品，就选中并选择“关联”。如果没有，选择“不关联”或“新增产品”，并填写你希望新增的品牌/产品名。</div>
  <div class="toolbar">
    <input id="search" placeholder="搜索公司、注册证号、产品名、适应证">
    <select id="decisionFilter"><option value="">全部处理状态</option><option value="undecided">未处理</option><option value="link">已选择关联</option><option value="no_link">不关联</option><option value="create">新增产品</option><option value="hold">暂缓</option></select>
    <select id="candidateFilter"><option value="">全部候选状态</option><option value="has">有候选产品</option><option value="none">无候选产品</option></select>
    <button class="primary" id="exportJson">导出决定 JSON</button>
    <button id="clearBtn">清空本页决定</button>
  </div>
  <main class="layout">
    <aside><div id="list" class="list"></div></aside>
    <section><div id="detail" class="panel"></div></section>
  </main>
  <dialog id="exportDialog">
    <h2>审核决定 JSON</h2>
    <textarea id="exportText" readonly></textarea>
    <div style="margin-top:10px;text-align:right"><button onclick="document.getElementById('exportDialog').close()">关闭</button></div>
  </dialog>
  <script>
    const DATA = __PAYLOAD__;
    const ROWS = DATA.rows;
    const SUMMARY = DATA.summary;
    const STORE_KEY = "nmpaProductMatchReview.v2";
    let state = JSON.parse(localStorage.getItem(STORE_KEY) || "{}");
    let active = ROWS[0]?.record_id || "";
    const $ = id => document.getElementById(id);
    function esc(v) { return String(v || "").replace(/[&<>"']/g, s => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[s])); }
    function key(row) { return row.record_id; }
    function saved(row) { return state[key(row)] || {}; }
    function save() { localStorage.setItem(STORE_KEY, JSON.stringify(state)); updateStats(); }
    function label(decision) { return ({link:"关联",no_link:"不关联",create:"新增产品",hold:"暂缓"}[decision] || "待判断"); }
    function hay(row) { return JSON.stringify(row).toLowerCase(); }
    function filteredRows() {
      const q = $("search").value.trim().toLowerCase();
      const df = $("decisionFilter").value;
      const cf = $("candidateFilter").value;
      return ROWS.filter(row => {
        const d = saved(row).decision || "undecided";
        if (q && !hay(row).includes(q)) return false;
        if (df && d !== df) return false;
        if (cf === "has" && !row.candidate_products.length) return false;
        if (cf === "none" && row.candidate_products.length) return false;
        return true;
      });
    }
    function renderList() {
      const rows = filteredRows();
      if (!rows.some(row => row.record_id === active)) active = rows[0]?.record_id || "";
      $("list").innerHTML = rows.map(row => {
        const s = saved(row);
        return `<article class="record ${row.record_id === active ? "active" : ""} ${s.decision ? "done" : ""}" data-id="${esc(row.record_id)}">
          <div class="title">${esc(row.nmpa_brand || row.nmpa_product_name || row.official_product_name)}</div>
          <div class="meta">${esc(row.certificate_no)} · ${esc(row.nmpa_registrant || row.nmpa_manufacturer_group)}</div>
          <div class="meta"><span class="badge">${row.candidate_products.length ? row.candidate_products.length + " 个候选产品" : "无候选产品"}</span> <span class="badge">${label(s.decision)}</span></div>
        </article>`;
      }).join("") || '<div class="empty">没有匹配的记录</div>';
      document.querySelectorAll(".record[data-id]").forEach(card => card.onclick = () => { active = card.dataset.id; render(); });
    }
    function renderDetail() {
      const row = ROWS.find(item => item.record_id === active);
      if (!row) { $("detail").innerHTML = '<div class="empty">请选择一条 NMPA 记录</div>'; return; }
      const s = saved(row);
      $("detail").innerHTML = `<div class="section">
        <h2>${esc(row.nmpa_brand || row.nmpa_product_name || row.official_product_name)}</h2>
        <p>${esc(row.certificate_no)} · ${esc(row.nmpa_registrant || row.nmpa_manufacturer_group)}</p>
      </div>
      <div class="section grid2">
        <div class="box"><div class="label">NMPA 官方产品名</div><div>${esc(row.official_product_name || row.nmpa_product_name)}</div><div class="meta">赛道：${esc(row.track)} · 来源：${esc(row.origin)}</div></div>
        <div class="box"><div class="label">官方适用范围 / 适应证</div><div>${esc(row.official_scope || "未提供")}</div></div>
      </div>
      <div class="section">
        <h3>可选择的全球产品</h3>
        ${row.candidate_products.length ? `<div class="candidates">${row.candidate_products.map(item => candidateHtml(row, item, s)).join("")}</div>` : '<div class="empty">没有找到同公司或同集团候选产品。你可以选择“不关联”，也可以选择“新增产品”。</div>'}
      </div>
      <div class="section">
        <h3>你的决定</h3>
        <div class="decision">
          <div><div class="label">处理方式</div><select id="decision"><option value="">待判断</option><option value="link">关联到选中的全球产品</option><option value="no_link">不关联现有全球产品</option><option value="create">新增全球产品线/产品</option><option value="hold">暂缓，需要更多资料</option></select></div>
          <div><div class="label">新增时归属公司</div><input id="newCompany" value="${esc(s.new_company || row.candidate_companies?.[0] || row.matched_company || "")}" placeholder="例如：Galderma"></div>
          <div><div class="label">新增品牌</div><input id="newBrand" value="${esc(s.new_brand || row.nmpa_brand || "")}" placeholder="例如：Restylane"></div>
          <div><div class="label">新增产品名</div><input id="newProduct" value="${esc(s.new_product || row.official_product_name || row.nmpa_product_name || "")}" placeholder="填写全球库应新增的产品名"></div>
          <div class="full"><div class="label">备注</div><textarea id="note" placeholder="写你为什么这样判断，或说明候选产品不够细、需要新增哪个产品族。">${esc(s.note || "")}</textarea></div>
        </div>
      </div>`;
      $("decision").value = s.decision || "";
      ["decision","newCompany","newBrand","newProduct","note"].forEach(id => $(id).oninput = () => saveDecision(row));
      document.querySelectorAll("[data-product-id]").forEach(card => card.onclick = () => {
        state[key(row)] = { ...saved(row), selected_product_id: card.dataset.productId, decision: "link", updated_at: new Date().toISOString() };
        save();
        render();
      });
    }
    function candidateHtml(row, item, s) {
      const selected = s.selected_product_id === item.product_id || (!s.selected_product_id && row.matched_product_id === item.product_id);
      return `<article class="candidate ${selected ? "selected" : ""}" data-product-id="${esc(item.product_id)}">
        <label><input type="radio" ${selected ? "checked" : ""}>${esc(item.company)} / ${esc(item.brand || item.product)}</label>
        <div class="meta">${esc(item.product)} · ${esc(item.product_id)}</div>
        <div class="meta">${esc(item.material_path || item.commercial_path || "未标注路径")}</div>
        <div class="meta">${esc((item.reasons || []).join("；"))}</div>
      </article>`;
    }
    function saveDecision(row) {
      state[key(row)] = {
        ...saved(row),
        decision: $("decision").value,
        new_company: $("newCompany").value.trim(),
        new_brand: $("newBrand").value.trim(),
        new_product: $("newProduct").value.trim(),
        note: $("note").value.trim(),
        updated_at: new Date().toISOString(),
      };
      save();
      renderList();
    }
    function updateStats() {
      $("total").textContent = SUMMARY.rows || ROWS.length;
      $("withCandidates").textContent = SUMMARY.with_candidates || 0;
      $("withoutCandidates").textContent = SUMMARY.without_candidates || 0;
      $("doneCount").textContent = ROWS.filter(row => saved(row).decision).length;
    }
    function exportDecisions() {
      const decisions = ROWS.map(row => ({
        record_id: row.record_id,
        certificate_no: row.certificate_no,
        nmpa_product_name: row.nmpa_product_name,
        nmpa_registrant: row.nmpa_registrant,
        ...saved(row),
      })).filter(row => row.decision || row.note || row.selected_product_id);
      $("exportText").value = JSON.stringify(decisions, null, 2);
      $("exportDialog").showModal();
    }
    function render() { renderList(); renderDetail(); updateStats(); }
    ["search","decisionFilter","candidateFilter"].forEach(id => $(id).oninput = render);
    $("exportJson").onclick = exportDecisions;
    $("clearBtn").onclick = () => { if (confirm("清空本页所有本地决定？")) { localStorage.removeItem(STORE_KEY); location.reload(); } };
    render();
  </script>
</body>
</html>
"""


def main() -> int:
    rows = load_review_rows()
    latest = write_html(rows)
    print(json.dumps({"latest": str(latest), "rows": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
