#!/usr/bin/env python3
"""Build progress reports for the current verification run."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from build_data import (
    COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH,
    COMPANY_OFFICIAL_SOURCE_PLAN_PATH,
    COMPANY_MEDIA_ASSET_INDEX_PATH,
    COMPANY_OFFICIAL_WEBSITE_PATH,
    DATA_DIR,
    DB_PATH,
    MDR_CE_SEARCH_PLAN_PATH,
    MARKET_SNAPSHOT_LIVE_PATH,
    OFFICIAL_WEBSITE_MASTER_PATH,
    PRODUCT_SPECIFICATION_EVIDENCE_PATH,
    STAGING_JSONL_PATH,
)
from collect_mdr_ce_sources import MDR_CE_EVIDENCE_PATH
from dashboard_scope import company_exclusion_reason


MARKET_VALUATION_RANK_PATH = DATA_DIR / "market_valuation_rank.csv"
MARKET_CONFLICT_PATH = DATA_DIR / "market_snapshot_conflicts.csv"
OFFICIAL_COVERAGE_PATH = DATA_DIR / "official_source_coverage.csv"
SOURCE_DIFF_REPORT_PATH = DATA_DIR / "source_diff_report.csv"
PROGRESS_SUMMARY_PATH = DATA_DIR / "progress_summary.md"
XUEQIU_MARKET_CHECK_PATH = DATA_DIR / "xueqiu_market_check.csv"


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            row
            for row in csv.DictReader(handle)
            if company_exclusion_reason(row) != "no_medical_aesthetic_product"
        ]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and company_exclusion_reason(row) == "no_medical_aesthetic_product":
            continue
        rows.append(row)
    return rows


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def build_market_reports(conn: sqlite3.Connection) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in conn.execute(
            """
            SELECT company, stock_code, exchange, ticker_symbol, listing_country,
                   market_cap_usd_m, as_of, source, source_url, snapshot_status, note
            FROM market_snapshot
            ORDER BY
              CASE WHEN market_cap_usd_m IS NULL OR market_cap_usd_m = '' THEN 1 ELSE 0 END,
              CAST(COALESCE(NULLIF(market_cap_usd_m, ''), '0') AS REAL) DESC,
              company
            """
        )
    ]
    ranked = []
    for rank, row in enumerate(rows, start=1):
        ranked.append(
            {
                "valuation_rank": rank,
                "company": row["company"],
                "stock_code": row["stock_code"],
                "exchange": row["exchange"],
                "ticker_symbol": row["ticker_symbol"],
                "listing_country": row["listing_country"],
                "market_cap_usd_m": row["market_cap_usd_m"],
                "valuation_band": valuation_band(number(row["market_cap_usd_m"])),
                "as_of": row["as_of"],
                "source": row["source"],
                "source_url": row["source_url"],
                "snapshot_status": row["snapshot_status"],
                "note": row["note"],
            }
        )
    conflicts = []
    for row in ranked:
        if row["snapshot_status"] != "valuation_fetched" or not row["market_cap_usd_m"]:
            conflicts.append(
                {
                    **row,
                    "issue_type": "valuation_or_ticker_unconfirmed",
                    "recommended_next_source": "Official exchange / SEC or local filing first; Xueqiu fallback when official source search misses or ticker is ambiguous.",
                }
            )
    write_csv(
        MARKET_VALUATION_RANK_PATH,
        [
            "valuation_rank",
            "company",
            "stock_code",
            "exchange",
            "ticker_symbol",
            "listing_country",
            "market_cap_usd_m",
            "valuation_band",
            "as_of",
            "source",
            "source_url",
            "snapshot_status",
            "note",
        ],
        ranked,
    )
    write_csv(
        MARKET_CONFLICT_PATH,
        [
            "valuation_rank",
            "company",
            "stock_code",
            "exchange",
            "ticker_symbol",
            "listing_country",
            "market_cap_usd_m",
            "valuation_band",
            "as_of",
            "source",
            "source_url",
            "snapshot_status",
            "note",
            "issue_type",
            "recommended_next_source",
        ],
        conflicts,
    )
    return ranked, conflicts


def valuation_band(usd_m: float) -> str:
    if usd_m >= 200_000:
        return "mega cap"
    if usd_m >= 10_000:
        return "large cap"
    if usd_m >= 2_000:
        return "mid cap"
    if usd_m > 0:
        return "small cap"
    return "pending"


def build_official_coverage() -> list[dict[str, Any]]:
    plan_rows = read_csv(COMPANY_OFFICIAL_SOURCE_PLAN_PATH)
    evidence_rows = read_jsonl(COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH)
    by_company: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "company_id": "",
            "company": "",
            "plan_rows": 0,
            "query_types_planned": Counter(),
            "evidence_rows": 0,
            "likely_official_rows": 0,
            "possible_official_rows": 0,
            "crosscheck_rows": 0,
            "product_portfolio_evidence": 0,
            "ifu_catalog_evidence": 0,
            "capital_evidence": 0,
            "official_domains": Counter(),
        }
    )
    for row in plan_rows:
        bucket = by_company[norm(row.get("company_id"))]
        bucket["company_id"] = norm(row.get("company_id"))
        bucket["company"] = norm(row.get("company"))
        bucket["plan_rows"] += 1
        bucket["query_types_planned"][norm(row.get("query_type"))] += 1
    for row in evidence_rows:
        bucket = by_company[norm(row.get("company_id"))]
        bucket["company_id"] = norm(row.get("company_id"))
        bucket["company"] = norm(row.get("company"))
        bucket["evidence_rows"] += 1
        candidate = norm(row.get("official_candidate"))
        confidence = norm(row.get("confidence"))
        query_type = norm(row.get("query_type"))
        if candidate == "likely" or confidence == "official_domain_candidate":
            bucket["likely_official_rows"] += 1
            host = row.get("url", "").split("/")[2].lower().replace("www.", "") if "://" in row.get("url", "") else ""
            if host:
                bucket["official_domains"][host] += 1
        elif candidate == "possible":
            bucket["possible_official_rows"] += 1
        else:
            bucket["crosscheck_rows"] += 1
        if query_type == "official_product_portfolio":
            bucket["product_portfolio_evidence"] += 1
        elif query_type == "official_ifu_catalog":
            bucket["ifu_catalog_evidence"] += 1
        elif query_type == "investor_relations_or_annual_report":
            bucket["capital_evidence"] += 1
    rows: list[dict[str, Any]] = []
    for bucket in by_company.values():
        status = "not_started"
        if bucket["likely_official_rows"]:
            status = "official_candidate_found"
        elif bucket["evidence_rows"]:
            status = "crosscheck_only"
        elif bucket["plan_rows"]:
            status = "planned_not_queried"
        rows.append(
            {
                "company_id": bucket["company_id"],
                "company": bucket["company"],
                "plan_rows": bucket["plan_rows"],
                "evidence_rows": bucket["evidence_rows"],
                "likely_official_rows": bucket["likely_official_rows"],
                "possible_official_rows": bucket["possible_official_rows"],
                "crosscheck_rows": bucket["crosscheck_rows"],
                "product_portfolio_evidence": bucket["product_portfolio_evidence"],
                "ifu_catalog_evidence": bucket["ifu_catalog_evidence"],
                "capital_evidence": bucket["capital_evidence"],
                "top_official_domains": "; ".join(domain for domain, _count in bucket["official_domains"].most_common(5)),
                "coverage_status": status,
            }
        )
    rows.sort(key=lambda row: (row["coverage_status"] != "official_candidate_found", -int(row["likely_official_rows"]), row["company"]))
    write_csv(
        OFFICIAL_COVERAGE_PATH,
        [
            "company_id",
            "company",
            "plan_rows",
            "evidence_rows",
            "likely_official_rows",
            "possible_official_rows",
            "crosscheck_rows",
            "product_portfolio_evidence",
            "ifu_catalog_evidence",
            "capital_evidence",
            "top_official_domains",
            "coverage_status",
        ],
        rows,
    )
    return rows


def build_diff_report(conn: sqlite3.Connection, market_conflicts: list[dict[str, Any]], coverage_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    rows: list[dict[str, Any]] = []
    fda_counts = Counter(
        row["company"]
        for row in conn.execute(
            """
            SELECT company
            FROM registration_evidence
            WHERE source_key = 'fda_openfda_510k'
            """
        )
    )
    for company, count in fda_counts.items():
        rows.append(
            {
                "entity_type": "company",
                "entity_name": company,
                "issue_type": "new_official_fda_evidence",
                "evidence_count": count,
                "status": "added_to_staging",
                "recommended_action": "Use official 510(k) rows to map registered name, applicant, product code and approval date back to product families.",
            }
        )
    for row in market_conflicts:
        rows.append(
            {
                "entity_type": "company",
                "entity_name": row["company"],
                "issue_type": "listing_or_valuation_unconfirmed",
                "evidence_count": 0,
                "status": row["snapshot_status"],
                "recommended_action": row["recommended_next_source"],
            }
        )
    for row in read_csv(XUEQIU_MARKET_CHECK_PATH):
        rows.append(
            {
                "entity_type": "company",
                "entity_name": row["company"],
                "issue_type": "xueqiu_market_api_check",
                "evidence_count": 1,
                "status": row["xueqiu_status"],
                "recommended_action": row.get("issue_hint") or "Use Xueqiu as market-data cross-check; confirm listing identity with official exchange or securities filing before changing master ticker.",
            }
        )
    for row in coverage_rows:
        if row["coverage_status"] == "planned_not_queried":
            rows.append(
                {
                    "entity_type": "company",
                    "entity_name": row["company"],
                    "issue_type": "official_company_source_not_queried_yet",
                    "evidence_count": 0,
                    "status": "planned",
                    "recommended_action": "Run collect_company_official_sources.py for the remaining official-source plan rows.",
                }
            )
        elif row["coverage_status"] == "crosscheck_only":
            rows.append(
                {
                    "entity_type": "company",
                    "entity_name": row["company"],
                    "issue_type": "official_company_source_unconfirmed",
                    "evidence_count": row["evidence_rows"],
                    "status": "crosscheck_only",
                    "recommended_action": "Use official website, IFU/catalog, investor-relations or filing source before merging product/company facts.",
                }
            )
    write_csv(
        SOURCE_DIFF_REPORT_PATH,
        ["entity_type", "entity_name", "issue_type", "evidence_count", "status", "recommended_action"],
        rows,
    )
    return rows


def build_summary(
    market_ranked: list[dict[str, Any]],
    market_conflicts: list[dict[str, Any]],
    coverage_rows: list[dict[str, Any]],
    diff_rows: list[dict[str, Any]],
) -> None:
    official_found = sum(1 for row in coverage_rows if row["coverage_status"] == "official_candidate_found")
    crosscheck_only = sum(1 for row in coverage_rows if row["coverage_status"] == "crosscheck_only")
    not_queried = sum(1 for row in coverage_rows if row["coverage_status"] == "planned_not_queried")
    fda_rows = [row for row in diff_rows if row["issue_type"] == "new_official_fda_evidence"]
    mdr_rows = read_jsonl(MDR_CE_EVIDENCE_PATH)
    xueqiu_rows = read_csv(XUEQIU_MARKET_CHECK_PATH)
    official_websites = read_csv(OFFICIAL_WEBSITE_MASTER_PATH)
    company_websites = read_csv(COMPANY_OFFICIAL_WEBSITE_PATH)
    media_assets = read_csv(COMPANY_MEDIA_ASSET_INDEX_PATH)
    product_specs = read_csv(PRODUCT_SPECIFICATION_EVIDENCE_PATH)
    xueqiu_status = Counter(row.get("xueqiu_status") or "unknown" for row in xueqiu_rows)
    website_scope = Counter(row.get("entity_scope") or "unknown" for row in official_websites)
    media_status = Counter(row.get("review_status") or "unknown" for row in media_assets)
    spec_category = Counter(row.get("spec_category") or "unknown" for row in product_specs)
    lines = [
        "# Verification Progress Summary",
        "",
        f"- Valuation rows: {len(market_ranked)}; conflicts/pending: {len(market_conflicts)}.",
        f"- Official company-source coverage: {official_found} companies with likely official-domain candidates, {crosscheck_only} cross-check only, {not_queried} not queried yet.",
        f"- Official website master: {len(official_websites)} rows across {len(company_websites)} companies; scopes {dict(website_scope)}.",
        f"- Media asset index: {len(media_assets)} rows; status {dict(media_status)}.",
        f"- Product specification evidence: {len(product_specs)} rows; categories {dict(spec_category)}.",
        f"- FDA openFDA staged companies: {len(fda_rows)}; official FDA evidence rows: {sum(int(row['evidence_count']) for row in fda_rows)}.",
        f"- MDR/CE candidate rows: {len(mdr_rows)}.",
        f"- Xueqiu API market checks: {len(xueqiu_rows)} rows; {dict(xueqiu_status)}.",
        f"- Source diff report rows: {len(diff_rows)}.",
        "",
        "## Top Valuation Rows",
    ]
    for row in market_ranked[:10]:
        value = row["market_cap_usd_m"] or "pending"
        lines.append(f"- {row['valuation_rank']}. {row['company']} | USDm {value} | {row['stock_code']} | {row['snapshot_status']}")
    lines.extend(
        [
            "",
            "## Output Files",
            f"- {MARKET_VALUATION_RANK_PATH}",
            f"- {MARKET_CONFLICT_PATH}",
            f"- {OFFICIAL_COVERAGE_PATH}",
            f"- {SOURCE_DIFF_REPORT_PATH}",
            f"- {PROGRESS_SUMMARY_PATH}",
        ]
    )
    PROGRESS_SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    market_ranked, market_conflicts = build_market_reports(conn)
    coverage_rows = build_official_coverage()
    diff_rows = build_diff_report(conn, market_conflicts, coverage_rows)
    conn.close()
    build_summary(market_ranked, market_conflicts, coverage_rows, diff_rows)
    result = {
        "market_valuation_rank_rows": len(market_ranked),
        "market_conflict_rows": len(market_conflicts),
        "official_coverage_rows": len(coverage_rows),
        "source_diff_report_rows": len(diff_rows),
        "paths": [
            str(MARKET_VALUATION_RANK_PATH),
            str(MARKET_CONFLICT_PATH),
            str(OFFICIAL_COVERAGE_PATH),
            str(SOURCE_DIFF_REPORT_PATH),
            str(PROGRESS_SUMMARY_PATH),
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
