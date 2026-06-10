#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_DIR = ROOT / "data" / "audits"
INPUT = AUDIT_DIR / "product_gap_queue_latest.csv"
CSV_OUT = AUDIT_DIR / "product_gap_optimization_queue_latest.csv"
HTML_OUT = AUDIT_DIR / "product_gap_optimization_review_latest.html"
MD_OUT = AUDIT_DIR / "product_gap_optimization_summary_latest.md"


REGULATED_TRACKS = {"EBD", "Injectables", "Implants", "Consumables", "Surgical", "Diagnostics", "Regenerative"}


GROUPS = {
    "A_identity_scope": {
        "title": "A. 先做身份/范围判断",
        "summary": "产品身份、公司归属或收录范围可能还没完全闭合。数量很少，应优先处理。",
        "action": "人工确认：保留、排除、改公司或改分类。",
        "weight": 100,
    },
    "B_regulatory_leads": {
        "title": "B. 监管候选可复核",
        "summary": "已有 FDA / CE / MDR / 注册候选线索，但尚未提升为正式注册证据。",
        "action": "机器优先：只接受官方监管库、IFU、证书、公告机构或制造商文件；查不到则标未公开。",
        "weight": 90,
    },
    "C_official_url_leads": {
        "title": "C. 官网/产品页候选可挂载",
        "summary": "没有直接官网产品页，但已有候选官网、目录页或产品页线索。",
        "action": "机器复核候选 URL，确认是官方/授权页面后挂到产品或产品家族。",
        "weight": 80,
    },
    "D_spec_leads": {
        "title": "D. 规格/IFU 候选可挂载",
        "summary": "没有直接规格候选，但已有 A/B 级规格或文档线索。",
        "action": "机器复核 IFU、catalog、brochure、label，能落地的写入规格证据。",
        "weight": 75,
    },
    "E_indication_backfill": {
        "title": "E. 官方适应症可批量补强",
        "summary": "产品事实已核，且已有规格或注册证据，可从现有证据中抽取 intended use / indication。",
        "action": "机器抽取：从 FDA summary、IFU、官方说明书、注册长表中提取官方适应症；没有明确医疗适应症则标官方定位。",
        "weight": 65,
    },
    "F_registration_deepcheck": {
        "title": "F. 注册证据深查池",
        "summary": "属于较可能受监管的产品，但当前没有注册证据，也没有明确候选链接。",
        "action": "按重点公司/重点赛道批量查；若公开渠道没有证号，标未公开，不逐条卡住入库。",
        "weight": 45,
    },
    "G_low_evidence_enrichment": {
        "title": "G. 低优先资料补强",
        "summary": "产品已可用，但仍可补官网、规格、差异化说明等辅助信息。",
        "action": "低优先机器补强；不建议你逐条人工确认。",
        "weight": 25,
    },
    "H_closed_monitor": {
        "title": "H. 已闭合，仅保留观察",
        "summary": "四类核心证据大体齐全，或缺口不影响当前使用。",
        "action": "无需现在处理；只在专题深挖或新增证据出现时刷新。",
        "weight": 5,
    },
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def as_int(row: dict[str, str], key: str) -> int:
    try:
        return int(norm(row.get(key)) or 0)
    except ValueError:
        return 0


def issue_set(row: dict[str, str]) -> set[str]:
    return {part.strip() for part in norm(row.get("issues")).split("|") if part.strip()}


def choose_group(row: dict[str, str]) -> str:
    issues = issue_set(row)
    action = norm(row.get("recommended_next_action"))
    if {"master_unverified_seed", "material_subtrack_conflict"} & issues:
        return "A_identity_scope"
    if "Review regulator" in action:
        return "B_regulatory_leads"
    if "Review fuzzy official" in action:
        return "C_official_url_leads"
    if "Review A/B spec" in action:
        return "D_spec_leads"
    if "no_official_indication" in issues and as_int(row, "official_indication_rows") == 0 and (
        as_int(row, "direct_spec_candidates") > 0 or as_int(row, "registration_rows") > 0
    ):
        return "E_indication_backfill"
    if as_int(row, "registration_rows") == 0 and norm(row.get("track")) in REGULATED_TRACKS:
        return "F_registration_deepcheck"
    if as_int(row, "direct_official_urls") == 0 or as_int(row, "direct_spec_candidates") == 0:
        return "G_low_evidence_enrichment"
    return "H_closed_monitor"


def improvement_reason(row: dict[str, str], group: str) -> str:
    if group == "A_identity_scope":
        return "身份或范围未完全闭合，处理后可避免错误产品留在主库。"
    if group == "B_regulatory_leads":
        return "已有监管候选，转化成本低，能直接提高注册证据覆盖。"
    if group == "C_official_url_leads":
        return "已有候选官网/目录页，确认后可补产品页直连。"
    if group == "D_spec_leads":
        return "已有规格/IFU 候选，确认后可补规格证据。"
    if group == "E_indication_backfill":
        return "已有规格或注册资料，可从原文抽取官方适应症或官方用途。"
    if group == "F_registration_deepcheck":
        return "受监管属性较强，但缺少公开注册证据；适合按专题批量深查。"
    if group == "G_low_evidence_enrichment":
        return "辅助资料可更完整，但当前不影响产品事实。"
    return "当前无需处理，作为低频观察项。"


def work_mode(group: str) -> str:
    if group == "A_identity_scope":
        return "需要人工"
    if group in {"B_regulatory_leads", "C_official_url_leads", "D_spec_leads", "E_indication_backfill"}:
        return "机器可跑"
    if group == "F_registration_deepcheck":
        return "机器深查"
    return "观察"


def product_label(row: dict[str, str]) -> str:
    parts = [norm(row.get("brand")), norm(row.get("standard_product_name"))]
    return " / ".join(part for part in parts if part)


def esc(value: Any) -> str:
    return html.escape(norm(value), quote=True)


def row_score(row: dict[str, str], group: str) -> int:
    score = GROUPS[group]["weight"] + as_int(row, "gap_score")
    if norm(row.get("company_priority_rank")):
        score += 8
    if as_int(row, "lead_registration_url") or as_int(row, "mdr_ce_candidate_rows") > 0:
        score += 5
    return score


def load_rows() -> list[dict[str, str]]:
    with INPUT.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    output: list[dict[str, str]] = []
    for row in rows:
        group = choose_group(row)
        enriched = dict(row)
        enriched["optimization_group"] = group
        enriched["optimization_group_title"] = GROUPS[group]["title"]
        enriched["improvement_reason"] = improvement_reason(row, group)
        enriched["work_mode"] = work_mode(group)
        enriched["optimization_score"] = str(row_score(row, group))
        output.append(enriched)
    output.sort(key=lambda item: (-int(item["optimization_score"]), item["optimization_group"], item.get("company", ""), item.get("brand", "")))
    return output


def write_csv(rows: list[dict[str, str]]) -> None:
    fields = [
        "optimization_group",
        "optimization_group_title",
        "work_mode",
        "optimization_score",
        "company",
        "brand",
        "standard_product_name",
        "track",
        "form",
        "verification_status",
        "direct_official_urls",
        "fuzzy_official_urls",
        "direct_spec_candidates",
        "fuzzy_spec_candidates",
        "registration_rows",
        "official_indication_rows",
        "mdr_ce_candidate_rows",
        "lead_official_url",
        "lead_spec_url",
        "lead_registration_url",
        "issues",
        "improvement_reason",
        "recommended_next_action",
        "product_id",
        "seed_record_id",
    ]
    with CSV_OUT.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def badge(text: str, klass: str = "") -> str:
    return f'<span class="badge {klass}">{esc(text)}</span>'


def table_rows(rows: list[dict[str, str]]) -> str:
    if not rows:
        return '<p class="empty">本组暂无条目。</p>'
    lines = []
    for row in rows:
        links = []
        for key, label in [
            ("lead_official_url", "官网候选"),
            ("lead_spec_url", "规格候选"),
            ("lead_registration_url", "注册候选"),
        ]:
            url = norm(row.get(key))
            if url:
                links.append(f'<a href="{esc(url)}" target="_blank" rel="noreferrer">{label}</a>')
        link_html = " · ".join(links) if links else '<span class="muted">暂无直接链接</span>'
        evidence = " ".join(
            [
                badge(f"官网 {as_int(row, 'direct_official_urls')}", "ok" if as_int(row, "direct_official_urls") else "watch"),
                badge(f"规格 {as_int(row, 'direct_spec_candidates')}", "ok" if as_int(row, "direct_spec_candidates") else "watch"),
                badge(f"注册 {as_int(row, 'registration_rows')}", "ok" if as_int(row, "registration_rows") else "watch"),
                badge(f"适应症 {as_int(row, 'official_indication_rows')}", "ok" if as_int(row, "official_indication_rows") else "watch"),
            ]
        )
        lines.append(
            "<tr>"
            f"<td><strong>{esc(row.get('company'))}</strong><small>{esc(product_label(row))}</small></td>"
            f"<td>{badge(row.get('work_mode'), 'mode')} {badge(row.get('track'), 'track')}</td>"
            f"<td>{evidence}</td>"
            f"<td>{esc(row.get('improvement_reason'))}<small>{esc(row.get('recommended_next_action'))}</small></td>"
            f"<td>{link_html}</td>"
            "</tr>"
        )
    return "\n".join(lines)


def write_html(rows: list[dict[str, str]], generated_at: str) -> None:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["optimization_group"]].append(row)
    group_counts = {key: len(grouped.get(key, [])) for key in GROUPS}
    mode_counts = Counter(row["work_mode"] for row in rows)
    track_counts = Counter(row["track"] for row in rows if row.get("track"))
    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>产品资料可补强清单</title>
  <style>
    :root {{ --ink:#2b2723; --muted:#8d8178; --line:#ece5df; --ok:#2f6f63; --watch:#8b6a42; --soft:#fbf8f5; --brand:#d97757; }}
    body {{ margin:0; background:#f7f4ef; color:var(--ink); font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI","Microsoft YaHei",sans-serif; }}
    main {{ max-width:1280px; margin:0 auto; padding:32px 24px 56px; }}
    h1 {{ margin:0 0 8px; font-size:30px; }}
    h2 {{ margin:0; font-size:20px; }}
    p {{ margin:6px 0; color:var(--muted); }}
    .hero, details {{ background:white; border:1px solid var(--line); border-radius:14px; box-shadow:0 10px 30px rgba(58,45,34,.06); }}
    .hero {{ padding:24px; margin-bottom:18px; }}
    .cards {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin-top:18px; }}
    .card {{ background:var(--soft); border:1px solid var(--line); border-radius:12px; padding:14px; }}
    .num {{ display:block; font-size:30px; font-weight:900; color:var(--brand); }}
    details {{ margin:12px 0; overflow:hidden; }}
    summary {{ cursor:pointer; padding:18px 20px; list-style:none; display:flex; gap:12px; align-items:center; justify-content:space-between; }}
    summary::-webkit-details-marker {{ display:none; }}
    .count {{ color:var(--brand); font-weight:900; }}
    .body {{ padding:0 20px 20px; }}
    table {{ width:100%; border-collapse:collapse; background:white; }}
    th, td {{ text-align:left; vertical-align:top; padding:12px 10px; border-top:1px solid var(--line); }}
    th {{ color:var(--muted); font-size:12px; letter-spacing:.04em; }}
    td small {{ display:block; color:var(--muted); margin-top:3px; }}
    a {{ color:#226c83; text-decoration:none; font-weight:700; }}
    .badge {{ display:inline-flex; align-items:center; min-height:22px; padding:2px 8px; margin:2px 3px 2px 0; border-radius:999px; background:#f1ebe5; color:#6c625a; font-size:12px; font-weight:800; white-space:nowrap; }}
    .badge.ok {{ color:var(--ok); background:rgba(126,174,158,.16); }}
    .badge.watch {{ color:var(--watch); background:rgba(214,166,82,.14); }}
    .badge.mode {{ color:#7d4b34; background:rgba(217,119,87,.14); }}
    .badge.track {{ color:#315f78; background:rgba(92,145,170,.14); }}
    .muted {{ color:var(--muted); }}
    .empty {{ padding:18px; }}
    @media (max-width: 900px) {{ .cards {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} table {{ font-size:13px; }} }}
  </style>
</head>
<body>
<main>
  <section class="hero">
    <h1>产品资料可补强清单</h1>
    <p>生成时间：{esc(generated_at)}。这不是“未完成待办”，而是从 P3 观察池里拆出来的可优化资料。优先处理 A-D；E 可以机器批量抽取；F 适合专题深查；G/H 不建议人工逐条看。</p>
    <div class="cards">
      <div class="card"><span class="num">{len(rows)}</span><strong>总观察项</strong><p>P3 可补强/观察池</p></div>
      <div class="card"><span class="num">{sum(group_counts[k] for k in ['A_identity_scope','B_regulatory_leads','C_official_url_leads','D_spec_leads'])}</span><strong>马上值得做</strong><p>身份、监管、官网、规格候选</p></div>
      <div class="card"><span class="num">{group_counts['E_indication_backfill']}</span><strong>适应症可批量补</strong><p>已有规格或注册基础</p></div>
      <div class="card"><span class="num">{group_counts['F_registration_deepcheck']}</span><strong>注册深查池</strong><p>无候选，按专题查</p></div>
    </div>
    <p>工作模式：{", ".join(f"{k} {v}" for k, v in mode_counts.items())}</p>
    <p>赛道分布：{", ".join(f"{k} {v}" for k, v in track_counts.most_common(10))}</p>
  </section>
"""
    for key, meta in GROUPS.items():
        items = grouped.get(key, [])
        open_attr = " open" if key in {"A_identity_scope", "B_regulatory_leads", "C_official_url_leads", "D_spec_leads"} else ""
        html_doc += f"""
  <details{open_attr}>
    <summary>
      <div>
        <h2>{esc(meta['title'])}</h2>
        <p>{esc(meta['summary'])}</p>
      </div>
      <span class="count">{len(items)} 条</span>
    </summary>
    <div class="body">
      <p><strong>建议动作：</strong>{esc(meta['action'])}</p>
      <table>
        <thead>
          <tr><th>产品</th><th>工作模式</th><th>当前证据</th><th>为什么可改善</th><th>候选链接</th></tr>
        </thead>
        <tbody>{table_rows(items)}</tbody>
      </table>
    </div>
  </details>
"""
    html_doc += """
</main>
</body>
</html>
"""
    HTML_OUT.write_text(html_doc, encoding="utf-8")


def write_md(rows: list[dict[str, str]], generated_at: str) -> None:
    grouped = Counter(row["optimization_group"] for row in rows)
    lines = [
        "# Product Gap Optimization Summary",
        "",
        f"Generated: {generated_at}",
        "",
        "| Group | Count | Meaning | Action |",
        "|---|---:|---|---|",
    ]
    for key, meta in GROUPS.items():
        lines.append(f"| {meta['title']} | {grouped.get(key, 0)} | {meta['summary']} | {meta['action']} |")
    lines += [
        "",
        f"- HTML: `{HTML_OUT.relative_to(ROOT)}`",
        f"- CSV: `{CSV_OUT.relative_to(ROOT)}`",
    ]
    MD_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not INPUT.exists():
        raise SystemExit(f"Missing input: {INPUT}")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().isoformat(timespec="seconds")
    rows = load_rows()
    write_csv(rows)
    write_html(rows, generated_at)
    write_md(rows, generated_at)
    print(
        json.dumps(
            {
                "rows": len(rows),
                "groups": dict(Counter(row["optimization_group"] for row in rows)),
                "html": str(HTML_OUT),
                "csv": str(CSV_OUT),
                "summary": str(MD_OUT),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
