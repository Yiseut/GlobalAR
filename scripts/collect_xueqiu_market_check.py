#!/usr/bin/env python3
"""Use Snowball/Xueqiu quote API as a market-data fallback.

The Snowball CLI supports no-login quote queries for A-shares, HK shares, and
US equities. Search and richer endpoints require login/cookie, so this script
only uses deterministic ticker candidates from our existing listing map.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_data import DATA_DIR


MARKET_CONFLICT_PATH = DATA_DIR / "market_snapshot_conflicts.csv"
XUEQIU_MARKET_CHECK_PATH = DATA_DIR / "xueqiu_market_check.csv"

MANUAL_SYMBOL_CANDIDATES = {
    # The seed table uses NASDAQ:NOVN, which Snowball/Yahoo resolve to a tiny
    # unrelated/stale US ticker. Novartis ADR is NVS.
    "Novartis": ["NVS"],
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_conflicts() -> list[dict[str, str]]:
    if not MARKET_CONFLICT_PATH.exists():
        raise SystemExit(f"Missing conflict report: {MARKET_CONFLICT_PATH}. Run build_progress_reports.py first.")
    with MARKET_CONFLICT_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def a_share_symbol(ticker: str) -> str:
    digits = re.sub(r"\D", "", ticker)
    if len(digits) != 6:
        return ""
    if digits.startswith(("6", "9")):
        return f"SH{digits}"
    return f"SZ{digits}"


def hk_symbol(ticker: str) -> str:
    digits = re.sub(r"\D", "", ticker)
    return digits.zfill(5) if digits else ""


def symbol_candidates(row: dict[str, str]) -> list[dict[str, str]]:
    company = norm(row.get("company"))
    stock_code = norm(row.get("stock_code"))
    exchange = norm(row.get("exchange")).upper()
    ticker = norm(row.get("ticker_symbol")) or stock_code
    if ":" in ticker:
        ticker = ticker.split(":", 1)[1]
    ticker = ticker.replace(".US", "").strip()
    candidates: list[dict[str, str]] = []
    for symbol in MANUAL_SYMBOL_CANDIDATES.get(company, []):
        candidates.append({"xueqiu_symbol": symbol, "candidate_reason": "manual_known_adr_or_corrected_symbol"})
    if exchange in {"NASDAQ", "NYSE", "NYSE AMERICAN", "AMEX"} and ticker:
        candidates.append({"xueqiu_symbol": ticker, "candidate_reason": "seed_us_ticker"})
    elif exchange in {"SZSE", "SSE"} or stock_code.endswith((".SZ", ".SS", ".SH")):
        symbol = a_share_symbol(ticker or stock_code)
        if symbol:
            candidates.append({"xueqiu_symbol": symbol, "candidate_reason": "seed_a_share_ticker"})
    elif exchange in {"HKEX", "SEHK"} or stock_code.upper().endswith(".HK"):
        symbol = hk_symbol(ticker or stock_code)
        if symbol:
            candidates.append({"xueqiu_symbol": symbol, "candidate_reason": "seed_hk_ticker"})
    seen = set()
    unique = []
    for item in candidates:
        key = item["xueqiu_symbol"]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def run_snowball_quote(symbols: list[str]) -> list[dict[str, Any]]:
    if not symbols:
        return []
    command = shutil.which("snowball") or shutil.which("snowball.cmd") or r"E:\shared\tools\npm-global\snowball.cmd"
    proc = subprocess.run(
        [command, "quote", *symbols],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip() or f"snowball exited with {proc.returncode}")
    text = proc.stdout.strip()
    if not text:
        return []
    return json.loads(text)


def quote_status(quote: dict[str, Any]) -> str:
    if not quote:
        return "not_found"
    if quote.get("market_capital") and quote.get("is_trade") is True:
        return "live_quote_with_market_cap"
    if quote.get("market_capital"):
        return "stale_or_non_trading_quote_with_market_cap"
    return "quote_without_market_cap"


def collect() -> dict[str, Any]:
    rows = read_conflicts()
    candidate_rows: list[dict[str, str]] = []
    for row in rows:
        for candidate in symbol_candidates(row):
            candidate_rows.append({**row, **candidate})
    symbols = [row["xueqiu_symbol"] for row in candidate_rows]
    quotes = {norm(item.get("symbol")): item for item in run_snowball_quote(symbols)}
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    output: list[dict[str, Any]] = []
    for row in candidate_rows:
        quote = quotes.get(row["xueqiu_symbol"], {})
        status = quote_status(quote)
        issue_hint = ""
        if row["company"] == "Novartis" and row["xueqiu_symbol"] == "NOVN":
            issue_hint = "Seed ticker appears wrong for Novartis; compare with NVS ADR and Swiss NOVN listing."
        elif status == "stale_or_non_trading_quote_with_market_cap":
            issue_hint = "Snowball found a quote but it is not actively trading; verify delisting, acquisition, OTC or stale symbol."
        elif status == "not_found":
            issue_hint = "Snowball did not return this symbol; use official exchange/local market source."
        output.append(
            {
                "company": row["company"],
                "seed_stock_code": row["stock_code"],
                "seed_exchange": row["exchange"],
                "seed_ticker_symbol": row["ticker_symbol"],
                "xueqiu_symbol": row["xueqiu_symbol"],
                "candidate_reason": row["candidate_reason"],
                "xueqiu_status": status,
                "current": quote.get("current", ""),
                "percent": quote.get("percent", ""),
                "market_capital_raw": quote.get("market_capital", ""),
                "float_market_capital_raw": quote.get("float_market_capital", ""),
                "is_trade": quote.get("is_trade", ""),
                "timestamp": quote.get("timestamp", ""),
                "captured_at": captured_at,
                "source": "snowball-cli / Xueqiu quote API",
                "source_url": f"https://xueqiu.com/S/{row['xueqiu_symbol']}",
                "issue_hint": issue_hint,
                "raw_json": json.dumps(quote, ensure_ascii=False, sort_keys=True) if quote else "",
            }
        )
    fieldnames = [
        "company",
        "seed_stock_code",
        "seed_exchange",
        "seed_ticker_symbol",
        "xueqiu_symbol",
        "candidate_reason",
        "xueqiu_status",
        "current",
        "percent",
        "market_capital_raw",
        "float_market_capital_raw",
        "is_trade",
        "timestamp",
        "captured_at",
        "source",
        "source_url",
        "issue_hint",
        "raw_json",
    ]
    XUEQIU_MARKET_CHECK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with XUEQIU_MARKET_CHECK_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)
    return {
        "conflict_rows": len(rows),
        "candidate_symbols": len(candidate_rows),
        "xueqiu_returned": len(quotes),
        "rows": len(output),
        "path": str(XUEQIU_MARKET_CHECK_PATH),
    }


def main() -> None:
    print(json.dumps(collect(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
