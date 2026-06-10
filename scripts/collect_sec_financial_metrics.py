#!/usr/bin/env python3
"""Collect SEC XBRL financial metrics for listed companies with CIKs."""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
LISTED_PATH = DATA_DIR / "listed_company_batch.csv"
MARKET_PATH = DATA_DIR / "market_snapshot_live.csv"
OUTPUT_PATH = DATA_DIR / "company_financial_metrics.csv"

USER_AGENT = "GlobalAestheticsDashboard data maintenance contact@example.com"

REVENUE_CONCEPTS = [
    ("us-gaap", "RevenueFromContractWithCustomerExcludingAssessedTax"),
    ("us-gaap", "Revenues"),
    ("us-gaap", "SalesRevenueNet"),
    ("us-gaap", "SalesRevenueGoodsNet"),
]
GROSS_PROFIT_CONCEPTS = [("us-gaap", "GrossProfit")]
NET_INCOME_CONCEPTS = [
    ("us-gaap", "NetIncomeLoss"),
    ("us-gaap", "ProfitLoss"),
    ("us-gaap", "NetIncomeLossAvailableToCommonStockholdersBasic"),
    ("us-gaap", "NetIncomeLossAttributableToParent"),
]
EPS_DILUTED_CONCEPTS = [
    ("us-gaap", "EarningsPerShareDiluted"),
    ("us-gaap", "EarningsPerShareBasicAndDiluted"),
]
EPS_BASIC_CONCEPTS = [("us-gaap", "EarningsPerShareBasic")]
EQUITY_CONCEPTS = [
    ("us-gaap", "StockholdersEquity"),
    ("us-gaap", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"),
    ("us-gaap", "StockholdersEquityAttributableToParent"),
]


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def fmt_number(value: Any, digits: int = 2) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{float(value):.{digits}f}".rstrip("0").rstrip(".")
    except (TypeError, ValueError):
        return ""


def load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def market_caps_by_company() -> dict[str, float]:
    out = {}
    for row in load_csv(MARKET_PATH):
        try:
            value = float(norm(row.get("market_cap_usd_m")) or 0)
        except ValueError:
            value = 0
        if value:
            for key in [row.get("company_id"), row.get("company"), row.get("stock_code"), row.get("ticker_symbol")]:
                if norm(key):
                    out[norm(key).lower()] = value
    return out


def fetch_companyfacts(cik: str) -> dict[str, Any]:
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik.zfill(10)}.json"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


def candidate_facts(
    payload: dict[str, Any],
    concepts: list[tuple[str, str]],
    allowed_units: set[str] | None = None,
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    all_facts = payload.get("facts") or {}
    for taxonomy, concept in concepts:
        units = (((all_facts.get(taxonomy) or {}).get(concept) or {}).get("units") or {})
        for unit, rows in units.items():
            if allowed_units is not None and unit not in allowed_units:
                continue
            for row in rows:
                form = norm(row.get("form"))
                fp = norm(row.get("fp"))
                frame = norm(row.get("frame"))
                if form not in {"10-K", "20-F"} and not frame.startswith("CY"):
                    continue
                value = row.get("val")
                if value in (None, ""):
                    continue
                try:
                    numeric = float(value)
                except (TypeError, ValueError):
                    continue
                facts.append(
                    {
                        "concept": concept,
                        "value": numeric,
                        "fy": row.get("fy"),
                        "fp": fp,
                        "form": form,
                        "unit": unit,
                        "filed": norm(row.get("filed")),
                        "end": norm(row.get("end")),
                        "accn": norm(row.get("accn")),
                    }
                )
    return sorted(facts, key=lambda item: (str(item.get("fy") or ""), item.get("filed") or "", item.get("end") or ""), reverse=True)


def annual_facts(
    payload: dict[str, Any],
    concepts: list[tuple[str, str]],
    allowed_units: set[str] | None = None,
) -> list[dict[str, Any]]:
    facts = candidate_facts(payload, concepts, allowed_units)
    annual = [row for row in facts if row.get("form") in {"10-K", "20-F"} and row.get("fp") == "FY"]
    return annual or facts


def latest_annual_fact(
    payload: dict[str, Any],
    concepts: list[tuple[str, str]],
    allowed_units: set[str] | None = None,
) -> dict[str, Any] | None:
    facts = annual_facts(payload, concepts, allowed_units)
    return (facts or [None])[0]


def previous_annual_fact(facts: list[dict[str, Any]], latest: dict[str, Any] | None) -> dict[str, Any] | None:
    if not latest:
        return None
    try:
        latest_fy = int(latest.get("fy"))
    except (TypeError, ValueError):
        latest_fy = None
    for row in facts:
        if row is latest:
            continue
        if latest_fy is None:
            if row.get("filed") != latest.get("filed") or row.get("end") != latest.get("end"):
                return row
            continue
        try:
            fy = int(row.get("fy"))
        except (TypeError, ValueError):
            continue
        if fy < latest_fy:
            return row
    return None


def collect(limit: int, sleep: float) -> dict[str, Any]:
    listed = [row for row in load_csv(LISTED_PATH) if norm(row.get("sec_cik"))]
    if limit:
        listed = listed[:limit]
    market_caps = market_caps_by_company()
    previous_rows = {norm(row.get("company_id")): row for row in load_csv(OUTPUT_PATH) if norm(row.get("company_id"))}
    rows: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
    for item in listed:
        cik = norm(item.get("sec_cik")).lstrip("0") or norm(item.get("sec_cik"))
        try:
            payload = fetch_companyfacts(cik)
        except Exception as exc:  # noqa: BLE001
            errors.append({"company": norm(item.get("company")), "sec_cik": norm(item.get("sec_cik")), "error": str(exc)})
            previous = previous_rows.get(norm(item.get("company_id")))
            if previous:
                previous = dict(previous)
                previous["note"] = (
                    norm(previous.get("note"))
                    + " Latest refresh failed; preserved previous successful SEC XBRL row."
                ).strip()
                rows.append(previous)
            continue
        revenue = latest_annual_fact(payload, REVENUE_CONCEPTS, {"USD"})
        gross = latest_annual_fact(payload, GROSS_PROFIT_CONCEPTS, {"USD"})
        net_income_facts = annual_facts(payload, NET_INCOME_CONCEPTS, {"USD"})
        net_income = net_income_facts[0] if net_income_facts else None
        previous_net_income = previous_annual_fact(net_income_facts, net_income)
        eps_diluted = latest_annual_fact(payload, EPS_DILUTED_CONCEPTS, {"USD/shares"})
        eps_basic = latest_annual_fact(payload, EPS_BASIC_CONCEPTS, {"USD/shares"})
        equity = latest_annual_fact(payload, EQUITY_CONCEPTS, {"USD"})
        revenue_usd_m = ""
        gross_margin_pct = ""
        ps_ratio = ""
        pe_ratio = ""
        pb_ratio = ""
        revenue_year = ""
        net_income_growth_yoy_pct = ""
        if revenue:
            revenue_usd_m = f"{revenue['value'] / 1_000_000:.2f}"
            revenue_year = str(revenue.get("fy") or "")
        if revenue and gross and revenue["value"]:
            gross_margin_pct = f"{(gross['value'] / revenue['value']) * 100:.2f}"
        if net_income and previous_net_income and previous_net_income.get("value"):
            net_income_growth_yoy_pct = fmt_number(
                ((net_income["value"] - previous_net_income["value"]) / abs(previous_net_income["value"])) * 100
            )
        market_cap = 0.0
        for key in [item.get("company_id"), item.get("company"), item.get("stock_code"), item.get("ticker_symbol")]:
            market_cap = market_caps.get(norm(key).lower(), 0.0)
            if market_cap:
                break
        if market_cap and revenue and revenue["value"]:
            ps_ratio = f"{market_cap / (revenue['value'] / 1_000_000):.2f}"
        if market_cap and net_income and net_income["value"]:
            pe_ratio = fmt_number(market_cap / (net_income["value"] / 1_000_000))
        if market_cap and equity and equity["value"]:
            pb_ratio = fmt_number(market_cap / (equity["value"] / 1_000_000))
        rows.append(
            {
                "company_id": norm(item.get("company_id")),
                "company": norm(item.get("company")),
                "stock_code": norm(item.get("stock_code")),
                "ticker_symbol": norm(item.get("ticker_symbol")),
                "sec_cik": norm(item.get("sec_cik")).zfill(10),
                "sec_entity_name": norm(payload.get("entityName")) or norm(item.get("sec_entity_name")),
                "fiscal_year": revenue_year,
                "revenue_usd_m": revenue_usd_m,
                "gross_profit_usd_m": "" if not gross else f"{gross['value'] / 1_000_000:.2f}",
                "gross_margin_pct": gross_margin_pct,
                "net_income_usd_m": "" if not net_income else f"{net_income['value'] / 1_000_000:.2f}",
                "net_income_growth_yoy_pct": net_income_growth_yoy_pct,
                "stockholders_equity_usd_m": "" if not equity else f"{equity['value'] / 1_000_000:.2f}",
                "market_cap_usd_m": "" if not market_cap else f"{market_cap:.2f}",
                "ps_ratio": ps_ratio,
                "pe_ratio": pe_ratio,
                "pb_ratio": pb_ratio,
                "eps_basic": "" if not eps_basic else fmt_number(eps_basic.get("value")),
                "eps_diluted": "" if not eps_diluted else fmt_number(eps_diluted.get("value")),
                "eps_ttm": "" if not (eps_diluted or eps_basic) else fmt_number((eps_diluted or eps_basic).get("value")),
                "revenue_concept": "" if not revenue else revenue["concept"],
                "gross_profit_concept": "" if not gross else gross["concept"],
                "net_income_concept": "" if not net_income else net_income["concept"],
                "equity_concept": "" if not equity else equity["concept"],
                "eps_concept": "" if not (eps_diluted or eps_basic) else (eps_diluted or eps_basic)["concept"],
                "revenue_filed": "" if not revenue else norm(revenue.get("filed")),
                "filing_date": norm((revenue or net_income or eps_diluted or eps_basic or {}).get("filed")),
                "financial_period": f"FY{revenue_year}" if revenue_year else "",
                "metric_basis": "SEC annual XBRL companyfacts",
                "source_url": f"https://data.sec.gov/api/xbrl/companyfacts/CIK{norm(item.get('sec_cik')).zfill(10)}.json",
                "captured_at": captured_at,
                "review_status": "official_sec_xbrl_auto",
                "note": "SEC XBRL annual revenue/gross profit; market cap is the dashboard dynamic market snapshot, so P/S is a derived snapshot ratio.",
            }
        )
        if sleep:
            time.sleep(sleep)
    fieldnames = [
        "company_id",
        "company",
        "stock_code",
        "ticker_symbol",
        "sec_cik",
        "sec_entity_name",
        "fiscal_year",
        "revenue_usd_m",
        "gross_profit_usd_m",
        "gross_margin_pct",
        "net_income_usd_m",
        "net_income_growth_yoy_pct",
        "stockholders_equity_usd_m",
        "market_cap_usd_m",
        "ps_ratio",
        "pe_ratio",
        "pb_ratio",
        "eps_basic",
        "eps_diluted",
        "eps_ttm",
        "revenue_concept",
        "gross_profit_concept",
        "net_income_concept",
        "equity_concept",
        "eps_concept",
        "revenue_filed",
        "filing_date",
        "financial_period",
        "metric_basis",
        "source_url",
        "captured_at",
        "review_status",
        "note",
    ]
    with OUTPUT_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "rows": len(rows),
        "with_revenue": sum(1 for row in rows if row.get("revenue_usd_m")),
        "with_gross_margin": sum(1 for row in rows if row.get("gross_margin_pct")),
        "with_eps": sum(1 for row in rows if row.get("eps_ttm")),
        "with_net_profit_growth": sum(1 for row in rows if row.get("net_income_growth_yoy_pct")),
        "with_ps_ratio": sum(1 for row in rows if row.get("ps_ratio")),
        "with_pe_ratio": sum(1 for row in rows if row.get("pe_ratio")),
        "with_pb_ratio": sum(1 for row in rows if row.get("pb_ratio")),
        "errors": errors,
        "path": str(OUTPUT_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--sleep", type=float, default=0.12)
    args = parser.parse_args()
    print(json.dumps(collect(args.limit, args.sleep), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
