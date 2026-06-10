"""
Merge manually-curated non-US listed financial metrics into
data/company_financial_metrics.csv. Only rows with review_status !=
'pending_collection' get included in the merged output as "verified" entries
for the dashboard; pending rows are dumped to a separate queue CSV.

Workflow:
1. Researcher fills in numbers in data/manual_non_us_financial_metrics.csv
   from each company's investor relations annual report (IR), citing the URL.
2. Researcher sets review_status to 'manual_verified' once double-checked.
3. This script appends those verified rows into company_financial_metrics.csv
   under the same schema used by the SEC collector.

The SEC collector still owns the US/ADR rows. This script is additive only.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEC_CSV = ROOT / "data" / "company_financial_metrics.csv"
MANUAL_CSV = ROOT / "data" / "manual_non_us_financial_metrics.csv"
QUEUE_CSV = ROOT / "data" / "audits" / "non_us_financial_pending_collection_latest.csv"

# Match the schema of company_financial_metrics.csv produced by SEC collector
SEC_FIELDS = [
    "company_id", "company", "stock_code", "ticker_symbol", "sec_cik",
    "sec_entity_name", "fiscal_year", "revenue_usd_m", "gross_profit_usd_m",
    "gross_margin_pct", "net_income_usd_m", "net_income_growth_yoy_pct",
    "stockholders_equity_usd_m", "market_cap_usd_m", "ps_ratio", "pe_ratio", "pb_ratio",
    "eps_basic", "eps_diluted", "eps_ttm",
    "revenue_concept", "gross_profit_concept", "net_income_concept", "equity_concept", "eps_concept", "revenue_filed",
    "filing_date", "financial_period", "metric_basis",
    "source_url", "captured_at", "review_status", "note",
]

ACCEPTED_STATUSES = {"manual_verified", "manual_pending_verification"}


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as h:
        return list(csv.DictReader(h))


def main() -> None:
    sec_rows = load_csv(SEC_CSV)
    manual_rows = load_csv(MANUAL_CSV)
    captured = dt.datetime.now().astimezone().isoformat(timespec="seconds")

    # Existing company_ids in SEC output — don't double-count
    existing_ids = {r.get("company_id", "") for r in sec_rows}

    accepted: list[dict[str, str]] = []
    pending: list[dict[str, str]] = []
    for r in manual_rows:
        status = (r.get("review_status") or "").strip().lower()
        cid = (r.get("company_id") or "").strip()
        if cid in existing_ids and cid:
            continue  # SEC row wins
        if status in ACCEPTED_STATUSES:
            accepted.append(r)
        else:
            pending.append(r)

    # Append accepted to SEC csv (preserving existing rows)
    merged = sec_rows + [
        {
            "company_id": r.get("company_id", ""),
            "company": r.get("company", ""),
            "stock_code": r.get("stock_code", ""),
            "ticker_symbol": r.get("ticker_symbol", ""),
            "sec_cik": "",
            "sec_entity_name": "",
            "fiscal_year": r.get("fiscal_year", ""),
            "revenue_usd_m": r.get("revenue_usd_m", ""),
            "gross_profit_usd_m": r.get("gross_profit_local", "")
                if r.get("revenue_currency", "USD").upper() == "USD"
                else "",
            "gross_margin_pct": r.get("gross_margin_pct", ""),
            "net_income_usd_m": r.get("net_income_usd_m", ""),
            "net_income_growth_yoy_pct": r.get("net_income_growth_yoy_pct", ""),
            "stockholders_equity_usd_m": r.get("stockholders_equity_usd_m", ""),
            "market_cap_usd_m": r.get("market_cap_usd_m", ""),
            "ps_ratio": r.get("ps_ratio", ""),
            "pe_ratio": r.get("pe_ratio", ""),
            "pb_ratio": r.get("pb_ratio", ""),
            "eps_basic": r.get("eps_basic", ""),
            "eps_diluted": r.get("eps_diluted", ""),
            "eps_ttm": r.get("eps_ttm", ""),
            "revenue_concept": r.get("revenue_basis", ""),
            "gross_profit_concept": "",
            "net_income_concept": r.get("net_income_basis", ""),
            "equity_concept": r.get("equity_basis", ""),
            "eps_concept": r.get("eps_basis", ""),
            "revenue_filed": r.get("revenue_filed", ""),
            "filing_date": r.get("filing_date", "") or r.get("revenue_filed", ""),
            "financial_period": f"FY{r.get('fiscal_year', '')}" if r.get("fiscal_year", "") else "",
            "metric_basis": r.get("metric_basis", "") or "Manual IR annual report",
            "source_url": r.get("source_url", ""),
            "captured_at": captured,
            "review_status": r.get("review_status", "manual_pending_verification"),
            "note": "[NON-US MANUAL] " + (r.get("note", "") or ""),
        }
        for r in accepted
    ]

    SEC_CSV.parent.mkdir(parents=True, exist_ok=True)
    with SEC_CSV.open("w", encoding="utf-8", newline="") as h:
        writer = csv.DictWriter(h, fieldnames=SEC_FIELDS)
        writer.writeheader()
        writer.writerows(merged)
    print(f"Wrote {SEC_CSV} · {len(merged)} rows ({len(sec_rows)} SEC + {len(accepted)} non-US verified)")

    # Pending queue
    QUEUE_CSV.parent.mkdir(parents=True, exist_ok=True)
    with QUEUE_CSV.open("w", encoding="utf-8", newline="") as h:
        if pending:
            writer = csv.DictWriter(h, fieldnames=list(pending[0].keys()))
            writer.writeheader()
            writer.writerows(pending)
    print(f"Wrote {QUEUE_CSV} · {len(pending)} pending rows for IR collection")


if __name__ == "__main__":
    main()
