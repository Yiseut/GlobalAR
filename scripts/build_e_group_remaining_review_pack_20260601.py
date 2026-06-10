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

UNCERTAIN = AUDIT_DIR / "e_group_indication_extraction_uncertain_latest.csv"
OUT_CSV = AUDIT_DIR / "e_group_remaining_review_pack_latest.csv"
OUT_HTML = AUDIT_DIR / "e_group_remaining_review_pack_latest.html"
OUT_JSON = AUDIT_DIR / "e_group_remaining_review_pack_latest.json"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def group_for(reason: str) -> tuple[str, str, str]:
    if reason == "not_explicit_enough":
        return (
            "A_not_explicit_user_rewrite",
            "可人工改写确认",
            "现有文本像宣传语，不能直接当正式适应症；需要人工提炼成正式用途。",
        )
    if reason == "no_clear_official_indication_phrase_in_existing_manual_evidence":
        return (
            "B_need_new_official_ifu_or_product_page",
            "需要补新官网/IFU链接",
            "当前证据里没有可抽取的适应症原文；不建议继续从这条旧证据硬抽。",
        )
    if reason.startswith("candidate_text_mentions_other_brand:"):
        return (
            "C_bad_url_mentions_other_brand",
            "丢弃低质URL/竞品串词",
            "候选文本提到了其他品牌，多半是分销页、SEO串词或错抓页面；不落库，后续换官方IFU/产品页。",
        )
    if reason == "possible_wrong_clinical_path":
        return (
            "D_possible_out_of_scope",
            "临床路径可疑，优先确认排除",
            "现有文本指向非医美或泛外科临床路径；需要按范围规则确认保留或排除。",
        )
    return (
        "E_other_quality_blocker",
        "其他质量拦截",
        "文本不完整、目标不明确或来源域名不合格；先不落库。",
    )


def short(value: str, limit: int = 280) -> str:
    value = " ".join(clean(value).split())
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "..."


def main() -> None:
    rows = read_csv(UNCERTAIN)
    out_rows: list[dict[str, str]] = []
    for row in rows:
        group, title, recommendation = group_for(clean(row.get("reason")))
        out_rows.append(
            {
                "action_group": group,
                "action_title_cn": title,
                "recommended_action_cn": recommendation,
                "reason": clean(row.get("reason")),
                "seed_record_id": clean(row.get("seed_record_id")),
                "company": clean(row.get("company")),
                "brand": clean(row.get("brand")),
                "standard_product_name": clean(row.get("standard_product_name")),
                "track": clean(row.get("track")),
                "form": clean(row.get("form")),
                "source_type": clean(row.get("source_type")),
                "source_url": clean(row.get("source_url")),
                "evidence_title": clean(row.get("evidence_title")),
                "candidate_text": clean(row.get("extracted_text") or row.get("source_evidence_excerpt")),
            }
        )

    fields = [
        "action_group",
        "action_title_cn",
        "recommended_action_cn",
        "reason",
        "seed_record_id",
        "company",
        "brand",
        "standard_product_name",
        "track",
        "form",
        "source_type",
        "source_url",
        "evidence_title",
        "candidate_text",
    ]
    with OUT_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)

    group_counts = Counter(row["action_group"] for row in out_rows)
    reason_counts = Counter(row["reason"] for row in out_rows)
    summary = {
        "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
        "rows": len(out_rows),
        "group_counts": dict(group_counts),
        "reason_top": dict(reason_counts.most_common(20)),
        "csv": str(OUT_CSV),
        "html": str(OUT_HTML),
    }
    OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    sections: list[str] = []
    for group in ["A_not_explicit_user_rewrite", "D_possible_out_of_scope", "C_bad_url_mentions_other_brand", "B_need_new_official_ifu_or_product_page", "E_other_quality_blocker"]:
        group_rows = [row for row in out_rows if row["action_group"] == group]
        if not group_rows:
            continue
        title = group_rows[0]["action_title_cn"]
        recommendation = group_rows[0]["recommended_action_cn"]
        table_rows = []
        for row in group_rows[:80]:
            product = " / ".join(part for part in [row["brand"], row["standard_product_name"]] if part)
            table_rows.append(
                "<tr>"
                f"<td>{html.escape(row['seed_record_id'])}</td>"
                f"<td>{html.escape(row['company'])}</td>"
                f"<td>{html.escape(product)}</td>"
                f"<td>{html.escape(row['reason'])}</td>"
                f"<td>{html.escape(short(row['candidate_text']))}</td>"
                f"<td><a href=\"{html.escape(row['source_url'])}\">source</a></td>"
                "</tr>"
            )
        sections.append(
            f"<section><h2>{html.escape(title)} <span>{len(group_rows)}</span></h2>"
            f"<p>{html.escape(recommendation)}</p>"
            "<table><thead><tr><th>ID</th><th>公司</th><th>产品</th><th>原因</th><th>候选文本</th><th>链接</th></tr></thead>"
            f"<tbody>{''.join(table_rows)}</tbody></table></section>"
        )

    OUT_HTML.write_text(
        """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>E组剩余适应症核验包</title>
  <style>
    body{font-family:Arial,'Microsoft YaHei',sans-serif;margin:0;background:#faf8f5;color:#2b2926}
    header{padding:28px 36px;background:#fff;border-bottom:1px solid #eadfd7}
    h1{margin:0 0 8px;font-size:26px}
    .meta{color:#756d66}
    main{padding:22px 36px}
    .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:22px}
    .card{background:#fff;border:1px solid #eadfd7;border-radius:8px;padding:14px}
    .num{font-size:28px;font-weight:700;color:#bd5b3d}
    section{background:#fff;border:1px solid #eadfd7;border-radius:8px;margin:18px 0;padding:16px}
    h2{font-size:20px;margin:0 0 8px}
    h2 span{color:#bd5b3d}
    p{margin:0 0 14px;color:#645e58}
    table{width:100%;border-collapse:collapse;font-size:13px}
    th,td{border-top:1px solid #eee5dd;padding:8px;text-align:left;vertical-align:top}
    th{background:#fbf4ef}
    td:nth-child(5){max-width:520px}
    a{color:#9b4a32}
  </style>
</head>
<body>
"""
        + f"<header><h1>E组剩余适应症核验包</h1><div class=\"meta\">生成时间：{html.escape(summary['generated_at'])}；总计 {len(out_rows)} 条。每组最多预览 80 条，完整清单见 CSV。</div></header>"
        + "<main><div class=\"cards\">"
        + "".join(
            f"<div class=\"card\"><div class=\"num\">{count}</div><div>{html.escape(next(row['action_title_cn'] for row in out_rows if row['action_group']==group))}</div></div>"
            for group, count in group_counts.most_common()
        )
        + "</div>"
        + "".join(sections)
        + "</main></body></html>",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
