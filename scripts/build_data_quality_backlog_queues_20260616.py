#!/usr/bin/env python3
"""Build actionable review queues for known non-blocking data-quality gaps."""

from __future__ import annotations

import csv
import json
import re
import sqlite3
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
DB_PATH = DATA_DIR / "global_aesthetics.db"

CST = timezone(timedelta(hours=8))
DATE_TAG = datetime.now(CST).strftime("%Y%m%d")


ENTITY_FIELDS = [
    "queue_id",
    "priority",
    "source_table",
    "source_row_key",
    "issue_type",
    "entity_name",
    "listed_entity_name",
    "current_company_id",
    "stock_code",
    "exchange",
    "ticker_symbol",
    "listing_country",
    "sec_cik",
    "review_status",
    "candidate_company_id",
    "candidate_company_name",
    "candidate_match_rule",
    "suggested_action",
    "owner_module",
    "source_url",
    "notes",
    "generated_at",
]

REGISTRATION_FIELDS = [
    "queue_id",
    "priority",
    "source_table",
    "source_row_key",
    "triage_bucket",
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "jurisdiction",
    "regulator",
    "regulatory_pathway",
    "status",
    "registration_no",
    "approval_date",
    "registered_name",
    "source_type",
    "source_key",
    "source_url",
    "evidence_title",
    "review_status",
    "confidence",
    "suggested_action",
    "generated_at",
]

AESTHETICS_REVENUE_FIELDS = [
    "queue_id",
    "priority",
    "company_id",
    "company",
    "stock_code",
    "ownership",
    "status",
    "revenue_usd_m",
    "revenue_year",
    "gross_margin_pct",
    "market_cap_usd_m",
    "financial_review_status",
    "financial_source_url",
    "issue_type",
    "expected_source",
    "suggested_action",
    "generated_at",
]


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def is_blank(value: Any) -> bool:
    return not norm(value)


def normalized_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", norm(value).lower())


def parse_float(value: Any) -> float | None:
    text = norm(value).replace(",", "")
    if not text or text.lower() in {"unavailable_verified", "not_disclosed", "na", "n/a"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def generated_at() -> str:
    return datetime.now(CST).replace(microsecond=0).isoformat()


def table_rows(cur: sqlite3.Cursor, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    cur.execute(sql, params)
    return [dict(row) for row in cur.fetchall()]


def company_master_indexes(cur: sqlite3.Cursor) -> dict[str, dict[str, dict[str, Any]]]:
    rows = table_rows(
        cur,
        """
        SELECT company_id, canonical_name, stock_code, ticker_symbol
        FROM company_master
        """,
    )
    by_name: dict[str, dict[str, Any]] = {}
    by_stock: dict[str, dict[str, Any]] = {}
    by_ticker: dict[str, dict[str, Any]] = {}
    for row in rows:
        name_key = normalized_key(row.get("canonical_name"))
        stock_key = norm(row.get("stock_code")).upper()
        ticker_key = norm(row.get("ticker_symbol")).upper()
        if name_key:
            by_name.setdefault(name_key, row)
        if stock_key:
            by_stock.setdefault(stock_key, row)
        if ticker_key:
            by_ticker.setdefault(ticker_key, row)
    return {"name": by_name, "stock": by_stock, "ticker": by_ticker}


def candidate_for(row: dict[str, Any], indexes: dict[str, dict[str, dict[str, Any]]]) -> tuple[str, str, str]:
    names = [
        row.get("company"),
        row.get("listed_entity_name"),
        row.get("sec_entity_name"),
        row.get("entity_name"),
    ]
    for name in names:
        key = normalized_key(name)
        if key and key in indexes["name"]:
            hit = indexes["name"][key]
            return hit["company_id"], hit["canonical_name"], "exact_normalized_name"

    stock = norm(row.get("stock_code")).upper()
    if stock and stock in indexes["stock"]:
        hit = indexes["stock"][stock]
        return hit["company_id"], hit["canonical_name"], "exact_stock_code"

    ticker = norm(row.get("ticker_symbol")).upper()
    if ticker and ticker in indexes["ticker"]:
        hit = indexes["ticker"][ticker]
        return hit["company_id"], hit["canonical_name"], "exact_ticker_symbol"

    return "", "", ""


def entity_priority(row: dict[str, Any], candidate_id: str) -> str:
    if candidate_id:
        return "P1"
    if norm(row.get("source_table")) == "company_financial_metrics":
        return "P1"
    if norm(row.get("relation_to_listed_entity")) == "listed_entity_self":
        return "P1"
    return "P2"


def entity_suggested_action(row: dict[str, Any], candidate_id: str, candidate_rule: str) -> str:
    table = norm(row.get("source_table"))
    company = norm(row.get("company") or row.get("entity_name"))
    stock_code = norm(row.get("stock_code")).upper()
    relation = norm(row.get("relation_to_listed_entity"))
    status = norm(row.get("listing_verification_status") or row.get("review_status"))

    if candidate_id:
        return (
            f"Review {candidate_rule} candidate {candidate_id}; if the listed/financial entity is the same legal entity, "
            "map company_id and add a note with the evidence basis."
        )
    if table == "company_financial_metrics" and stock_code == "NASDAQ:WALD":
        return "Resolve Waldencast listed parent vs Obagi operating-company mapping before assigning company_id."
    if table == "company_financial_metrics" and company.lower().startswith("novartis"):
        return "Verify the stale/incorrect NASDAQ:NOVN ticker and decide whether Novartis is in-scope or parent-only evidence."
    if table == "company_financial_metrics" and company.lower().startswith("el.en"):
        return "Confirm whether ELN.MI should map to the existing El.En. company or a separate listed group parent."
    if relation == "subsidiary_or_affiliate":
        return "Confirm parent/affiliate relationship; do not map to the operating subsidiary without an explicit parent trace."
    if "non-us" in status.lower():
        return "Verify non-US exchange and legal listed entity from exchange/IR source, then add or map company_master."
    return "Review entity identity, decide add-to-company_master vs keep as unresolved reference evidence."


def build_entity_resolution_queue(cur: sqlite3.Cursor, now: str) -> list[dict[str, Any]]:
    indexes = company_master_indexes(cur)
    rows: list[dict[str, Any]] = []

    listed_rows = table_rows(
        cur,
        """
        SELECT
          batch_id,
          company_id,
          company,
          listed_entity_name,
          relation_to_listed_entity,
          stock_code,
          exchange,
          ticker_symbol,
          listing_country,
          sec_cik,
          sec_entity_name,
          listing_verification_status,
          review_status,
          official_source_url,
          market_source_url,
          notes
        FROM listed_company_batch
        WHERE NULLIF(TRIM(COALESCE(company_id, '')), '') IS NULL
        ORDER BY company, listed_entity_name, stock_code
        """,
    )
    for row in listed_rows:
        row["source_table"] = "listed_company_batch"
        candidate_id, candidate_name, candidate_rule = candidate_for(row, indexes)
        rows.append(
            {
                "queue_id": f"entity-listed-{row.get('batch_id')}",
                "priority": entity_priority(row, candidate_id),
                "source_table": "listed_company_batch",
                "source_row_key": row.get("batch_id", ""),
                "issue_type": "blank_company_id",
                "entity_name": row.get("company", ""),
                "listed_entity_name": row.get("listed_entity_name", ""),
                "current_company_id": row.get("company_id", ""),
                "stock_code": row.get("stock_code", ""),
                "exchange": row.get("exchange", ""),
                "ticker_symbol": row.get("ticker_symbol", ""),
                "listing_country": row.get("listing_country", ""),
                "sec_cik": row.get("sec_cik", ""),
                "review_status": row.get("review_status") or row.get("listing_verification_status", ""),
                "candidate_company_id": candidate_id,
                "candidate_company_name": candidate_name,
                "candidate_match_rule": candidate_rule,
                "suggested_action": entity_suggested_action(row, candidate_id, candidate_rule),
                "owner_module": "entity_resolution",
                "source_url": row.get("official_source_url") or row.get("market_source_url", ""),
                "notes": row.get("notes", ""),
                "generated_at": now,
            }
        )

    financial_rows = table_rows(
        cur,
        """
        SELECT
          rowid AS rowid,
          company_id,
          company,
          stock_code,
          ticker_symbol,
          sec_cik,
          sec_entity_name,
          review_status,
          source_url,
          note
        FROM company_financial_metrics
        WHERE NULLIF(TRIM(COALESCE(company_id, '')), '') IS NULL
        ORDER BY company, stock_code
        """,
    )
    for row in financial_rows:
        row["source_table"] = "company_financial_metrics"
        candidate_id, candidate_name, candidate_rule = candidate_for(row, indexes)
        rows.append(
            {
                "queue_id": f"entity-financial-{row.get('rowid')}",
                "priority": entity_priority(row, candidate_id),
                "source_table": "company_financial_metrics",
                "source_row_key": str(row.get("rowid", "")),
                "issue_type": "blank_company_id",
                "entity_name": row.get("company", ""),
                "listed_entity_name": row.get("sec_entity_name", ""),
                "current_company_id": row.get("company_id", ""),
                "stock_code": row.get("stock_code", ""),
                "exchange": "",
                "ticker_symbol": row.get("ticker_symbol", ""),
                "listing_country": "",
                "sec_cik": row.get("sec_cik", ""),
                "review_status": row.get("review_status", ""),
                "candidate_company_id": candidate_id,
                "candidate_company_name": candidate_name,
                "candidate_match_rule": candidate_rule,
                "suggested_action": entity_suggested_action(row, candidate_id, candidate_rule),
                "owner_module": "entity_resolution",
                "source_url": row.get("source_url", ""),
                "notes": row.get("note", ""),
                "generated_at": now,
            }
        )

    return rows


def registration_triage_bucket(row: dict[str, Any]) -> str:
    review_status = norm(row.get("review_status"))
    source_type = norm(row.get("source_type")).lower()
    confidence = norm(row.get("confidence")).lower()
    source_url = norm(row.get("source_url")).lower()

    if review_status == "manual_new_product_candidate":
        return "new_product_candidate_resolution"
    if "seed" in source_type or confidence == "seed_unverified":
        return "seed_registration_verification"
    if source_url:
        return "official_source_text_review"
    return "evidence_completeness_review"


def registration_priority(row: dict[str, Any], bucket: str) -> str:
    if bucket == "new_product_candidate_resolution":
        return "P1"
    if norm(row.get("registration_no")) and norm(row.get("source_url")):
        return "P1"
    if norm(row.get("source_url")):
        return "P2"
    return "P3"


def registration_suggested_action(bucket: str) -> str:
    if bucket == "new_product_candidate_resolution":
        return "Decide promote-to-product, merge-to-existing product, or exclude/out-of-scope."
    if bucket == "seed_registration_verification":
        return "Verify against official regulator or certificate source, then update confidence/status."
    if bucket == "official_source_text_review":
        return "Review official wording and populate approved_indication/intended_use where supportable."
    return "Find official evidence or mark unavailable_verified/not_disclosed with rationale."


def build_registration_review_queue(cur: sqlite3.Cursor, now: str) -> list[dict[str, Any]]:
    review_rows = table_rows(
        cur,
        """
        SELECT
          id,
          product_id,
          seed_record_id,
          company_id,
          company,
          brand,
          jurisdiction,
          regulator,
          regulatory_pathway,
          status,
          registration_no,
          approval_date,
          registered_name,
          source_type,
          source_key,
          source_url,
          evidence_title,
          review_status,
          confidence
        FROM registration_evidence
        WHERE review_status IN ('needs_review', 'manual_new_product_candidate')
        ORDER BY
          CASE review_status
            WHEN 'manual_new_product_candidate' THEN 1
            WHEN 'needs_review' THEN 2
            ELSE 3
          END,
          jurisdiction,
          company,
          brand,
          seed_record_id
        """,
    )

    rows: list[dict[str, Any]] = []
    for row in review_rows:
        bucket = registration_triage_bucket(row)
        rows.append(
            {
                "queue_id": f"registration-{row.get('id')}",
                "priority": registration_priority(row, bucket),
                "source_table": "registration_evidence",
                "source_row_key": str(row.get("id", "")),
                "triage_bucket": bucket,
                "product_id": row.get("product_id", ""),
                "seed_record_id": row.get("seed_record_id", ""),
                "company_id": row.get("company_id", ""),
                "company": row.get("company", ""),
                "brand": row.get("brand", ""),
                "jurisdiction": row.get("jurisdiction", ""),
                "regulator": row.get("regulator", ""),
                "regulatory_pathway": row.get("regulatory_pathway", ""),
                "status": row.get("status", ""),
                "registration_no": row.get("registration_no", ""),
                "approval_date": row.get("approval_date", ""),
                "registered_name": row.get("registered_name", ""),
                "source_type": row.get("source_type", ""),
                "source_key": row.get("source_key", ""),
                "source_url": row.get("source_url", ""),
                "evidence_title": row.get("evidence_title", ""),
                "review_status": row.get("review_status", ""),
                "confidence": row.get("confidence", ""),
                "suggested_action": registration_suggested_action(bucket),
                "generated_at": now,
            }
        )
    return rows


def aesthetics_revenue_priority(row: dict[str, Any]) -> str:
    revenue = parse_float(row.get("revenue_usd_m"))
    if revenue is None:
        return "P3"
    if revenue >= 1000:
        return "P1"
    if revenue >= 100:
        return "P2"
    return "P3"


def expected_aesthetics_revenue_source(row: dict[str, Any]) -> str:
    source = norm(row.get("financial_source_url")).lower()
    if "sec.gov" in source:
        return "Annual filing segment footnotes and MD&A; SEC XBRL total revenue is not enough."
    if "annual" in source or "investor" in source or "ir" in source:
        return "Company annual report or investor-relations segment disclosure."
    return "Company annual report, investor deck, or explicit not-disclosed review."


def build_aesthetics_revenue_queue(cur: sqlite3.Cursor, now: str) -> list[dict[str, Any]]:
    missing_rows = table_rows(
        cur,
        """
        SELECT
          cm.company_id,
          c.company,
          c.stock_code,
          c.ownership,
          c.status,
          c.revenue_usd_m,
          c.revenue_year,
          c.gross_margin_pct,
          c.market_cap_usd_m,
          c.financial_review_status,
          c.financial_source_url
        FROM companies AS c
        LEFT JOIN company_master AS cm
          ON LOWER(TRIM(cm.canonical_name)) = LOWER(TRIM(c.company))
        WHERE c.ownership = 'Public'
          AND c.status = 'Active'
          AND NULLIF(TRIM(COALESCE(c.aesthetics_revenue_pct, '')), '') IS NULL
        ORDER BY
          CASE
            WHEN CAST(NULLIF(c.revenue_usd_m, '') AS REAL) >= 1000 THEN 1
            WHEN CAST(NULLIF(c.revenue_usd_m, '') AS REAL) >= 100 THEN 2
            ELSE 3
          END,
          c.company
        """,
    )

    rows: list[dict[str, Any]] = []
    for index, row in enumerate(missing_rows, start=1):
        rows.append(
            {
                "queue_id": f"aesthetics-revenue-{index:03d}",
                "priority": aesthetics_revenue_priority(row),
                "company_id": row.get("company_id", ""),
                "company": row.get("company", ""),
                "stock_code": row.get("stock_code", ""),
                "ownership": row.get("ownership", ""),
                "status": row.get("status", ""),
                "revenue_usd_m": row.get("revenue_usd_m", ""),
                "revenue_year": row.get("revenue_year", ""),
                "gross_margin_pct": row.get("gross_margin_pct", ""),
                "market_cap_usd_m": row.get("market_cap_usd_m", ""),
                "financial_review_status": row.get("financial_review_status", ""),
                "financial_source_url": row.get("financial_source_url", ""),
                "issue_type": "missing_aesthetics_revenue_pct",
                "expected_source": expected_aesthetics_revenue_source(row),
                "suggested_action": (
                    "Collect aesthetics-specific revenue share from segment disclosure, or mark not_disclosed/"
                    "unavailable_verified; do not infer from total revenue alone."
                ),
                "generated_at": now,
            }
        )
    return rows


def write_queue(name: str, fields: list[str], rows: list[dict[str, Any]]) -> dict[str, Any]:
    latest_path = AUDIT_DIR / f"{name}_latest.csv"
    dated_path = AUDIT_DIR / f"{name}_{DATE_TAG}.csv"
    for path in [latest_path, dated_path]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
    return {
        "name": name,
        "rows": len(rows),
        "latest_path": str(latest_path),
        "dated_path": str(dated_path),
    }


def write_summary(summary: dict[str, Any]) -> None:
    json_latest = AUDIT_DIR / "data_quality_backlog_queue_summary_latest.json"
    json_dated = AUDIT_DIR / f"data_quality_backlog_queue_summary_{DATE_TAG}.json"
    md_latest = AUDIT_DIR / "data_quality_backlog_queue_summary_latest.md"
    md_dated = AUDIT_DIR / f"data_quality_backlog_queue_summary_{DATE_TAG}.md"

    for path in [json_latest, json_dated]:
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Data Quality Backlog Queue Summary",
        "",
        f"Generated at: {summary['generated_at']}",
        "",
        "| Queue | Rows | Latest CSV |",
        "| --- | ---: | --- |",
    ]
    for item in summary["queues"]:
        lines.append(f"| {item['name']} | {item['rows']} | `{item['latest_path']}` |")

    lines.extend(
        [
            "",
            "## Checks",
            "",
            f"- Financial blank company_id after Galderma remap: {summary['checks']['financial_blank_company_id']}",
            f"- Listed batch blank company_id: {summary['checks']['listed_blank_company_id']}",
            f"- Registration evidence review backlog: {summary['checks']['registration_review_backlog']}",
            f"- Public company aesthetics revenue pct backlog: {summary['checks']['public_aesthetics_revenue_pct_backlog']}",
            "",
            "## Notes",
            "",
            "- These queues are backlog controls, not release-blocking failures by themselves.",
            "- Entity candidates are hints only; a candidate_company_id still requires source review before mapping.",
            "- Aesthetics revenue pct should be filled only from segment evidence or explicit unavailable/not-disclosed review.",
        ]
    )
    text = "\n".join(lines) + "\n"
    for path in [md_latest, md_dated]:
        path.write_text(text, encoding="utf-8")


def main() -> int:
    now = generated_at()
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    entity_rows = build_entity_resolution_queue(cur, now)
    registration_rows = build_registration_review_queue(cur, now)
    revenue_rows = build_aesthetics_revenue_queue(cur, now)

    queue_summaries = [
        write_queue("entity_resolution_review_queue", ENTITY_FIELDS, entity_rows),
        write_queue("registration_review_queue", REGISTRATION_FIELDS, registration_rows),
        write_queue("aesthetics_revenue_pct_collection_queue", AESTHETICS_REVENUE_FIELDS, revenue_rows),
    ]

    summary = {
        "generated_at": now,
        "database_path": str(DB_PATH),
        "queues": queue_summaries,
        "checks": {
            "financial_blank_company_id": sum(
                1
                for row in entity_rows
                if row["source_table"] == "company_financial_metrics" and row["issue_type"] == "blank_company_id"
            ),
            "listed_blank_company_id": sum(
                1
                for row in entity_rows
                if row["source_table"] == "listed_company_batch" and row["issue_type"] == "blank_company_id"
            ),
            "registration_review_backlog": len(registration_rows),
            "public_aesthetics_revenue_pct_backlog": len(revenue_rows),
            "registration_by_review_status": dict(Counter(row["review_status"] for row in registration_rows)),
            "registration_by_triage_bucket": dict(Counter(row["triage_bucket"] for row in registration_rows)),
            "entity_by_source_table": dict(Counter(row["source_table"] for row in entity_rows)),
            "aesthetics_revenue_by_priority": dict(Counter(row["priority"] for row in revenue_rows)),
        },
    }
    write_summary(summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
