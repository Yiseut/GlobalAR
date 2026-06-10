#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

REVIEW_PACK = AUDIT_DIR / "e_group_remaining_review_pack_latest.csv"
OUT_CSV = AUDIT_DIR / "e_group_reacquire_official_source_queue_latest.csv"
OUT_HTML = AUDIT_DIR / "e_group_reacquire_official_source_queue_latest.html"
OUT_JSON = AUDIT_DIR / "e_group_reacquire_official_source_queue_latest.json"

REACQUIRE_GROUPS = {
    "A_not_explicit_user_rewrite",
    "B_need_new_official_ifu_or_product_page",
    "C_bad_url_mentions_other_brand",
    "E_other_quality_blocker",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def source_policy(row: dict[str, str]) -> tuple[str, str]:
    group = clean(row.get("action_group"))
    reason = clean(row.get("reason"))
    if group == "A_not_explicit_user_rewrite":
        return "reacquire_official_ifu_or_brochure", "现有文字已经不足以安全改写；不再要求人工硬读，统一换取 IFU、Brochure、说明书、510(k) Summary 或更明确的官方产品页。"
    if group == "C_bad_url_mentions_other_brand":
        return "reacquire_official_ifu_or_brochure", "候选文本提到其他品牌；旧 URL 视为分销/SEO 引流页，不落库，导回 IFU/Brochure/510(k) 官方源任务池。"
    if reason == "incomplete_indication_text":
        return "reacquire_official_ifu_or_brochure", "候选文本在 indicated/intended for 处截断；旧 URL 不落库，优先找完整 IFU/Brochure/510(k) Summary。"
    if group == "B_need_new_official_ifu_or_product_page":
        return "reacquire_official_ifu_or_brochure", "现有证据没有可抽取适应症原文；优先补官方 IFU、Brochure、说明书、510(k) Summary 或厂商 PDF。"
    return "reacquire_official_ifu_or_brochure", "现有链接质量不足；优先补 IFU/Brochure/510(k) 官方源。"


def query_for(row: dict[str, str]) -> str:
    company = clean(row.get("company"))
    brand = clean(row.get("brand"))
    product = clean(row.get("standard_product_name"))
    base = " ".join(part for part in [company, brand, product] if part)
    track = clean(row.get("track")).lower()
    if "ebd" in track:
        return f'"{base}" (IFU OR "Instructions for Use" OR brochure OR "510(k) Summary") filetype:pdf'
    if "inject" in track or "regenerative" in track:
        return f'"{base}" (IFU OR "Instructions for Use" OR brochure OR SSCP OR "intended use") filetype:pdf'
    return f'"{base}" (IFU OR "Instructions for Use" OR brochure OR "intended use") filetype:pdf'


def short(value: str, limit: int = 220) -> str:
    value = " ".join(clean(value).split())
    return value if len(value) <= limit else value[: limit - 1] + "..."


def main() -> None:
    rows = read_csv(REVIEW_PACK)
    out_rows: list[dict[str, str]] = []
    for row in rows:
        if clean(row.get("action_group")) not in REACQUIRE_GROUPS:
            continue
        action, note = source_policy(row)
        out_rows.append(
            {
                "reacquire_action": action,
                "note_cn": note,
                "seed_record_id": clean(row.get("seed_record_id")),
                "company": clean(row.get("company")),
                "brand": clean(row.get("brand")),
                "standard_product_name": clean(row.get("standard_product_name")),
                "track": clean(row.get("track")),
                "form": clean(row.get("form")),
                "old_reason": clean(row.get("reason")),
                "old_url_to_discard_or_deprioritize": clean(row.get("source_url")),
                "source_priority": "1_IFU_or_instructions_for_use_pdf; 2_brochure_or_catalog_pdf; 3_FDA_510k_summary_or_regulator_record; 4_official_product_page_only_if_pdf_unavailable",
                "suggested_query": query_for(row),
                "candidate_text": clean(row.get("candidate_text")),
            }
        )

    fields = [
        "reacquire_action",
        "note_cn",
        "seed_record_id",
        "company",
        "brand",
        "standard_product_name",
        "track",
        "form",
        "old_reason",
        "old_url_to_discard_or_deprioritize",
        "source_priority",
        "suggested_query",
        "candidate_text",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    action_counts = Counter(row["reacquire_action"] for row in out_rows)
    summary = {
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "rows": len(out_rows),
        "action_counts": dict(action_counts),
        "csv": str(OUT_CSV),
        "html": str(OUT_HTML),
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    preview_rows = []
    for row in out_rows[:160]:
        product = " / ".join(part for part in [row["brand"], row["standard_product_name"]] if part)
        preview_rows.append(
            "<tr>"
            f"<td>{html.escape(row['reacquire_action'])}</td>"
            f"<td>{html.escape(row['seed_record_id'])}</td>"
            f"<td>{html.escape(row['company'])}</td>"
            f"<td>{html.escape(product)}</td>"
            f"<td>{html.escape(row['old_reason'])}</td>"
            f"<td>{html.escape(row['source_priority'])}</td>"
            f"<td>{html.escape(short(row['suggested_query']))}</td>"
            "</tr>"
        )

    OUT_HTML.write_text(
        """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>E组官方源重新获取队列</title>
  <style>
    body{font-family:Arial,'Microsoft YaHei',sans-serif;margin:0;background:#faf8f5;color:#2b2926}
    header{padding:28px 36px;background:#fff;border-bottom:1px solid #eadfd7}
    h1{margin:0 0 8px;font-size:26px}
    main{padding:22px 36px}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px;margin-bottom:22px}
    .card{background:#fff;border:1px solid #eadfd7;border-radius:8px;padding:14px}
    .num{font-size:28px;font-weight:700;color:#bd5b3d}
    table{width:100%;border-collapse:collapse;background:#fff;border:1px solid #eadfd7;border-radius:8px;overflow:hidden;font-size:13px}
    th,td{border-top:1px solid #eee5dd;padding:8px;text-align:left;vertical-align:top}
    th{background:#fbf4ef}
  </style>
</head>
<body>
"""
        + f"<header><h1>E组官方源重新获取队列</h1><div>生成时间：{html.escape(summary['generated_at'])}；总计 {len(out_rows)} 条。当前旧 URL 不直接落库。</div></header>"
        + "<main><div class=\"cards\">"
        + "".join(f"<div class=\"card\"><div class=\"num\">{count}</div><div>{html.escape(action)}</div></div>" for action, count in action_counts.most_common())
        + "</div><table><thead><tr><th>动作</th><th>ID</th><th>公司</th><th>产品</th><th>旧原因</th><th>来源优先级</th><th>建议检索式</th></tr></thead><tbody>"
        + "".join(preview_rows)
        + "</tbody></table></main></body></html>",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
