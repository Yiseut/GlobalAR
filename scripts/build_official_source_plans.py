#!/usr/bin/env python3
"""Build reusable official-source search plans.

The output files are queue layers. They describe where to search and what kind
of evidence is expected; they are not verified facts by themselves.
"""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from build_data import (
    COMPANY_OFFICIAL_SOURCE_PLAN_PATH,
    DB_PATH,
    POLICY_REGULATORY_SOURCE_PLAN_PATH,
    stable_id,
)


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def company_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
          company_id, canonical_name, aliases, hq_country, ownership,
          parent_company, ultimate_parent, stock_code, exchange,
          ticker_symbol, listing_country, product_count, brand_count,
          primary_track, priority_rank
        FROM company_master
        ORDER BY
          CASE WHEN stock_code IS NOT NULL AND stock_code != '' THEN 0 ELSE 1 END,
          COALESCE(product_count, 0) DESC,
          COALESCE(priority_rank, 9999),
          canonical_name
        """
    ).fetchall()


def listed_lookup(conn: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT company_id, listed_entity_name, stock_code, exchange, ticker_symbol,
               listing_country, listing_verification_status, official_source_url
        FROM listed_company_batch
        WHERE company_id IS NOT NULL AND company_id != ''
        """
    ).fetchall()
    return {row["company_id"]: row for row in rows}


def quoted(value: str) -> str:
    value = norm(value)
    return f'"{value}"' if value and " " in value else value


def alias_hint(row: sqlite3.Row) -> str:
    raw = norm(row["aliases"])
    aliases: list[str]
    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
            aliases = [norm(item) for item in parsed if norm(item)] if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            aliases = []
    else:
        aliases = [part.strip() for part in raw.replace(";", ",").split(",") if part.strip()]
    aliases = [alias for alias in aliases if alias.lower() != norm(row["canonical_name"]).lower()]
    return aliases[0] if aliases else ""


def product_query(row: sqlite3.Row) -> str:
    company = quoted(row["canonical_name"])
    alias = alias_hint(row)
    track = norm(row["primary_track"])
    terms = [company, alias, "official product portfolio", "aesthetic medical device"]
    if track:
        terms.append(track)
    return " ".join(term for term in terms if term)


def ifu_query(row: sqlite3.Row) -> str:
    company = quoted(row["canonical_name"])
    alias = alias_hint(row)
    return " ".join(
        term
        for term in [company, alias, "IFU catalog brochure PDF", "aesthetic device official"]
        if term
    )


def capital_query(row: sqlite3.Row, listed: sqlite3.Row | None) -> str:
    company = norm(listed["listed_entity_name"]) if listed and norm(listed["listed_entity_name"]) else norm(row["canonical_name"])
    stock_code = norm(listed["stock_code"]) if listed and norm(listed["stock_code"]) else norm(row["stock_code"])
    exchange = norm(listed["exchange"]) if listed and norm(listed["exchange"]) else norm(row["exchange"])
    return " ".join(term for term in [quoted(company), stock_code, exchange, "investor relations annual report official filing"] if term)


PRODUCT_QUERY_TYPES = {
    "product_official_page": {
        "expected_source": "Brand / product official page",
        "target_fact_group": "commercial_product_identity",
        "notes": "Use product-specific official page to confirm brand owner, product family and commercial claims.",
    },
    "product_ifu_labeling": {
        "expected_source": "Product IFU / instructions for use / official labeling PDF",
        "target_fact_group": "commercial_product_identity",
        "notes": "Use IFU/labeling to confirm intended use, legal manufacturer, registered name and official wording.",
    },
    "product_certificate_registration": {
        "expected_source": "Official certificate / declaration / registration page",
        "target_fact_group": "registration_or_certificate_lead",
        "notes": "Use product-level certificate, declaration or official registration page as a lead for regulatory evidence.",
    },
}


def product_family_rows(conn: sqlite3.Connection, company_ids: set[str], families_per_company: int = 8) -> list[sqlite3.Row]:
    if not company_ids:
        return []
    placeholders = ",".join("?" for _ in company_ids)
    rows = conn.execute(
        f"""
        SELECT cm.priority_rank, cm.stock_code, pf.*
        FROM product_family_master pf
        JOIN company_master cm ON cm.company_id = pf.company_id
        WHERE pf.company_id IN ({placeholders})
        ORDER BY cm.priority_rank, pf.primary_record_count DESC, pf.product_family
        """,
        tuple(sorted(company_ids)),
    ).fetchall()
    selected: list[sqlite3.Row] = []
    counts: dict[str, int] = {}
    for row in rows:
        company_id = row["company_id"]
        count = counts.get(company_id, 0)
        if families_per_company and count >= families_per_company:
            continue
        selected.append(row)
        counts[company_id] = count + 1
    return selected


def product_family_query(row: sqlite3.Row, query_type: str) -> str:
    company = quoted(row["company"])
    brand = quoted(row["brand"])
    family = quoted(row["product_family"])
    category = norm(row["category_l1"])
    tech = norm(row["tech_type"])
    if query_type == "product_official_page":
        suffix = "official product page aesthetic medical device"
    elif query_type == "product_ifu_labeling":
        suffix = "IFU instructions for use intended purpose official PDF"
    else:
        suffix = "certificate declaration of conformity registration official"
    return " ".join(term for term in [company, brand, family, category, tech, suffix] if term)


def product_blank_fields() -> dict[str, str]:
    return {
        "product_family_id": "",
        "brand": "",
        "product_family": "",
        "category_l1": "",
        "category_l2": "",
        "tech_type": "",
    }


def product_fields(row: sqlite3.Row) -> dict[str, str]:
    return {
        "product_family_id": row["product_family_id"],
        "brand": row["brand"],
        "product_family": row["product_family"],
        "category_l1": row["category_l1"],
        "category_l2": row["category_l2"],
        "tech_type": row["tech_type"],
    }


def family_priority(row: sqlite3.Row, base_priority: int) -> int:
    text = " ".join(
        norm(row[key]).lower()
        for key in ["brand", "product_family", "category_l2", "tech_type"]
    )
    if any(term in text for term in ["calcium hydroxylapatite", "caha", "radiesse", "harmonyca", "facetem", "neauvia"]):
        return 0
    return base_priority


def build_company_plan(limit_companies: int | None = None, product_families_per_company: int = 0) -> dict[str, Any]:
    conn = connect()
    listed = listed_lookup(conn)
    companies = company_rows(conn)
    if limit_companies:
        companies = companies[:limit_companies]
    created_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(companies, start=1):
        base_priority = 1 if norm(row["stock_code"]) else 2
        plan_specs = [
            {
                "query_type": "official_product_portfolio",
                "query": product_query(row),
                "expected_source": "Company official website / product portfolio page",
                "target_fact_group": "commercial_product_identity",
                "priority": base_priority,
                "notes": "Use company official page/catalog to confirm brand, product family and commercial positioning.",
            },
            {
                "query_type": "official_ifu_catalog",
                "query": ifu_query(row),
                "expected_source": "Company IFU / official catalog / product PDF",
                "target_fact_group": "commercial_product_identity",
                "priority": base_priority,
                "notes": "Use IFU/catalog/PDF to confirm model/SKU, intended use, legal manufacturer and differentiator claims.",
            },
        ]
        if norm(row["stock_code"]) or row["company_id"] in listed:
            plan_specs.append(
                {
                    "query_type": "investor_relations_or_annual_report",
                    "query": capital_query(row, listed.get(row["company_id"])),
                    "expected_source": "Investor relations / annual report / exchange or securities filing",
                    "target_fact_group": "company_capital_and_ownership",
                    "priority": 1,
                    "notes": "Use official filings to confirm listed entity, parent/subsidiary relation, ticker and acquisition timeline.",
                }
            )
        for spec in plan_specs:
            rows.append(
                {
                    "plan_id": stable_id("cosplan", row["company_id"], spec["query_type"]),
                    "company_id": row["company_id"],
                    "priority_rank": rank,
                    "company": row["canonical_name"],
                    **product_blank_fields(),
                    "query_type": spec["query_type"],
                    "query": spec["query"],
                    "expected_source": spec["expected_source"],
                    "target_fact_group": spec["target_fact_group"],
                    "priority": spec["priority"],
                    "status": "ready",
                    "created_at": created_at,
                    "notes": spec["notes"],
                }
            )
    company_ids = {row["company_id"] for row in companies}
    for family in product_family_rows(conn, company_ids, product_families_per_company):
        base_priority = 1 if norm(family["stock_code"]) else 2
        priority = family_priority(family, base_priority)
        for query_type, spec in PRODUCT_QUERY_TYPES.items():
            rows.append(
                {
                    "plan_id": stable_id("cosplan", family["company_id"], family["product_family_id"], query_type),
                    "company_id": family["company_id"],
                    "priority_rank": family["priority_rank"],
                    "company": family["company"],
                    **product_fields(family),
                    "query_type": query_type,
                    "query": product_family_query(family, query_type),
                    "expected_source": spec["expected_source"],
                    "target_fact_group": spec["target_fact_group"],
                    "priority": priority,
                    "status": "ready",
                    "created_at": created_at,
                    "notes": spec["notes"],
                }
            )
    COMPANY_OFFICIAL_SOURCE_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "plan_id",
        "company_id",
        "priority_rank",
        "company",
        "product_family_id",
        "brand",
        "product_family",
        "category_l1",
        "category_l2",
        "tech_type",
        "query_type",
        "query",
        "expected_source",
        "target_fact_group",
        "priority",
        "status",
        "created_at",
        "notes",
    ]
    with COMPANY_OFFICIAL_SOURCE_PLAN_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    conn.close()
    return {
        "rows": len(rows),
        "companies": len(companies),
        "product_family_rows": sum(1 for row in rows if row.get("product_family_id")),
        "path": str(COMPANY_OFFICIAL_SOURCE_PLAN_PATH),
    }


def fact_group_for_source(row: sqlite3.Row) -> str:
    channel = norm(row["channel_code"]).lower()
    if channel == "company_official":
        return "commercial_product_identity"
    if channel == "mdsap":
        return "quality_system_audit_evidence"
    return "registration_status_and_approved_indication"


def query_template_for_source(row: sqlite3.Row) -> str:
    source_key = norm(row["source_key"])
    channel = norm(row["channel_code"]).lower()
    regulator = norm(row["regulator"])
    if source_key == "fda_openfda_510k":
        return "openFDA device 510k API search: applicant/device_name/product_code"
    if source_key == "fda_510k_database":
        return "{company} {brand} {product_family} FDA 510(k) official"
    if source_key == "fda_registration_listing":
        return "{company} FDA Registration Listing owner operator device listing"
    if source_key == "fda_accessgudid":
        return "{company} {brand} {product_family} AccessGUDID UDI"
    if channel == "ce":
        return "{company} {brand} {product_family} CE MDR EUDAMED Basic UDI-DI certificate"
    if channel == "company_official":
        return "{company} {brand} {product_family} official IFU catalog product PDF"
    if channel == "mdsap":
        return "{company} MDSAP certificate quality system audit official"
    return f"{{company}} {{brand}} {{product_family}} {regulator} medical device registration official"


def build_policy_plan() -> dict[str, Any]:
    conn = connect()
    rows = conn.execute(
        """
        SELECT source_key, channel_code, source_kind, scope_status, jurisdiction,
               regulator, source_name, source_url, primary_use, automation_status,
               priority, note
        FROM official_source_registry
        WHERE scope_status != 'external_project'
        ORDER BY priority, source_key
        """
    ).fetchall()
    output: list[dict[str, Any]] = []
    for row in rows:
        output.append(
            {
                "plan_id": stable_id("polplan", row["source_key"]),
                "source_key": row["source_key"],
                "channel_code": row["channel_code"],
                "jurisdiction": row["jurisdiction"],
                "regulator": row["regulator"],
                "source_name": row["source_name"],
                "source_url": row["source_url"],
                "fact_group": fact_group_for_source(row),
                "priority": row["priority"],
                "status": row["scope_status"],
                "query_template": query_template_for_source(row),
                "notes": row["primary_use"],
            }
        )
    POLICY_REGULATORY_SOURCE_PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "plan_id",
        "source_key",
        "channel_code",
        "jurisdiction",
        "regulator",
        "source_name",
        "source_url",
        "fact_group",
        "priority",
        "status",
        "query_template",
        "notes",
    ]
    with POLICY_REGULATORY_SOURCE_PLAN_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output)
    conn.close()
    return {"rows": len(output), "path": str(POLICY_REGULATORY_SOURCE_PLAN_PATH)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-companies", type=int, default=0, help="0 means all companies.")
    parser.add_argument("--product-families-per-company", type=int, default=0, help="0 means all product families.")
    args = parser.parse_args()
    limit = args.limit_companies or None
    result = {
        "company_official_source_plan": build_company_plan(limit, args.product_families_per_company),
        "policy_regulatory_source_plan": build_policy_plan(),
    }
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
