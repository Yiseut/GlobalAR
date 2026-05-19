#!/usr/bin/env python3
"""Build the MDR/CE evidence search plan for priority companies.

Rows generated here are review targets, not verified CE authorization facts.
They make the manual path explicit: EUDAMED, notified-body certificate, and
manufacturer IFU/declaration evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any

from build_data import DB_PATH, MDR_CE_SEARCH_PLAN_PATH, stable_id


CE_SOURCES = {
    "eu_eudamed": {
        "source_name": "EUDAMED public site",
        "source_url": "https://ec.europa.eu/tools/eudamed/",
        "evidence_target": "EUDAMED device / actor / certificate lookup",
        "expected_evidence": "Basic UDI-DI, SRN, legal manufacturer, certificate reference, risk class and status if public.",
        "automation_status": "manual_search_ready",
    },
    "ce_notified_body_certificate": {
        "source_name": "Notified Body MDR/MDD certificate evidence",
        "source_url": "https://ec.europa.eu/tools/eudamed/",
        "evidence_target": "Notified-body certificate or certificate record",
        "expected_evidence": "Certificate number, scope, device class, notified body, validity date, manufacturer and product family.",
        "automation_status": "manual_search_ready",
    },
    "company_ce_documents": {
        "source_name": "Manufacturer IFU / Declaration of Conformity / EU product page",
        "source_url": "",
        "evidence_target": "Manufacturer IFU / DoC / EU product documentation",
        "expected_evidence": "Registered/marketed name, intended purpose, CE/MDR claim, legal manufacturer and authorized representative.",
        "automation_status": "manual_search_ready",
    },
}

CE_RELEVANT_CATEGORIES = {"EBD", "Injectables", "Implants", "Consumables", "Diagnostics", "Regenerative"}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def connect_when_ready(required_tables: set[str], attempts: int = 12, sleep_seconds: float = 5.0) -> sqlite3.Connection:
    missing: set[str] = set(required_tables)
    for _ in range(attempts):
        conn = connect()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name IN ({})".format(
                ",".join("?" for _ in required_tables)
            ),
            tuple(required_tables),
        ).fetchall()
        existing = {row["name"] for row in rows}
        missing = required_tables - existing
        if not missing:
            return conn
        conn.close()
        time.sleep(sleep_seconds)
    raise sqlite3.OperationalError(f"required database tables not ready: {', '.join(sorted(missing))}")


def source_registry(conn: sqlite3.Connection) -> dict[str, dict[str, Any]]:
    try:
        rows = conn.execute(
            """
            SELECT source_key, source_name, source_url, automation_status
            FROM official_source_registry
            WHERE source_key IN ('eu_eudamed', 'ce_notified_body_certificate', 'company_ce_documents')
            """
        ).fetchall()
    except sqlite3.OperationalError:
        return CE_SOURCES
    registry = {row["source_key"]: dict(row) for row in rows}
    merged = dict(CE_SOURCES)
    for key, value in registry.items():
        merged[key] = {**merged.get(key, {}), **value}
    return merged


def build_query(company: str, brand: str, product_family: str, source_key: str) -> str:
    core = " ".join(x for x in [company, brand, product_family] if norm(x))
    suffix = {
        "eu_eudamed": "EUDAMED Basic UDI-DI SRN certificate device",
        "ce_notified_body_certificate": "CE MDR certificate notified body declaration conformity scope",
        "company_ce_documents": "IFU instructions for use intended purpose declaration of conformity official PDF",
    }[source_key]
    return f"{core} {suffix}".strip()


def priority_families(conn: sqlite3.Connection, limit_companies: int, families_per_company: int) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT cm.priority_rank, pf.*
        FROM product_family_master pf
        JOIN company_master cm ON cm.company_id = pf.company_id
        WHERE cm.priority_rank IS NOT NULL
          AND cm.priority_rank <= ?
          AND pf.category_l1 IN ('EBD', 'Injectables', 'Implants', 'Consumables', 'Diagnostics', 'Regenerative')
        ORDER BY cm.priority_rank, pf.primary_record_count DESC, pf.product_family
        """,
        (limit_companies,),
    ).fetchall()
    selected: list[sqlite3.Row] = []
    counts: dict[str, int] = {}
    for row in rows:
        count = counts.get(row["company_id"], 0)
        if count >= families_per_company:
            continue
        selected.append(row)
        counts[row["company_id"]] = count + 1
    return selected


def build_plan(limit_companies: int, families_per_company: int) -> dict[str, Any]:
    conn = connect_when_ready({"product_family_master", "company_master"})
    sources = source_registry(conn)
    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for family in priority_families(conn, limit_companies, families_per_company):
        for source_key, source in sources.items():
            plan_id = stable_id("ceplan", family["company_id"], family["product_family_id"], source_key)
            rows.append(
                {
                    "plan_id": plan_id,
                    "priority_rank": family["priority_rank"],
                    "company_id": family["company_id"],
                    "company": family["company"],
                    "product_family_id": family["product_family_id"],
                    "brand": family["brand"],
                    "product_family": family["product_family"],
                    "category_l1": family["category_l1"],
                    "category_l2": family["category_l2"],
                    "tech_type": family["tech_type"],
                    "evidence_target": source["evidence_target"],
                    "source_key": source_key,
                    "source_name": source["source_name"],
                    "source_url": source.get("source_url", ""),
                    "query": build_query(family["company"], family["brand"], family["product_family"], source_key),
                    "expected_evidence": source["expected_evidence"],
                    "review_status": "needs_review",
                    "automation_status": source.get("automation_status", "manual_search_ready"),
                    "created_at": created_at,
                    "notes": "Search target only; merge only after reviewer confirms official certificate/IFU/EUDAMED evidence.",
                }
            )
    conn.close()
    MDR_CE_SEARCH_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "plan_id",
        "priority_rank",
        "company_id",
        "company",
        "product_family_id",
        "brand",
        "product_family",
        "category_l1",
        "category_l2",
        "tech_type",
        "evidence_target",
        "source_key",
        "source_name",
        "source_url",
        "query",
        "expected_evidence",
        "review_status",
        "automation_status",
        "created_at",
        "notes",
    ]
    with MDR_CE_SEARCH_PLAN_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return {
        "companies_limit": limit_companies,
        "families_per_company": families_per_company,
        "rows": len(rows),
        "sources": sorted(sources),
        "path": str(MDR_CE_SEARCH_PLAN_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", type=int, default=37)
    parser.add_argument("--families-per-company", type=int, default=4)
    args = parser.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/build_data.py first.")
    print(json.dumps(build_plan(args.companies, args.families_per_company), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
