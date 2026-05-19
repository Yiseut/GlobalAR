#!/usr/bin/env python3
"""Build a review batch for listed companies and related subsidiaries.

This script does not merge facts into Company_Master. It creates a long-lived
review table that groups workbook companies by ticker/stock code and stages
the best available official capital-market evidence for human review.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from build_data import DB_PATH, LISTED_COMPANY_BATCH_PATH, MARKET_SNAPSHOT_LIVE_PATH, stable_id
from collect_company_background import (
    SEC_COMPANY_TICKERS_URL,
    SEC_SUBMISSIONS_URL,
    SEC_USER_AGENT,
    fetch_json,
    is_us_sec_candidate,
    load_sec_ticker_map,
    norm,
)


FIELDNAMES = [
    "batch_id",
    "company_id",
    "priority_rank",
    "company",
    "listing_group_key",
    "listed_entity_name",
    "relation_to_listed_entity",
    "related_companies",
    "related_company_ids",
    "related_product_count",
    "stock_code",
    "exchange",
    "ticker_symbol",
    "listing_country",
    "ownership_seed",
    "parent_company_seed",
    "ultimate_parent_seed",
    "product_count",
    "brand_count",
    "primary_track",
    "sec_cik",
    "sec_entity_name",
    "sec_exchange_current",
    "listing_verification_status",
    "official_source_key",
    "official_source_url",
    "market_snapshot_status",
    "market_price",
    "market_currency",
    "market_day_change_pct",
    "market_source_url",
    "market_captured_at",
    "review_status",
    "notes",
]

US_EXCHANGES = {"NASDAQ", "NYSE", "NYSE AMERICAN", "NYSE ARCA", "AMEX"}
EXCHANGE_LABELS = {
    "NASDAQ": "sec_edgar",
    "NYSE": "sec_edgar",
    "NYSE AMERICAN": "sec_edgar",
    "NYSE ARCA": "sec_edgar",
    "AMEX": "sec_edgar",
    "SIX": "six_official_company_page",
    "HKEX": "hkex_official_quote",
    "KRX": "krx_official_market_data",
    "SZSE": "szse_official_security_profile",
    "BORSA ITALIANA": "borsa_italiana_official_search",
    "TA": "tase_official_security_page",
    "T": "jpx_official_listing_search",
    "TW": "twse_official_profile",
    "TWO": "tpex_official_profile",
    "ASX": "asx_official_company_page",
    "PA": "euronext_official_search",
    "BR": "euronext_brussels_official_search",
    "JSE": "jse_official_issuer_page",
    "OTC": "otcmarkets_official_quote",
}


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def stock_group_key(stock_code: str, exchange: str, ticker: str) -> str:
    raw = norm(stock_code) or ":".join(part for part in [norm(exchange), norm(ticker)] if part)
    return re.sub(r"\s+", "", raw.upper())


def normalized_exchange(exchange: str, stock_code: str, ticker: str) -> str:
    exchange = norm(exchange).upper()
    if exchange:
        return exchange
    code = norm(stock_code).upper()
    if ":" in code:
        return code.split(":", 1)[0].strip()
    if ticker.endswith(".MI"):
        return "BORSA ITALIANA"
    if ticker.endswith(".PA"):
        return "PA"
    if ticker.endswith(".BR"):
        return "BR"
    if ticker.endswith(".ASX"):
        return "ASX"
    if ticker.endswith(".T"):
        return "T"
    if ticker.endswith(".TW"):
        return "TW"
    if ticker.endswith(".TWO"):
        return "TWO"
    if ticker.endswith(".JSE"):
        return "JSE"
    return exchange


def ticker_core(ticker: str, stock_code: str) -> str:
    ticker = norm(ticker)
    if not ticker and ":" in norm(stock_code):
        ticker = norm(stock_code).split(":", 1)[1]
    return ticker


def sec_submission(cik: Any) -> dict[str, Any]:
    return fetch_json(SEC_SUBMISSIONS_URL.format(cik=int(cik)))


def sec_company_search(company: str) -> tuple[str, str, str]:
    query = urllib.parse.quote(company)
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={query}&owner=exclude&count=10"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "identity"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "ignore")
    candidates = []
    for match in re.finditer(r"CIK=(\d{1,10})", html):
        cik = match.group(1)
        if cik not in candidates:
            candidates.append(cik)
    return (candidates[0], url, html[:600]) if candidates else ("", url, html[:600])


def official_exchange_url(exchange: str, ticker: str, stock_code: str) -> str:
    exchange = normalized_exchange(exchange, stock_code, ticker)
    ticker = ticker_core(ticker, stock_code)
    ticker_upper = ticker.upper()
    ticker_plain = ticker_upper.split(".")[0]
    if exchange in US_EXCHANGES:
        return f"https://www.nasdaq.com/market-activity/stocks/{ticker_plain.lower()}"
    if exchange == "SIX":
        return f"https://www.six-group.com/en/market-data/shares/company-information.html?valorSymbol={ticker_plain}"
    if exchange == "HKEX":
        return f"https://www.hkex.com.hk/Market-Data/Securities-Prices/Equities/Equities-Quote?sym={ticker_plain}&sc_lang=en"
    if exchange == "KRX":
        return "http://data.krx.co.kr/contents/MDC/MAIN/main/index.cmd"
    if exchange == "SZSE":
        digits = re.sub(r"\D", "", ticker_plain)
        return f"https://www.szse.cn/certificate/individual/index.html?code={digits}" if digits else "https://www.szse.cn/English/"
    if exchange == "BORSA ITALIANA":
        return f"https://www.borsaitaliana.it/borsa/azioni/cerca.html?lang=en&search={ticker_plain}"
    if exchange == "TA":
        return f"https://market.tase.co.il/en/market_data/security/{ticker_plain}/major_data"
    if exchange == "ASX":
        return f"https://www.asx.com.au/markets/company/{ticker_plain}"
    if exchange == "T":
        return f"https://www.jpx.co.jp/english/listing/stocks/new/index.html?query={ticker_plain}"
    if exchange == "TW":
        return f"https://www.twse.com.tw/en/products/system/company.html?stockNo={ticker_plain}"
    if exchange == "TWO":
        return f"https://www.tpex.org.tw/web/stock/regular_emerging/corporateInfo/regular/regular_stock_detail.php?stk_code={ticker_plain}&l=en-us"
    if exchange in {"PA", "BR"}:
        return f"https://live.euronext.com/en/search_instruments/{ticker_plain}"
    if exchange == "JSE":
        return f"https://www.jse.co.za/companies-and-financial-instruments?search={ticker_plain}"
    if exchange == "OTC":
        return f"https://www.otcmarkets.com/stock/{ticker_plain}/overview"
    return ""


def load_market_live() -> dict[str, dict[str, str]]:
    if not MARKET_SNAPSHOT_LIVE_PATH.exists():
        return {}
    with MARKET_SNAPSHOT_LIVE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapped: dict[str, dict[str, str]] = {}
    for row in rows:
        for key in [row.get("company_id"), row.get("stock_code"), row.get("ticker_symbol")]:
            if key:
                mapped[key] = row
    return mapped


def load_companies() -> list[sqlite3.Row]:
    return connect().execute(
        """
        SELECT company_id, canonical_name, priority_rank, ownership, stock_code, exchange,
               ticker_symbol, listing_country, parent_company, ultimate_parent,
               product_count, brand_count, primary_track
        FROM company_master
        WHERE COALESCE(stock_code, '') <> ''
        ORDER BY COALESCE(priority_rank, 9999), product_count DESC, canonical_name
        """
    ).fetchall()


def choose_group_entity(group: list[sqlite3.Row], sec_info: dict[str, str]) -> str:
    if sec_info.get("sec_entity_name"):
        return sec_info["sec_entity_name"]
    if len(group) == 1:
        row = group[0]
        company = norm(row["canonical_name"]).lower()
        for field in ["ultimate_parent", "parent_company"]:
            value = norm(row[field])
            if value and value.lower() != company:
                return value
    public_rows = [row for row in group if norm(row["ownership"]).lower() == "public"]
    if public_rows:
        return sorted(public_rows, key=lambda row: (int(row["priority_rank"] or 9999), -int(row["product_count"] or 0)))[0][
            "canonical_name"
        ]
    for row in group:
        for field in ["ultimate_parent", "parent_company"]:
            if norm(row[field]) and norm(row[field]).lower() != norm(row["canonical_name"]).lower():
                return norm(row[field])
    return group[0]["canonical_name"]


def relation(row: sqlite3.Row, listed_entity: str, group_size: int) -> str:
    company = norm(row["canonical_name"]).lower()
    parent = norm(row["parent_company"]).lower()
    ultimate = norm(row["ultimate_parent"]).lower()
    listed = norm(listed_entity).lower()
    if parent or (ultimate and ultimate != company) or norm(row["ownership"]).lower() == "subsidiary":
        return "subsidiary_or_affiliate"
    if norm(row["ownership"]).lower() == "public" and (company in listed or listed in company or group_size == 1):
        return "listed_entity_self"
    if group_size > 1:
        return "same_ticker_related_company"
    return "listed_entity_candidate"


def sec_status(row: sqlite3.Row, sec_map: dict[str, dict[str, Any]]) -> dict[str, str]:
    ticker = ticker_core(row["ticker_symbol"], row["stock_code"]).upper()
    exchange = normalized_exchange(row["exchange"], row["stock_code"], ticker)
    if not is_us_sec_candidate(row):
        return {
            "sec_cik": "",
            "sec_entity_name": "",
            "sec_exchange_current": "",
            "listing_verification_status": "non_us_exchange_review_target",
            "official_source_key": EXCHANGE_LABELS.get(exchange, "exchange_official_review_target"),
            "official_source_url": official_exchange_url(exchange, ticker, row["stock_code"]),
            "notes": "Non-US listing: generated official exchange review target; listing identity still needs human review.",
        }
    sec_match = sec_map.get(ticker)
    if sec_match:
        submission = sec_submission(sec_match["cik_str"])
        exchanges = ", ".join(submission.get("exchanges") or [norm(sec_match.get("exchange"))])
        return {
            "sec_cik": f"{int(submission.get('cik') or sec_match['cik_str']):010d}",
            "sec_entity_name": norm(submission.get("name")) or norm(sec_match.get("title")),
            "sec_exchange_current": exchanges,
            "listing_verification_status": "official_sec_current_listing",
            "official_source_key": "sec_edgar_submissions",
            "official_source_url": SEC_SUBMISSIONS_URL.format(cik=int(submission.get("cik") or sec_match["cik_str"])),
            "notes": "SEC current ticker/exchange file and submissions API verify the listed entity identity; product relationship still needs review.",
        }
    try:
        cik, search_url, _ = sec_company_search(row["canonical_name"])
        if cik:
            submission = sec_submission(cik)
            return {
                "sec_cik": f"{int(submission.get('cik') or cik):010d}",
                "sec_entity_name": norm(submission.get("name")),
                "sec_exchange_current": ", ".join(submission.get("exchanges") or []),
                "listing_verification_status": "sec_registrant_name_match_not_current_ticker",
                "official_source_key": "sec_edgar_company_search",
                "official_source_url": search_url,
                "notes": "SEC company-name search found a registrant, but the seed ticker is not in the SEC current ticker/exchange file; treat as stale/delisted/transaction candidate until reviewed.",
            }
    except Exception as exc:  # noqa: BLE001 - keep the batch useful when a name search fails.
        return {
            "sec_cik": "",
            "sec_entity_name": "",
            "sec_exchange_current": "",
            "listing_verification_status": "us_listing_needs_manual_review",
            "official_source_key": "sec_edgar_company_search",
            "official_source_url": official_exchange_url(exchange, ticker, row["stock_code"]),
            "notes": f"SEC current ticker lookup missed and name search failed: {exc}",
        }
    return {
        "sec_cik": "",
        "sec_entity_name": "",
        "sec_exchange_current": "",
        "listing_verification_status": "us_seed_ticker_not_current_sec",
        "official_source_key": "sec_current_ticker_exchange",
        "official_source_url": SEC_COMPANY_TICKERS_URL,
        "notes": "US seed ticker is not present in the SEC current ticker/exchange file; verify delisting, acquisition, ticker change, or seed error.",
    }


def collect(sleep_seconds: float = 0.1) -> dict[str, Any]:
    companies = load_companies()
    market_live = load_market_live()
    sec_map = load_sec_ticker_map()
    groups: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in companies:
        groups[stock_group_key(row["stock_code"], row["exchange"], row["ticker_symbol"])].append(row)

    sec_by_group: dict[str, dict[str, str]] = {}
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for group_key, group in groups.items():
        representative = sorted(group, key=lambda row: (int(row["priority_rank"] or 9999), -int(row["product_count"] or 0)))[0]
        try:
            sec_info = sec_status(representative, sec_map)
            if sleep_seconds and sec_info.get("official_source_key", "").startswith("sec_"):
                time.sleep(sleep_seconds)
        except Exception as exc:  # noqa: BLE001
            sec_info = {
                "sec_cik": "",
                "sec_entity_name": "",
                "sec_exchange_current": "",
                "listing_verification_status": "listing_evidence_fetch_failed",
                "official_source_key": "",
                "official_source_url": official_exchange_url(representative["exchange"], representative["ticker_symbol"], representative["stock_code"]),
                "notes": str(exc),
            }
            errors.append({"stock_code": representative["stock_code"], "company": representative["canonical_name"], "error": str(exc)})
        sec_by_group[group_key] = sec_info

        listed_entity = choose_group_entity(group, sec_info)
        related_companies = "; ".join(row["canonical_name"] for row in group)
        related_company_ids = "; ".join(row["company_id"] for row in group)
        related_product_count = sum(int(row["product_count"] or 0) for row in group)
        for row in sorted(group, key=lambda item: (int(item["priority_rank"] or 9999), item["canonical_name"])):
            market = market_live.get(row["company_id"]) or market_live.get(row["stock_code"]) or market_live.get(row["ticker_symbol"]) or {}
            status = sec_info.get("listing_verification_status") or "needs_review"
            review_status = "needs_review"
            if status in {"official_sec_current_listing"} and relation(row, listed_entity, len(group)) == "listed_entity_self":
                review_status = "review_ready_official_listing"
            rows.append(
                {
                    "batch_id": stable_id("listed", row["company_id"], group_key),
                    "company_id": row["company_id"],
                    "priority_rank": row["priority_rank"] or "",
                    "company": row["canonical_name"],
                    "listing_group_key": group_key,
                    "listed_entity_name": listed_entity,
                    "relation_to_listed_entity": relation(row, listed_entity, len(group)),
                    "related_companies": related_companies,
                    "related_company_ids": related_company_ids,
                    "related_product_count": related_product_count,
                    "stock_code": row["stock_code"],
                    "exchange": normalized_exchange(row["exchange"], row["stock_code"], row["ticker_symbol"]),
                    "ticker_symbol": ticker_core(row["ticker_symbol"], row["stock_code"]),
                    "listing_country": row["listing_country"],
                    "ownership_seed": row["ownership"],
                    "parent_company_seed": row["parent_company"],
                    "ultimate_parent_seed": row["ultimate_parent"],
                    "product_count": row["product_count"] or 0,
                    "brand_count": row["brand_count"] or 0,
                    "primary_track": row["primary_track"],
                    "sec_cik": sec_info.get("sec_cik", ""),
                    "sec_entity_name": sec_info.get("sec_entity_name", ""),
                    "sec_exchange_current": sec_info.get("sec_exchange_current", ""),
                    "listing_verification_status": status,
                    "official_source_key": sec_info.get("official_source_key", ""),
                    "official_source_url": sec_info.get("official_source_url", ""),
                    "market_snapshot_status": market.get("snapshot_status", ""),
                    "market_price": market.get("price", ""),
                    "market_currency": market.get("currency", ""),
                    "market_day_change_pct": market.get("day_change_pct", ""),
                    "market_source_url": market.get("source_url", ""),
                    "market_captured_at": market.get("as_of", ""),
                    "review_status": review_status,
                    "notes": sec_info.get("notes", ""),
                }
            )

    LISTED_COMPANY_BATCH_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LISTED_COMPANY_BATCH_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "rows": len(rows),
        "listed_groups": len(groups),
        "status_counts": dict(sorted({row["listing_verification_status"]: 0 for row in rows}.items())),
        "official_sec_current_groups": sum(
            1 for item in sec_by_group.values() if item.get("listing_verification_status") == "official_sec_current_listing"
        ),
        "output_path": str(LISTED_COMPANY_BATCH_PATH),
        "captured_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "errors": errors[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sleep", type=float, default=0.1, help="Delay after SEC requests.")
    args = parser.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/build_data.py first.")
    summary = collect(args.sleep)
    with LISTED_COMPANY_BATCH_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        status_counts: dict[str, int] = defaultdict(int)
        relation_counts: dict[str, int] = defaultdict(int)
        for row in csv.DictReader(handle):
            status_counts[row.get("listing_verification_status", "")] += 1
            relation_counts[row.get("relation_to_listed_entity", "")] += 1
    summary["status_counts"] = dict(sorted(status_counts.items()))
    summary["relation_counts"] = dict(sorted(relation_counts.items()))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
