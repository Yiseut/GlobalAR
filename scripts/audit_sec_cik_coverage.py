#!/usr/bin/env python3
"""Audit SEC CIK coverage for listed company batch."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDITS_DIR = DATA_DIR / "audits"
LISTED_PATH = DATA_DIR / "listed_company_batch.csv"
CAPITAL_PATH = DATA_DIR / "company_capital_structure.csv"
SEC_EXCHANGES = {"NASDAQ", "NYSE", "NYSE AMERICAN", "AMEX", "OTC"}


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def has_value(value: str | None) -> bool:
    return bool((value or "").strip())


def audit() -> dict[str, object]:
    listed = load_csv(LISTED_PATH)
    capital = load_csv(CAPITAL_PATH)
    listed_total = len(listed)
    listed_sec = [row for row in listed if has_value(row.get("sec_cik"))]
    sec_applicable = [
        row
        for row in listed
        if (row.get("exchange") or "").upper() in SEC_EXCHANGES
        or (row.get("listing_country") or "").upper() == "US"
        or (row.get("stock_code") or "").upper().startswith(("NASDAQ:", "NYSE:", "AMEX:", "OTC:"))
    ]
    sec_missing = [row for row in sec_applicable if not has_value(row.get("sec_cik"))]
    non_us = [row for row in listed if row not in sec_applicable]
    exchange_counts = Counter(row.get("exchange") or "Unknown" for row in listed)
    capital_sec = [row for row in capital if has_value(row.get("sec_cik"))]
    now = datetime.now().astimezone().isoformat(timespec="seconds")

    summary = {
        "checked_at": now,
        "listed_company_batch_rows": listed_total,
        "listed_company_batch_with_sec_cik": len(listed_sec),
        "sec_applicable_rows": len(sec_applicable),
        "sec_applicable_with_cik": len(sec_applicable) - len(sec_missing),
        "sec_applicable_missing_cik": len(sec_missing),
        "non_sec_exchange_rows": len(non_us),
        "company_capital_structure_rows": len(capital),
        "company_capital_structure_with_sec_cik": len(capital_sec),
        "exchange_counts": dict(exchange_counts),
        "sec_missing": [
            {
                "company": row.get("company"),
                "stock_code": row.get("stock_code"),
                "exchange": row.get("exchange"),
                "ticker_symbol": row.get("ticker_symbol"),
                "listing_country": row.get("listing_country"),
            }
            for row in sec_missing
        ],
    }

    md_path = AUDITS_DIR / f"sec_cik_coverage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    latest_md = AUDITS_DIR / "sec_cik_coverage_latest.md"
    json_path = AUDITS_DIR / "sec_cik_coverage_latest.json"
    lines = [
        "# SEC CIK 覆盖审计",
        "",
        f"- 检查时间：{now}",
        f"- listed_company_batch：{listed_total} 行，其中 {len(listed_sec)} 行有 sec_cik",
        f"- SEC 适用范围（美股/ADR/OTC）：{len(sec_applicable)} 行，已覆盖 {len(sec_applicable) - len(sec_missing)} 行，缺失 {len(sec_missing)} 行",
        f"- 非 SEC 交易所/本地交易所：{len(non_us)} 行，不应强行填 SEC CIK",
        f"- company_capital_structure：{len(capital)} 行，其中 {len(capital_sec)} 行有 sec_cik",
        "",
        "## 交易所分布",
        "",
        "| Exchange | Rows |",
        "|---|---:|",
    ]
    for exchange, count in exchange_counts.most_common():
        lines.append(f"| {exchange} | {count} |")
    lines.extend(["", "## SEC 适用但仍缺 CIK", ""])
    if sec_missing:
        lines.extend(["| Company | Stock code | Exchange | Ticker | Country |", "|---|---|---|---|---|"])
        for row in sec_missing:
            lines.append(
                f"| {row.get('company') or ''} | {row.get('stock_code') or ''} | {row.get('exchange') or ''} | "
                f"{row.get('ticker_symbol') or ''} | {row.get('listing_country') or ''} |"
            )
    else:
        lines.append("当前没有 SEC 适用但缺失 CIK 的上市主体。剩余空值主要是 KRX、HKEX、SIX、欧洲、A 股等本地交易所。")
    lines.extend(
        [
            "",
            "## 结论",
            "",
            f"原始缺口口径会把非美国交易所也算作 SEC 缺失。按 SEC 实际适用范围看，当前 SEC CIK 覆盖为 {len(sec_applicable) - len(sec_missing)}/{len(sec_applicable)}；下一步应为非美国上市主体补本地交易所/年报链接，而不是继续追 SEC CIK。",
            "",
        ]
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    latest_md.write_text("\n".join(lines), encoding="utf-8")
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary | {"markdown": str(md_path), "latest_markdown": str(latest_md)}


def main() -> None:
    print(json.dumps(audit(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
