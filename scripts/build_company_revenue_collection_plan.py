#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"

LISTED_COMPANY_BATCH_PATH = DATA_DIR / "listed_company_batch.csv"
COMPANY_FINANCIAL_METRICS_PATH = DATA_DIR / "company_financial_metrics.csv"
COMPANY_OFFICIAL_SOURCE_PLAN_PATH = DATA_DIR / "company_official_source_plan.csv"
OUTPUT_CSV = AUDIT_DIR / "company_revenue_collection_plan_latest.csv"
OUTPUT_MD = AUDIT_DIR / "company_revenue_collection_plan_latest.md"


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def row_has_revenue(row: dict[str, str]) -> bool:
    return norm(row.get("revenue_usd_m")) not in {"", "0", "0.0", "0.00"}


def module_for(listed: dict[str, str], financial: dict[str, str] | None) -> str:
    if financial and row_has_revenue(financial):
        return "already_promoted_company_financial_metrics"
    if norm(listed.get("sec_cik")):
        return "sec_xbrl_collector"
    exchange = norm(listed.get("exchange")).upper()
    if exchange in {"NASDAQ", "NYSE", "AMEX"}:
        return "sec_cik_backfill_then_sec_xbrl_collector"
    if exchange in {"SIX", "HKEX", "KRX", "KOSDAQ", "TSE", "XETRA", "PA", "EPA", "BIT", "MIL", "LSE"}:
        return "non_us_ir_annual_report_collector"
    return "official_ir_or_exchange_filing_collector"


def run() -> int:
    generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    listed_rows = read_csv(LISTED_COMPANY_BATCH_PATH)
    financial_by_id = {norm(row.get("company_id")): row for row in read_csv(COMPANY_FINANCIAL_METRICS_PATH)}
    revenue_plans = {
        norm(row.get("company_id")): row
        for row in read_csv(COMPANY_OFFICIAL_SOURCE_PLAN_PATH)
        if norm(row.get("query_type")) == "investor_relations_or_annual_report"
    }

    rows: list[dict[str, Any]] = []
    for listed in listed_rows:
        company_id = norm(listed.get("company_id"))
        financial = financial_by_id.get(company_id)
        plan = revenue_plans.get(company_id, {})
        module = module_for(listed, financial)
        has_revenue = bool(financial and row_has_revenue(financial))
        status = "promoted_to_companies" if has_revenue else "ready_to_collect"
        if module == "sec_cik_backfill_then_sec_xbrl_collector":
            status = "needs_sec_cik"
        rows.append(
            {
                "company_id": company_id,
                "company": listed.get("company", ""),
                "listed_entity_name": listed.get("listed_entity_name", ""),
                "stock_code": listed.get("stock_code", ""),
                "exchange": listed.get("exchange", ""),
                "ticker_symbol": listed.get("ticker_symbol", ""),
                "listing_country": listed.get("listing_country", ""),
                "sec_cik": listed.get("sec_cik", ""),
                "current_revenue_usd_m": "" if not financial else financial.get("revenue_usd_m", ""),
                "current_revenue_year": "" if not financial else financial.get("fiscal_year", ""),
                "current_gross_margin_pct": "" if not financial else financial.get("gross_margin_pct", ""),
                "current_source_url": "" if not financial else financial.get("source_url", ""),
                "operational_status": status,
                "responsible_module": module,
                "plan_id": plan.get("plan_id", ""),
                "query": plan.get("query", ""),
                "expected_source": plan.get("expected_source", "Investor relations / annual report / exchange or securities filing"),
                "next_action": (
                    "Keep refreshed during financial promote runs."
                    if has_revenue
                    else "Fetch latest annual report or securities filing, extract revenue/gross profit, cite source URL, then merge into company_financial_metrics.csv."
                ),
                "generated_at": generated_at,
            }
        )

    rows.sort(key=lambda row: (row["operational_status"] != "ready_to_collect", row["operational_status"], norm(row.get("company")).lower()))
    fields = [
        "company_id",
        "company",
        "listed_entity_name",
        "stock_code",
        "exchange",
        "ticker_symbol",
        "listing_country",
        "sec_cik",
        "current_revenue_usd_m",
        "current_revenue_year",
        "current_gross_margin_pct",
        "current_source_url",
        "operational_status",
        "responsible_module",
        "plan_id",
        "query",
        "expected_source",
        "next_action",
        "generated_at",
    ]
    write_csv(OUTPUT_CSV, fields, rows)

    by_status = Counter(row["operational_status"] for row in rows)
    by_module = Counter(row["responsible_module"] for row in rows)
    lines = [
        "# Company Revenue Collection Plan",
        "",
        f"- Generated: {generated_at}",
        f"- Listed companies: {len(rows)}",
        f"- Already promoted revenue rows: {by_status.get('promoted_to_companies', 0)}",
        f"- Ready to collect: {by_status.get('ready_to_collect', 0)}",
        f"- Needs SEC CIK first: {by_status.get('needs_sec_cik', 0)}",
        "",
        "## Responsible Modules",
        "",
    ]
    for module, count in by_module.most_common():
        lines.append(f"- {module}: {count}")
    lines.extend(["", "## File", "", f"- Plan CSV: `{OUTPUT_CSV}`"])
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "generated_at": generated_at,
                "rows": len(rows),
                "by_status": dict(by_status),
                "by_module": dict(by_module),
                "output_csv": str(OUTPUT_CSV),
                "summary": str(OUTPUT_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
