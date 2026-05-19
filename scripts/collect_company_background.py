#!/usr/bin/env python3
"""Collect review-stage company background and capital-structure evidence.

The collector writes durable staging files only. It does not update
Company_Master facts directly; build_data.py imports the staging files into
SQLite and the dashboard workbench.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from build_data import (
    COMPANY_BACKGROUND_EVIDENCE_PATH,
    COMPANY_CAPITAL_STRUCTURE_PATH,
    DB_PATH,
)


SEC_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SEC_USER_AGENT = "GlobalAestheticsVerification/0.1 contact: local-project@example.invalid"
SEC_EXCHANGES = {"NASDAQ", "NYSE", "NYSE AMERICAN", "NYSE ARCA", "AMEX"}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": SEC_USER_AGENT,
            "Accept-Encoding": "identity",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def load_sec_ticker_map() -> dict[str, dict[str, Any]]:
    payload = fetch_json(SEC_COMPANY_TICKERS_URL)
    if isinstance(payload, dict) and "fields" in payload and "data" in payload:
        fields = payload.get("fields") or []
        rows = [dict(zip(fields, row)) for row in payload.get("data") or []]
        return {
            norm(row.get("ticker")).upper(): {
                "cik_str": row.get("cik"),
                "title": row.get("name"),
                "ticker": row.get("ticker"),
                "exchange": row.get("exchange"),
            }
            for row in rows
            if norm(row.get("ticker"))
        }
    rows = payload.values() if isinstance(payload, dict) else payload
    return {norm(row.get("ticker")).upper(): row for row in rows if norm(row.get("ticker"))}


def is_us_sec_candidate(company: sqlite3.Row) -> bool:
    exchange = norm(company["exchange"]).upper()
    ticker = norm(company["ticker_symbol"]).upper()
    return bool(ticker) and (exchange in SEC_EXCHANGES or norm(company["listing_country"]).upper() == "US")


def load_existing_background() -> dict[tuple[str, str, str], dict[str, Any]]:
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not COMPANY_BACKGROUND_EVIDENCE_PATH.exists():
        return records
    for line in COMPANY_BACKGROUND_EVIDENCE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (item.get("company_id") or "", item.get("source_key") or "", item.get("field_name") or "")
        records[key] = item
    return records


def save_background(records: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    COMPANY_BACKGROUND_EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(records.values(), key=lambda item: (int(item.get("priority_rank") or 9999), item.get("company") or "", item.get("field_name") or ""))
    payload = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True) for item in rows)
    COMPANY_BACKGROUND_EVIDENCE_PATH.write_text(payload + ("\n" if payload else ""), encoding="utf-8")


def save_capital(rows: list[dict[str, Any]]) -> None:
    COMPANY_CAPITAL_STRUCTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "company_id",
        "priority_rank",
        "company",
        "ownership_seed",
        "stock_code_seed",
        "exchange_seed",
        "ticker_symbol_seed",
        "listing_country_seed",
        "sec_cik",
        "sec_entity_name",
        "sec_tickers",
        "sec_exchanges",
        "sec_former_names",
        "evidence_status",
        "source_url",
        "captured_at",
        "review_status",
        "notes",
    ]
    with COMPANY_CAPITAL_STRUCTURE_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def sec_field_evidence(company: sqlite3.Row, submission: dict[str, Any], source_url: str, captured_at: str) -> list[dict[str, Any]]:
    former_names = "; ".join(norm(item.get("name")) for item in submission.get("formerNames") or [] if norm(item.get("name")))
    fields = {
        "sec_cik": f"{int(submission.get('cik') or 0):010d}" if submission.get("cik") else "",
        "sec_entity_name": norm(submission.get("name")),
        "sec_tickers": ", ".join(submission.get("tickers") or []),
        "sec_exchanges": ", ".join(submission.get("exchanges") or []),
        "sec_former_names": former_names,
    }
    rows = []
    for field_name, field_value in fields.items():
        if not field_value:
            continue
        rows.append(
            {
                "company_id": company["company_id"],
                "company": company["canonical_name"],
                "priority_rank": company["priority_rank"],
                "fact_type": "capital_market_identity",
                "field_name": field_name,
                "field_value": field_value,
                "source_key": "sec_submissions",
                "source_name": "SEC EDGAR Submissions API",
                "source_url": source_url,
                "captured_at": captured_at,
                "confidence": "official_api_unreviewed",
                "review_status": "needs_review",
                "raw_json": {
                    "cik": submission.get("cik"),
                    "name": submission.get("name"),
                    "tickers": submission.get("tickers"),
                    "exchanges": submission.get("exchanges"),
                    "formerNames": submission.get("formerNames"),
                },
            }
        )
    return rows


def capital_row(
    company: sqlite3.Row,
    captured_at: str,
    sec_match: dict[str, Any] | None = None,
    submission: dict[str, Any] | None = None,
    error: str = "",
) -> dict[str, Any]:
    stock_code = norm(company["stock_code"])
    if submission:
        source_url = SEC_SUBMISSIONS_URL.format(cik=int(submission.get("cik") or sec_match.get("cik_str")))
        return {
            "company_id": company["company_id"],
            "priority_rank": company["priority_rank"],
            "company": company["canonical_name"],
            "ownership_seed": company["ownership"],
            "stock_code_seed": stock_code,
            "exchange_seed": company["exchange"],
            "ticker_symbol_seed": company["ticker_symbol"],
            "listing_country_seed": company["listing_country"],
            "sec_cik": f"{int(submission.get('cik') or sec_match.get('cik_str')):010d}",
            "sec_entity_name": norm(submission.get("name")),
            "sec_tickers": ", ".join(submission.get("tickers") or []),
            "sec_exchanges": ", ".join(submission.get("exchanges") or []),
            "sec_former_names": "; ".join(norm(item.get("name")) for item in submission.get("formerNames") or [] if norm(item.get("name"))),
            "evidence_status": "official_sec_verified",
            "source_url": source_url,
            "captured_at": captured_at,
            "review_status": "needs_review",
            "notes": "SEC verifies capital-market entity identity; product-company relationship still requires human review.",
        }
    if stock_code:
        return {
            "company_id": company["company_id"],
            "priority_rank": company["priority_rank"],
            "company": company["canonical_name"],
            "ownership_seed": company["ownership"],
            "stock_code_seed": stock_code,
            "exchange_seed": company["exchange"],
            "ticker_symbol_seed": company["ticker_symbol"],
            "listing_country_seed": company["listing_country"],
            "sec_cik": norm(sec_match.get("cik_str")) if sec_match else "",
            "sec_entity_name": norm(sec_match.get("title")) if sec_match else "",
            "sec_tickers": norm(sec_match.get("ticker")) if sec_match else "",
            "sec_exchanges": "",
            "sec_former_names": "",
            "evidence_status": "listed_needs_local_exchange_review",
            "source_url": SEC_COMPANY_TICKERS_URL if sec_match else "",
            "captured_at": captured_at,
            "review_status": "needs_review",
            "notes": error or "Ticker is from seed workbook; verify against the relevant exchange or securities filing.",
        }
    return {
        "company_id": company["company_id"],
        "priority_rank": company["priority_rank"],
        "company": company["canonical_name"],
        "ownership_seed": company["ownership"],
        "stock_code_seed": "",
        "exchange_seed": "",
        "ticker_symbol_seed": "",
        "listing_country_seed": "",
        "sec_cik": "",
        "sec_entity_name": "",
        "sec_tickers": "",
        "sec_exchanges": "",
        "sec_former_names": "",
        "evidence_status": "private_or_unlisted_seed",
        "source_url": "",
        "captured_at": captured_at,
        "review_status": "backlog",
        "notes": "No stock code in seed workbook.",
    }


def collect(limit_companies: int, sleep_seconds: float, include_all_listed: bool = False) -> dict[str, Any]:
    conn = connect()
    if include_all_listed:
        companies = conn.execute(
            """
            WITH selected AS (
                SELECT company_id, canonical_name, priority_rank, ownership, stock_code,
                       exchange, ticker_symbol, listing_country, product_count,
                       CASE
                         WHEN priority_rank IS NOT NULL THEN 0
                         WHEN COALESCE(stock_code, '') <> '' THEN 1
                         ELSE 2
                       END AS bucket
                FROM company_master
                WHERE priority_rank IS NOT NULL OR COALESCE(stock_code, '') <> ''
            )
            SELECT company_id, canonical_name, priority_rank, ownership, stock_code,
                   exchange, ticker_symbol, listing_country
            FROM selected
            ORDER BY bucket, COALESCE(priority_rank, 9999), product_count DESC, canonical_name
            """
        ).fetchall()
    else:
        companies = conn.execute(
            """
            SELECT company_id, canonical_name, priority_rank, ownership, stock_code,
                   exchange, ticker_symbol, listing_country
            FROM company_master
            WHERE priority_rank IS NOT NULL
            ORDER BY priority_rank
            LIMIT ?
            """,
            (limit_companies,),
        ).fetchall()
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    background = load_existing_background()
    capital_rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    sec_verified = 0
    sec_map: dict[str, dict[str, Any]] = {}
    try:
        sec_map = load_sec_ticker_map()
    except Exception as exc:  # noqa: BLE001 - keep non-US capital mapping useful if SEC is unavailable.
        errors.append({"source": "sec_company_tickers", "error": str(exc)})

    for company in companies:
        ticker = norm(company["ticker_symbol"]).upper()
        sec_match = sec_map.get(ticker) if ticker else None
        submission = None
        error = ""
        if sec_match and is_us_sec_candidate(company):
            try:
                source_url = SEC_SUBMISSIONS_URL.format(cik=int(sec_match["cik_str"]))
                submission = fetch_json(source_url)
                for item in sec_field_evidence(company, submission, source_url, captured_at):
                    key = (item["company_id"], item["source_key"], item["field_name"])
                    background[key] = item
                sec_verified += 1
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, ValueError) as exc:
                error = f"SEC submission fetch failed: {exc}"
                errors.append({"company": company["canonical_name"], "ticker": ticker, "error": error})
        capital_rows.append(capital_row(company, captured_at, sec_match=sec_match, submission=submission, error=error))

    save_background(background)
    save_capital(capital_rows)
    conn.close()
    return {
        "companies": len(companies),
        "capital_rows": len(capital_rows),
        "background_evidence_rows": len(background),
        "sec_verified_companies": sec_verified,
        "background_path": str(COMPANY_BACKGROUND_EVIDENCE_PATH),
        "capital_path": str(COMPANY_CAPITAL_STRUCTURE_PATH),
        "errors": errors[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", type=int, default=37, help="Number of priority companies to stage.")
    parser.add_argument("--sleep", type=float, default=0.1, help="Delay between SEC submission calls.")
    parser.add_argument(
        "--include-all-listed",
        action="store_true",
        help="Include every workbook company with a stock code, in addition to the priority companies.",
    )
    args = parser.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/build_data.py first.")
    print(json.dumps(collect(args.companies, args.sleep, args.include_all_listed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
