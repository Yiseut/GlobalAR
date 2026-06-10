"""Aggregate evidence-pipeline tables into the v3 Evidence Library page feed.

This is the operations-side view — tracks data quality / backfill progress.
Output: web/v3/v3-evidence.js → window.V3_EVIDENCE_DATA with:

  summary               — totals by table (registration / indication / spec / etc.)
  funnel                — planned → candidate → collected → reviewed → merged counts
  rows                  — unified evidence list (search/filter/sort target)
                          ~1,500 rows from 5 evidence tables
  coverage              — companies × evidence-type completeness heatmap
  review_queue          — top pending review items
  source_lane_mix       — distribution by source_lane
  findings              — derived ops findings (backfill priorities)
"""
from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "global_aesthetics.db"
OUT = ROOT / "web" / "v3" / "v3-evidence.js"


def clean(v) -> str:
    if v is None:
        return ""
    return str(v).strip()


def short(v, n=80) -> str:
    s = clean(v)
    return s if len(s) <= n else s[:n - 1] + "…"


def main() -> None:
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row

    # ---- Bulk counts -------------------------------------------------------
    counts = {}
    for t in ("registration_evidence", "official_indication_evidence",
              "product_specification_evidence", "company_official_source_evidence",
              "evidence_staging", "verification_queue", "company_background_evidence",
              "briefing_update_candidates", "briefing_verified_update_events",
              "company_official_source_plan", "mdr_ce_search_plan"):
        try:
            counts[t] = conn.execute(f"SELECT COUNT(*) FROM `{t}`").fetchone()[0]
        except sqlite3.OperationalError:
            counts[t] = 0

    # ---- Build unified evidence rows --------------------------------------
    rows = []

    # registration_evidence
    for r in conn.execute(
        "SELECT id, company, brand, regulator, jurisdiction, regulatory_pathway, "
        "approval_date, registration_no, registered_name, intended_use, "
        "evidence_title, source_url, review_status, confidence "
        "FROM registration_evidence ORDER BY approval_date DESC"
    ):
        # data_status flag for v3 visual markers:
        #   "registered_name_missing"  → Tier 1 oxblood chip (?)
        #   "indication_not_public"    → Tier 2 暗号 (5px 暗红点)
        #   "complete"                 → no marker
        reg_name = clean(r["registered_name"])
        intended = clean(r["intended_use"]).lower()
        if not reg_name:
            data_status = "registered_name_missing"
        elif "unavailable_verified" in intended:
            data_status = "indication_not_public"
        else:
            data_status = "complete"
        rows.append({
            "type": "registration",
            "id":   f"reg-{r['id']}",
            "company": clean(r["company"]),
            "brand":   clean(r["brand"]),
            "title":   short(r["evidence_title"] or r["registration_no"], 110),
            "lane":    clean(r["regulator"]),
            "scope":   clean(r["jurisdiction"]),
            "pathway": clean(r["regulatory_pathway"]),
            "date":    clean(r["approval_date"])[:10],
            "url":     clean(r["source_url"]),
            "status":  clean(r["review_status"]) or "—",
            "confidence": clean(r["confidence"]),
            "registered_name": reg_name,
            "data_status": data_status,
        })

    # official_indication_evidence
    for r in conn.execute(
        "SELECT id, company, brand, product, country, regulator, pathway, year, "
        "indication, source_url, source_label, confidence "
        "FROM official_indication_evidence ORDER BY id DESC"
    ):
        rows.append({
            "type": "indication",
            "id":   f"ind-{r['id']}",
            "company": clean(r["company"]),
            "brand":   clean(r["brand"]),
            "title":   short(f'{r["product"]} · {r["indication"]}', 110),
            "lane":    clean(r["regulator"]),
            "scope":   clean(r["country"]),
            "pathway": clean(r["pathway"]),
            "date":    clean(r["year"]),
            "url":     clean(r["source_url"]),
            "status":  "approved",
            "confidence": clean(r["confidence"]),
        })

    # evidence_staging (pending review)
    for r in conn.execute(
        "SELECT id, company, brand, jurisdiction, evidence_type, title, url, "
        "captured_at, review_status, confidence, source_lane, source_key "
        "FROM evidence_staging ORDER BY captured_at DESC"
    ):
        rows.append({
            "type":  "staging",
            "id":    f"stg-{r['id']}",
            "company": clean(r["company"]),
            "brand":   clean(r["brand"]),
            "title":   short(r["title"] or r["evidence_type"], 110),
            "lane":    clean(r["source_lane"]) or clean(r["source_key"]),
            "scope":   clean(r["jurisdiction"]),
            "pathway": clean(r["evidence_type"]),
            "date":    clean(r["captured_at"])[:10],
            "url":     clean(r["url"]),
            "status":  clean(r["review_status"]),
            "confidence": clean(r["confidence"]),
        })

    # company_background_evidence
    for r in conn.execute(
        "SELECT id, company, fact_type, field_name, field_value, source_name, "
        "source_url, captured_at, review_status, confidence "
        "FROM company_background_evidence ORDER BY id DESC"
    ):
        rows.append({
            "type":  "background",
            "id":    f"bkg-{r['id']}",
            "company": clean(r["company"]),
            "brand":   "",
            "title":   short(f'{r["fact_type"]} · {r["field_name"]} = {r["field_value"]}', 110),
            "lane":    clean(r["source_name"]),
            "scope":   "",
            "pathway": clean(r["fact_type"]),
            "date":    clean(r["captured_at"])[:10],
            "url":     clean(r["source_url"]),
            "status":  clean(r["review_status"]),
            "confidence": clean(r["confidence"]),
        })

    # briefing_update_candidates (recent industry events)
    for r in conn.execute(
        "SELECT candidate_id, event_type, article_date, company, brand, product_name, "
        "market_or_jurisdiction, article_url, status, confidence_score "
        "FROM briefing_update_candidates ORDER BY article_date DESC LIMIT 200"
    ):
        rows.append({
            "type":  "briefing",
            "id":    f"brf-{r['candidate_id']}",
            "company": clean(r["company"]),
            "brand":   clean(r["brand"]),
            "title":   short(f'{r["product_name"] or ""} · {r["event_type"]}', 110),
            "lane":    "briefing",
            "scope":   clean(r["market_or_jurisdiction"]),
            "pathway": clean(r["event_type"]),
            "date":    clean(r["article_date"])[:10],
            "url":     clean(r["article_url"]),
            "status":  clean(r["status"]),
            "confidence": clean(r["confidence_score"]),
        })

    # Top 200 official_source_evidence (sample — full set is 27K)
    for r in conn.execute(
        "SELECT evidence_id, company, brand, query_type, query, url, captured_at, "
        "source_key, confidence "
        "FROM company_official_source_evidence "
        "WHERE captured_at IS NOT NULL "
        "ORDER BY captured_at DESC LIMIT 200"
    ):
        rows.append({
            "type":  "official_source",
            "id":    f"src-{r['evidence_id']}",
            "company": clean(r["company"]),
            "brand":   clean(r["brand"]),
            "title":   short(r["query"] or r["query_type"], 110),
            "lane":    clean(r["source_key"]),
            "scope":   "",
            "pathway": clean(r["query_type"]),
            "date":    clean(r["captured_at"])[:10],
            "url":     clean(r["url"]),
            "status":  "collected",
            "confidence": clean(r["confidence"]),
        })

    # ---- Source-lane mix --------------------------------------------------
    lane_mix = Counter(r["lane"] for r in rows if r["lane"]).most_common(12)
    type_mix = Counter(r["type"] for r in rows).most_common()

    # ---- Funnel — pipeline state -----------------------------------------
    funnel = [
        {"label": "Planned", "label_zh": "搜寻计划",  "n": counts["company_official_source_plan"] + counts["mdr_ce_search_plan"]},
        {"label": "Candidate", "label_zh": "候选证据", "n": counts["evidence_staging"] + counts["briefing_update_candidates"]},
        {"label": "Collected", "label_zh": "已采集",   "n": counts["company_official_source_evidence"] + counts["product_specification_evidence"]},
        {"label": "Reviewed",  "label_zh": "已审核",   "n": counts["briefing_verified_update_events"] + 22},  # 22 = approved evidence_staging
        {"label": "Merged",    "label_zh": "已合并",   "n": counts["registration_evidence"] + counts["official_indication_evidence"] + counts["company_background_evidence"]},
    ]

    # ---- Company coverage heatmap ----
    # For each company, count evidence in 4 buckets: capital / portfolio / regulatory / indication
    company_cov = defaultdict(lambda: defaultdict(int))
    for r in conn.execute("SELECT company FROM company_background_evidence"):
        if r["company"]: company_cov[r["company"]]["capital"] += 1
    for r in conn.execute("SELECT company FROM company_official_source_evidence WHERE captured_at IS NOT NULL"):
        if r["company"]: company_cov[r["company"]]["portfolio"] += 1
    for r in conn.execute("SELECT company FROM registration_evidence"):
        if r["company"]: company_cov[r["company"]]["regulatory"] += 1
    for r in conn.execute("SELECT company FROM official_indication_evidence"):
        if r["company"]: company_cov[r["company"]]["indication"] += 1

    # Top 12 companies by total evidence
    company_totals = sorted(
        company_cov.items(),
        key=lambda kv: -sum(kv[1].values())
    )[:12]
    coverage_rows = []
    for company, buckets in company_totals:
        total = sum(buckets.values())
        coverage_rows.append({
            "company": company,
            "capital":    buckets.get("capital", 0),
            "portfolio":  buckets.get("portfolio", 0),
            "regulatory": buckets.get("regulatory", 0),
            "indication": buckets.get("indication", 0),
            "total": total,
        })

    # ---- Review queue — top pending items -------------------------------
    queue = []
    for r in conn.execute(
        "SELECT id, priority_rank, company, fact_group, target_label, "
        "source_lane, status, evidence_count, query "
        "FROM verification_queue WHERE status IN ('needs_review','queued','pending') "
        "ORDER BY priority_rank ASC LIMIT 40"
    ):
        queue.append({
            "id": r["id"],
            "priority": r["priority_rank"] or 999,
            "company": clean(r["company"]),
            "fact_group": clean(r["fact_group"]),
            "target": clean(r["target_label"]),
            "lane": clean(r["source_lane"]),
            "status": clean(r["status"]),
            "evidence_count": r["evidence_count"] or 0,
            "query": short(r["query"], 90),
        })

    conn.close()

    # ---- Findings ----
    total_pending = counts["evidence_staging"] + counts["verification_queue"]
    pct_collected_unmerged = round(
        100 * (counts["company_official_source_evidence"] - counts["registration_evidence"] - counts["official_indication_evidence"])
        / max(1, counts["company_official_source_evidence"]),
        1,
    )
    biggest_gap_company = ""
    biggest_gap_zero = 0
    for company, buckets in company_cov.items():
        zeros = sum(1 for k in ("capital", "portfolio", "regulatory", "indication") if buckets.get(k, 0) == 0)
        if zeros > biggest_gap_zero:
            biggest_gap_zero = zeros
            biggest_gap_company = company

    findings = [
        {
            "stamp": "Ops · 01",
            "lead": "<em>{0}</em> 条证据等审 + 验证。".format(total_pending),
            "num_pair": {"num": total_pending, "unit": "items pending"},
            "body": "evidence_staging 有 <em>{s}</em> 条候选证据待 review；verification_queue 有 <em>{q}</em> 条事实组待验证。审核积压决定了下一批数据 backfill 的吞吐量。".format(
                s=counts["evidence_staging"], q=counts["verification_queue"],
            ),
            "wash": "w-rose-deep",
        },
        {
            "stamp": "Ops · 02",
            "lead": "采集 ↔ 合并存在 <em>{0}%</em> 的 gap。".format(pct_collected_unmerged),
            "num_pair": {"num": "{0}%".format(pct_collected_unmerged), "unit": "collected but not merged"},
            "body": "已采集 <em>{c}</em> 条 official_source_evidence，但只有 <em>{m}</em> 条 registration_evidence + <em>{i}</em> 条 indication_evidence 进入 master。这个 gap 是「我们找到了但还没消化的数据」 — 优化 staging → master 的合并流程是 ROI 最高的工作。".format(
                c=counts["company_official_source_evidence"],
                m=counts["registration_evidence"],
                i=counts["official_indication_evidence"],
            ),
            "wash": "w-apricot",
        },
        {
            "stamp": "Ops · 03",
            "lead": "下一轮 backfill 优先补 indication + EBD 510(k)。",
            "num_pair": {"num": "82 → 200+", "unit": "indication backfill target"},
            "body": "official_indication_evidence 仅 <em>82</em> 条 / 覆盖 4.1% 产品。EBD 整个赛道几乎没有适应症证据。下一轮采集应优先用 FDA 510(k) Summary 提取 EBD intended use 字段。company_background_evidence 也仅 <em>52</em> 条 — 资本验证侧也欠债。",
            "wash": "w-plum",
        },
    ]

    payload = {
        "summary": {
            "total_evidence_rows":  len(rows),
            "registration":         counts["registration_evidence"],
            "indication":           counts["official_indication_evidence"],
            "official_source":      counts["company_official_source_evidence"],
            "product_spec":         counts["product_specification_evidence"],
            "staging":              counts["evidence_staging"],
            "verification_queue":   counts["verification_queue"],
            "background":           counts["company_background_evidence"],
            "briefing_candidates":  counts["briefing_update_candidates"],
            "merged_briefings":     counts["briefing_verified_update_events"],
            "search_plans":         counts["company_official_source_plan"] + counts["mdr_ce_search_plan"],
            "pending_total":        total_pending,
        },
        "rows": rows,
        "funnel": funnel,
        "lane_mix": [{"name": n, "n": c} for n, c in lane_mix],
        "type_mix": [{"name": n, "n": c} for n, c in type_mix],
        "coverage": coverage_rows,
        "review_queue": queue,
        "findings": findings,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = (
        "// auto-generated by scripts/_v3_build_evidence.py — do not hand-edit\n"
        f"// {len(rows)} unified rows from 5 evidence tables\n"
        f"window.V3_EVIDENCE_DATA = {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))};\n"
    )
    OUT.write_text(js, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} · {len(rows)} unified rows · {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
