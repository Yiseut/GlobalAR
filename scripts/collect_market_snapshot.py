#!/usr/bin/env python3
"""Collect market valuation snapshots for listed companies.

The output is a dynamic layer consumed by build_data.py. It does not modify the
static company master or the source workbook.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

from build_data import DB_PATH, MARKET_SNAPSHOT_LIVE_PATH

MARKET_VALUATION_RANK_PATH = MARKET_SNAPSHOT_LIVE_PATH.parent / "market_valuation_rank.csv"

try:
    import yfinance as yf
except Exception:  # noqa: BLE001 - chart fallback still works for symbol sanity checks.
    yf = None

YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?range=5d&interval=1d"
YAHOO_QUOTE_SUMMARY = (
    "https://query2.finance.yahoo.com/v10/finance/quoteSummary/{symbol}"
    "?modules=summaryDetail,defaultKeyStatistics,financialData"
)
FX_TO_USD_SYMBOL = {
    "USD": "",
    "CHF": "CHFUSD=X",
    "HKD": "HKDUSD=X",
    "CNY": "CNYUSD=X",
    "CNH": "CNHUSD=X",
    "EUR": "EURUSD=X",
    "KRW": "KRWUSD=X",
    "ILS": "ILSUSD=X",
    "JPY": "JPYUSD=X",
    "TWD": "TWDUSD=X",
    "ZAR": "ZARUSD=X",
    "AUD": "AUDUSD=X",
    "GBP": "GBPUSD=X",
    "BRL": "BRLUSD=X",
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def fmt_number(value: Any, digits: int = 2) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""


def _snapshot_keys(row: dict[str, Any] | sqlite3.Row) -> list[str]:
    keys = []
    for field in ("company_id", "stock_code", "ticker_symbol", "company"):
        if isinstance(row, sqlite3.Row):
            value = norm(row[field] if field in row.keys() else "")
        else:
            value = norm(row.get(field))
        if value:
            keys.append(value.lower())
    return keys


def load_valuation_fallbacks() -> dict[str, dict[str, str]]:
    """Load previous valuation fields so a price-only refresh cannot erase market cap."""
    fallback: dict[str, dict[str, str]] = {}

    def add_row(row: dict[str, str]) -> None:
        if not norm(row.get("market_cap_usd_m")):
            return
        for key in _snapshot_keys(row):
            fallback.setdefault(key, row)

    for path in (MARKET_SNAPSHOT_LIVE_PATH, MARKET_VALUATION_RANK_PATH):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                add_row(row)
    return fallback


def preserve_valuation(row: dict[str, Any], company: sqlite3.Row, fallback: dict[str, dict[str, str]]) -> dict[str, Any]:
    if norm(row.get("market_cap_usd_m")):
        return row
    previous = None
    for key in _snapshot_keys(
        {
            "company_id": company["company_id"],
            "company": company["canonical_name"],
            "stock_code": company["stock_code"],
            "ticker_symbol": company["ticker_symbol"],
        }
    ):
        previous = fallback.get(key)
        if previous:
            break
    if not previous:
        return row

    row["market_cap_usd_m"] = norm(previous.get("market_cap_usd_m"))
    for field in (
        "pe_ratio",
        "pb_ratio",
        "eps_ttm",
        "net_profit_growth_yoy_pct",
        "financial_period",
        "filing_date",
        "metric_basis",
        "financial_refreshed_at",
    ):
        row[field] = norm(row.get(field)) or norm(previous.get(field))
    preserved_as_of = norm(previous.get("as_of"))
    preserved_source = norm(previous.get("source"))
    row["snapshot_status"] = "price_refreshed_valuation_carried_forward"
    row["note"] = (
        "Latest price/day-change refreshed when available; market-cap valuation is carried forward "
        f"from prior snapshot ({preserved_as_of or 'date unavailable'}, {preserved_source or 'source unavailable'}) "
        "because the realtime fallback source did not return valuation fields."
    )
    return row


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def yahoo_symbols(stock_code: str, exchange: str, ticker: str) -> list[str]:
    stock_code = norm(stock_code)
    exchange_upper = norm(exchange).upper()
    ticker = norm(ticker) or stock_code
    upper_stock = stock_code.upper()
    if "(XETRA)" in upper_stock:
        return [stock_code.split()[0] + ".DE"]
    if stock_code.endswith(".JSE"):
        return [stock_code[:-4] + ".JO"]
    if stock_code.endswith(".ASX"):
        return [stock_code[:-4] + ".AX"]
    if stock_code.endswith(".TWO"):
        return [stock_code.replace(".TWO", ".TWO"), stock_code.replace(".TWO", ".TW")]
    if ":" in stock_code:
        _, ticker = stock_code.split(":", 1)
    if exchange_upper in {"NASDAQ", "NYSE", "NYSE AMERICAN", "AMEX"}:
        return [ticker]
    if exchange_upper == "SIX":
        return [f"{ticker}.SW"]
    if exchange_upper == "HKEX":
        return [f"{ticker.zfill(4)}.HK"]
    if exchange_upper in {"KRX", "KOSDAQ"}:
        return [f"{ticker}.KQ", f"{ticker}.KS"]
    if exchange_upper in {"SZSE", "SSE"}:
        return [ticker if "." in ticker else f"{ticker}.SZ"]
    if exchange_upper == "BORSA ITALIANA":
        return [ticker if "." in ticker else f"{ticker}.MI"]
    if exchange_upper in {"TSE", "JPX"}:
        return [ticker if "." in ticker else f"{ticker}.T"]
    if exchange_upper == "LSE":
        return [ticker if "." in ticker else f"{ticker}.L"]
    if ticker:
        return [ticker]
    return []


def fetch_chart(symbol: str) -> dict[str, Any] | None:
    url = YAHOO_CHART.format(symbol=urllib.parse.quote(symbol))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GlobalAestheticsDashboard/0.1"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = (payload.get("chart") or {}).get("result") or []
    return result[0] if result else None


def fetch_quote_summary(symbol: str) -> dict[str, Any]:
    url = YAHOO_QUOTE_SUMMARY.format(symbol=urllib.parse.quote(symbol))
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GlobalAestheticsDashboard/0.1"})
    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.loads(response.read().decode("utf-8"))
    result = (((payload.get("quoteSummary") or {}).get("result") or [{}])[0]) or {}
    merged: dict[str, Any] = {}
    for module in ("summaryDetail", "defaultKeyStatistics", "financialData"):
        values = result.get(module) or {}
        if isinstance(values, dict):
            merged.update(values)
    return merged


def quote_value(summary: dict[str, Any], key: str) -> Any:
    value = summary.get(key)
    if isinstance(value, dict):
        return value.get("raw") if value.get("raw") is not None else value.get("fmt")
    return value


def day_change_pct(result: dict[str, Any], price: float | None) -> str:
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0].get("close") or [])
    values = [float(value) for value in closes if value is not None]
    if price is None or len(values) < 2:
        return ""
    previous = values[-2]
    if not previous:
        return ""
    return f"{((price - previous) / previous) * 100:.2f}"


def fast_info_value(info: Any, key: str) -> Any:
    if info is None:
        return None
    try:
        value = info.get(key) if hasattr(info, "get") else None
    except Exception:
        value = None
    if value is not None:
        return value
    try:
        return getattr(info, key)
    except Exception:
        return None


FX_CACHE: dict[str, float] = {"USD": 1.0}


def fx_to_usd(currency: str) -> float | None:
    currency = norm(currency).upper()
    if not currency:
        return None
    if currency in FX_CACHE:
        return FX_CACHE[currency]
    symbol = FX_TO_USD_SYMBOL.get(currency)
    if not symbol or yf is None:
        return None
    try:
        info = yf.Ticker(symbol).fast_info
        rate = fast_info_value(info, "last_price") or fast_info_value(info, "lastPrice")
        if rate:
            FX_CACHE[currency] = float(rate)
            return FX_CACHE[currency]
    except Exception:
        return None
    return None


def fetch_yfinance_snapshot(company: sqlite3.Row, symbol: str) -> dict[str, Any] | None:
    if yf is None:
        return None
    ticker = yf.Ticker(symbol)
    info = ticker.fast_info
    market_cap = fast_info_value(info, "market_cap") or fast_info_value(info, "marketCap")
    price = fast_info_value(info, "last_price") or fast_info_value(info, "lastPrice")
    currency = norm(fast_info_value(info, "currency")).upper()
    previous_close = fast_info_value(info, "previous_close") or fast_info_value(info, "previousClose")
    quote_summary: dict[str, Any] = {}
    try:
        quote_summary = fetch_quote_summary(symbol)
    except Exception:
        quote_summary = {}
    if market_cap is None:
        market_cap = quote_value(quote_summary, "marketCap")
    if price is None:
        price = quote_value(quote_summary, "regularMarketPrice") or quote_value(quote_summary, "currentPrice")
    if market_cap is None and price is None:
        return None
    rate = fx_to_usd(currency)
    market_cap_usd_m = ""
    if market_cap is not None and rate:
        market_cap_usd_m = f"{float(market_cap) * rate / 1_000_000:.2f}"
    day_change = ""
    if price is not None and previous_close:
        day_change = f"{((float(price) - float(previous_close)) / float(previous_close)) * 100:.2f}"
    as_of = datetime.now().astimezone().isoformat(timespec="seconds")
    pe_ratio = quote_value(quote_summary, "trailingPE") or quote_value(quote_summary, "forwardPE")
    pb_ratio = quote_value(quote_summary, "priceToBook")
    eps_ttm = quote_value(quote_summary, "trailingEps")
    earnings_growth = quote_value(quote_summary, "earningsGrowth")
    return {
        "company_id": company["company_id"],
        "company": company["canonical_name"],
        "stock_code": company["stock_code"],
        "exchange": company["exchange"],
        "ticker_symbol": company["ticker_symbol"],
        "yahoo_symbol": symbol,
        "listing_country": company["listing_country"],
        "as_of": as_of,
        "price": "" if price is None else str(price),
        "currency": currency,
        "market_cap_usd_m": market_cap_usd_m,
        "pe_ratio": fmt_number(pe_ratio),
        "pb_ratio": fmt_number(pb_ratio),
        "eps_ttm": fmt_number(eps_ttm),
        "net_profit_growth_yoy_pct": fmt_number(float(earnings_growth) * 100) if earnings_growth not in (None, "") else "",
        "financial_period": "",
        "filing_date": "",
        "metric_basis": "Yahoo Finance quote summary" if quote_summary else "",
        "market_refreshed_at": as_of,
        "financial_refreshed_at": "",
        "day_change_pct": day_change,
        "source": "yfinance / Yahoo Finance fast_info",
        "source_url": f"https://finance.yahoo.com/quote/{urllib.parse.quote(symbol)}",
        "snapshot_status": "valuation_fetched" if market_cap_usd_m else "valuation_partial",
        "note": (
            f"Market cap source currency: {currency or 'unknown'}; converted to USD million using live FX when available. "
            "Frontend displays valuation only, not share price."
        ),
    }


def snapshot_for(company: sqlite3.Row) -> dict[str, Any]:
    errors = []
    for symbol in yahoo_symbols(company["stock_code"], company["exchange"], company["ticker_symbol"]):
        try:
            yfinance_row = fetch_yfinance_snapshot(company, symbol)
            if yfinance_row:
                return yfinance_row
        except Exception as exc:  # noqa: BLE001 - keep chart fallback available.
            errors.append(f"{symbol} yfinance: {exc}")
        try:
            result = fetch_chart(symbol)
        except Exception as exc:  # noqa: BLE001 - keep other symbols flowing.
            errors.append(f"{symbol}: {exc}")
            continue
        if not result:
            continue
        meta = result.get("meta") or {}
        price = meta.get("regularMarketPrice") or meta.get("previousClose")
        as_of = ""
        if meta.get("regularMarketTime"):
            as_of = datetime.fromtimestamp(int(meta["regularMarketTime"])).astimezone().isoformat(timespec="seconds")
        source_url = YAHOO_CHART.format(symbol=symbol)
        return {
            "company_id": company["company_id"],
            "company": company["canonical_name"],
            "stock_code": company["stock_code"],
            "exchange": company["exchange"],
            "ticker_symbol": company["ticker_symbol"],
            "yahoo_symbol": symbol,
            "listing_country": company["listing_country"],
            "as_of": as_of,
            "price": "" if price is None else str(price),
            "currency": meta.get("currency") or "",
            "market_cap_usd_m": "",
            "pe_ratio": "",
            "pb_ratio": "",
            "eps_ttm": "",
            "net_profit_growth_yoy_pct": "",
            "financial_period": "",
            "filing_date": "",
            "metric_basis": "",
            "market_refreshed_at": as_of,
            "financial_refreshed_at": "",
            "day_change_pct": day_change_pct(result, float(price) if price is not None else None),
            "source": "Yahoo Finance chart API",
            "source_url": source_url,
            "snapshot_status": "valuation_missing_price_only" if price is not None else "valuation_missing",
            "note": "Only price was available from chart fallback. Frontend suppresses price and shows valuation as pending.",
        }
    return {
        "company_id": company["company_id"],
        "company": company["canonical_name"],
        "stock_code": company["stock_code"],
        "exchange": company["exchange"],
        "ticker_symbol": company["ticker_symbol"],
        "yahoo_symbol": "",
        "listing_country": company["listing_country"],
        "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
        "price": "",
        "currency": "",
        "market_cap_usd_m": "",
        "pe_ratio": "",
        "pb_ratio": "",
        "eps_ttm": "",
        "net_profit_growth_yoy_pct": "",
        "financial_period": "",
        "filing_date": "",
        "metric_basis": "",
        "market_refreshed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "financial_refreshed_at": "",
        "day_change_pct": "",
        "source": "Yahoo Finance chart API",
        "source_url": "",
        "snapshot_status": "valuation_fetch_failed",
        "note": "; ".join(errors[:3]) or "No compatible market symbol.",
    }


def collect(limit: int, sleep_seconds: float) -> dict[str, Any]:
    conn = connect()
    valuation_fallback = load_valuation_fallbacks()
    rows = conn.execute(
        """
        SELECT company_id, canonical_name, stock_code, exchange, ticker_symbol, listing_country
        FROM company_master
        WHERE stock_code IS NOT NULL AND stock_code != ''
        ORDER BY COALESCE(priority_rank, 9999), canonical_name
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    snapshots = []
    for company in rows:
        snapshots.append(preserve_valuation(snapshot_for(company), company, valuation_fallback))
        if sleep_seconds:
            time.sleep(sleep_seconds)
    conn.close()
    fieldnames = [
        "company_id",
        "company",
        "stock_code",
        "exchange",
        "ticker_symbol",
        "yahoo_symbol",
        "listing_country",
        "as_of",
        "price",
        "currency",
        "market_cap_usd_m",
        "pe_ratio",
        "pb_ratio",
        "eps_ttm",
        "net_profit_growth_yoy_pct",
        "financial_period",
        "filing_date",
        "metric_basis",
        "market_refreshed_at",
        "financial_refreshed_at",
        "day_change_pct",
        "source",
        "source_url",
        "snapshot_status",
        "note",
    ]
    MARKET_SNAPSHOT_LIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with MARKET_SNAPSHOT_LIVE_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(snapshots)
    return {
        "rows": len(snapshots),
        "valuation_fetched": sum(1 for row in snapshots if row["snapshot_status"] == "valuation_fetched"),
        "valuation_partial": sum(1 for row in snapshots if row["snapshot_status"] == "valuation_partial"),
        "valuation_carried_forward": sum(
            1 for row in snapshots if row["snapshot_status"] == "price_refreshed_valuation_carried_forward"
        ),
        "failed": sum(1 for row in snapshots if row["snapshot_status"] == "valuation_fetch_failed"),
        "path": str(MARKET_SNAPSHOT_LIVE_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--sleep", type=float, default=0.05)
    args = parser.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/build_data.py first.")
    print(json.dumps(collect(args.limit, args.sleep), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
