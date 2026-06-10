#!/usr/bin/env python3
"""Promote conservative product-fact evidence for gap rows.

This pass does not turn marketing pages into regulatory approvals. It only
records product existence, official product/document pages, and clean official
specification candidates so Product_Master can stop treating those rows as
unverified seed-only facts.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_data import (
    COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH,
    COMPANY_OFFICIAL_WEBSITE_PATH,
    DATA_DIR,
    MANUAL_EVIDENCE_PROMOTION_LOG_PATH,
    OFFICIAL_WEBSITE_MASTER_PATH,
    PRODUCT_MASTER_PATH,
    PRODUCT_SKU_MASTER_PATH,
    PRODUCT_SPECIFICATION_EVIDENCE_PATH,
    clean_evidence_text,
    host_matches_domain,
    load_company_official_source_evidence,
    load_generated_csv,
    norm,
    normalized_host,
    promotion_domain_blocked,
    stable_id,
)


GAP_QUEUE_PATH = DATA_DIR / "audits" / "product_gap_queue_latest.csv"
MANUAL_PRODUCT_FACT_EVIDENCE_PATH = DATA_DIR / "manual_product_fact_evidence.csv"
SUMMARY_PATH = DATA_DIR / "audits" / "product_fact_promotion_summary_latest.md"

FACT_FIELDS = [
    "fact_id",
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "product_family_id",
    "standard_product_name",
    "priority",
    "fact_group",
    "field_name",
    "field_value",
    "source_url",
    "evidence_title",
    "evidence_excerpt",
    "source_type",
    "confidence",
    "captured_at",
    "promoted_at",
    "review_status",
    "note",
]

PROMOTION_LOG_FIELDS = [
    "promotion_id",
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "product_family_id",
    "source_key",
    "source_type",
    "field_name",
    "promoted_value",
    "source_url",
    "evidence_title",
    "confidence",
    "promoted_at",
    "note",
]

OFFICIAL_PAGE_CONFIDENCE = {
    "official_domain_candidate",
    "product_official_domain_candidate",
    "company_official_search_candidate",
    "brand_official_search_candidate",
}

OFFICIAL_SEARCH_CONFIDENCE = {
    "product_official_search_candidate",
}

OFFICIAL_PAGE_QUERY_TYPES = {
    "product_official_page",
    "official_product_portfolio",
}

OFFICIAL_DOCUMENT_QUERY_TYPES = {
    "product_ifu_labeling",
    "product_certificate_registration",
    "official_ifu_catalog",
}

SPEC_CATEGORIES = {
    "material_or_ingredient",
    "packaging",
    "volume_packaging",
    "device_energy",
    "dose_strength",
    "commercial_certification",
}

GENERIC_TOKENS = {
    "aesthetic",
    "aesthetics",
    "beauty",
    "biomedical",
    "biotech",
    "care",
    "company",
    "corp",
    "corporation",
    "derma",
    "dermal",
    "filler",
    "global",
    "group",
    "health",
    "injectable",
    "international",
    "lab",
    "laboratoire",
    "laboratories",
    "laboratory",
    "llc",
    "ltd",
    "medical",
    "pharma",
    "pharmaceutical",
    "pharmaceuticals",
    "products",
    "science",
    "skin",
    "solution",
    "solutions",
    "technology",
    "therapeutic",
}

NOISY_SPEC_PATTERNS = [
    r"box-sizing",
    r"window\.",
    r"viewerModel",
    r"schema\.org",
    r"function\s*\(",
    r"javascript",
    r"\b(obj|endobj|endstream|xref)\b",
    r"/Filter\b",
    r"/FlateDecode",
    r"font-family",
    r"css",
    r"^[-_{}();:,.\\/\s]+$",
]

BLOCKED_PRODUCT_FACT_DOMAINS = {
    "aestheticsrxpharma.co.uk",
    "aiqixie.com",
    "beyondmedicalaesthetics.uk",
    "clinicaltrials.gov",
    "cosmodirectsupply.com",
    "fda.innolitics.com",
    "fda.report",
    "mitoconbiomed.in",
    "prnewswire.com",
    "sigma-stat.com",
    "tradekorea.com",
}


def load_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def domain_from_url(url: Any) -> str:
    return normalized_host(url)


def split_urls(value: Any) -> list[str]:
    text = norm(value)
    if not text:
        return []
    parts = re.split(r"[\n,;|]+", text)
    return [part.strip() for part in parts if part.strip()]


def tokenise(value: Any) -> set[str]:
    text = norm(value).lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", text)
    tokens = {part for part in text.split() if part and part not in GENERIC_TOKENS}
    return {part for part in tokens if len(part) >= 3 or re.search(r"[\u4e00-\u9fff]", part)}


def token_score(host: str, row: dict[str, Any]) -> int:
    host_key = re.sub(r"[^a-z0-9]+", "", host.lower())
    if not host_key:
        return 0
    token_groups = [
        tokenise(row.get("company")),
        tokenise(row.get("brand")),
        tokenise(row.get("product_family") or row.get("standard_product_name")),
    ]
    score = 0
    for i, tokens in enumerate(token_groups):
        for token in tokens:
            token_key = re.sub(r"[^a-z0-9]+", "", token)
            if len(token_key) < 3:
                continue
            if token_key in host_key:
                score += 2 if i < 2 else 1
    joined_company = "".join(sorted(token_groups[0]))
    if joined_company and joined_company in host_key:
        score += 2
    return score


def build_company_domains(company_websites: list[dict[str, Any]]) -> dict[str, set[str]]:
    domains: dict[str, set[str]] = defaultdict(set)
    for row in company_websites:
        company_id = norm(row.get("company_id"))
        if not company_id:
            continue
        for field in (
            "listed_parent_domain",
            "operating_company_domain",
            "primary_official_domain",
        ):
            host = norm(row.get(field)).lower()
            if host:
                domains[company_id].add(re.sub(r"^www\.", "", host))
        for field in ("listed_parent_url", "operating_company_url", "primary_official_url"):
            host = domain_from_url(row.get(field))
            if host:
                domains[company_id].add(host)
    return domains


def host_in_company_domains(host: str, company_id: str, company_domains: dict[str, set[str]]) -> bool:
    return any(host_matches_domain(host, domain) for domain in company_domains.get(company_id, set()))


def is_accepted_official_source(row: dict[str, Any], company_domains: dict[str, set[str]]) -> bool:
    url = row.get("official_website_url") or row.get("url") or row.get("source_url") or row.get("source_page_url")
    host = domain_from_url(url)
    if not host or promotion_domain_blocked(host):
        return False
    if any(host_matches_domain(host, domain) for domain in BLOCKED_PRODUCT_FACT_DOMAINS):
        return False
    company_id = norm(row.get("company_id"))
    confidence = norm(row.get("confidence"))
    candidate = norm(row.get("official_candidate")).lower()
    if confidence == "secondary_source_crosscheck":
        return False
    if candidate in {"no", "unknown"}:
        return False
    score = token_score(host, row)
    if company_id and host_in_company_domains(host, company_id, company_domains):
        return True
    if confidence in OFFICIAL_PAGE_CONFIDENCE and (candidate == "likely" or score >= 2):
        return True
    if confidence in OFFICIAL_SEARCH_CONFIDENCE and candidate == "likely" and score >= 2:
        return True
    if candidate == "likely" and score >= 2:
        return True
    return False


def product_family_to_product_ids(product_rows: list[dict[str, Any]], sku_rows: list[dict[str, Any]]) -> dict[str, set[str]]:
    by_seed = {norm(row.get("seed_record_id")): norm(row.get("product_id")) for row in product_rows}
    mapping: dict[str, set[str]] = defaultdict(set)
    for sku in sku_rows:
        family_id = norm(sku.get("product_family_id"))
        seed_id = norm(sku.get("seed_record_id"))
        product_id = by_seed.get(seed_id)
        if family_id and product_id:
            mapping[family_id].add(product_id)
    return mapping


def product_ids_for_source(
    row: dict[str, Any],
    target_ids: set[str],
    family_map: dict[str, set[str]],
    product_by_seed: dict[str, dict[str, Any]],
    product_by_id: dict[str, dict[str, Any]],
) -> list[str]:
    product_id = norm(row.get("product_id"))
    if product_id and product_id in target_ids:
        return [product_id]
    family_id = norm(row.get("product_family_id"))
    ids = sorted(pid for pid in family_map.get(family_id, set()) if pid in target_ids)
    if ids:
        return ids
    seed_id = norm(row.get("seed_record_id"))
    if seed_id:
        product_id = norm(product_by_seed.get(seed_id, {}).get("product_id"))
        if product_id in target_ids:
            return [product_id]
    company = norm(row.get("company")).lower()
    brand = norm(row.get("brand")).lower()
    product_name = norm(row.get("product_family") or row.get("standard_product_name")).lower()
    if not company or not (brand or product_name):
        return []
    matches = []
    for pid in target_ids:
        product = product_by_id.get(pid) or {}
        if norm(product.get("company")).lower() != company:
            continue
        if brand and brand == norm(product.get("brand")).lower():
            matches.append(pid)
            continue
        if product_name and product_name == norm(product.get("standard_product_name")).lower():
            matches.append(pid)
    return sorted(set(matches))


def noisy_spec_text(row: dict[str, Any]) -> bool:
    text = " | ".join(
        norm(row.get(field))
        for field in ("spec_name", "spec_value", "spec_unit", "evidence_excerpt", "source_title")
        if norm(row.get(field))
    )
    if len(text) < 3 or len(text) > 1400:
        return True
    if text.count("{") + text.count("}") > 4:
        return True
    if len(re.findall(r"[A-Za-z0-9]{60,}", text)) > 0:
        return True
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in NOISY_SPEC_PATTERNS)


def spec_value(row: dict[str, Any]) -> str:
    pieces = [norm(row.get("spec_name")), norm(row.get("spec_value")), norm(row.get("spec_unit"))]
    return " ".join(part for part in pieces if part)


def make_fact_row(
    source: dict[str, Any],
    product: dict[str, Any],
    priority: str,
    fact_group: str,
    field_name: str,
    field_value: str,
    source_type: str,
    promoted_at: str,
    note: str,
) -> dict[str, Any]:
    source_url = norm(source.get("official_website_url") or source.get("url") or source.get("source_url") or source.get("source_page_url"))
    evidence_title = norm(source.get("source_title") or source.get("title") or source.get("evidence_title") or source.get("standard_product_name"))
    excerpt = clean_evidence_text(source.get("evidence_excerpt") or source.get("raw_text") or source.get("relationship_notes"))[:1000]
    product_family_id = norm(source.get("product_family_id"))
    field_value = clean_evidence_text(field_value)[:1000]
    fact_id = stable_id("pfact", product.get("product_id"), fact_group, field_name, source_url, field_value)
    return {
        "fact_id": fact_id,
        "product_id": norm(product.get("product_id")),
        "seed_record_id": norm(product.get("seed_record_id")),
        "company_id": norm(product.get("company_id")),
        "company": norm(product.get("company")),
        "brand": norm(product.get("brand")),
        "product_family_id": product_family_id,
        "standard_product_name": norm(product.get("standard_product_name")),
        "priority": priority,
        "fact_group": fact_group,
        "field_name": field_name,
        "field_value": field_value,
        "source_url": source_url,
        "evidence_title": evidence_title,
        "evidence_excerpt": excerpt,
        "source_type": source_type,
        "confidence": norm(source.get("confidence")) or "official_product_fact_candidate",
        "captured_at": norm(source.get("captured_at")),
        "promoted_at": promoted_at,
        "review_status": "auto_cross_checked",
        "note": note,
    }


def promotion_log_from_fact(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "promotion_id": stable_id("manual_fact", row.get("product_id"), row.get("field_name"), row.get("source_url"), row.get("field_value")),
        "product_id": row.get("product_id"),
        "seed_record_id": row.get("seed_record_id"),
        "company_id": row.get("company_id"),
        "company": row.get("company"),
        "brand": row.get("brand"),
        "product_family_id": row.get("product_family_id"),
        "source_key": row.get("fact_group"),
        "source_type": row.get("source_type"),
        "field_name": row.get("field_name"),
        "promoted_value": row.get("field_value"),
        "source_url": row.get("source_url"),
        "evidence_title": row.get("evidence_title"),
        "confidence": row.get("confidence"),
        "promoted_at": row.get("promoted_at"),
        "note": row.get("note"),
    }


def merge_rows(existing: list[dict[str, Any]], new_rows: list[dict[str, Any]], key_field: str) -> list[dict[str, Any]]:
    merged = {norm(row.get(key_field)): row for row in existing if norm(row.get(key_field))}
    for row in new_rows:
        key = norm(row.get(key_field))
        if key:
            merged[key] = row
    return list(merged.values())


def write_summary(summary: dict[str, Any], by_priority: Counter, by_fact: Counter, skipped: Counter) -> None:
    lines = [
        "# Product Fact Promotion Summary",
        "",
        f"- Promoted at: {summary['promoted_at']}",
        f"- Target priorities: {', '.join(summary['priorities'])}",
        f"- Target products: {summary['target_products']}",
        f"- New/updated fact rows: {summary['fact_rows']}",
        f"- Products with promoted facts: {summary['products_with_facts']}",
        f"- Manual fact evidence total rows: {summary['manual_fact_total_rows']}",
        f"- Manual promotion log total rows: {summary['manual_log_total_rows']}",
        "",
        "## By Priority",
    ]
    lines.extend(f"- {key}: {value}" for key, value in sorted(by_priority.items()))
    lines.append("")
    lines.append("## By Fact Group")
    lines.extend(f"- {key}: {value}" for key, value in sorted(by_fact.items()))
    lines.append("")
    lines.append("## Skipped")
    lines.extend(f"- {key}: {value}" for key, value in sorted(skipped.items()))
    lines.append("")
    lines.append("Note: specification evidence remains a traceable candidate layer and is not treated as regulatory approval.")
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Promote official product facts for gap products.")
    parser.add_argument("--priorities", default="P0,P1,P2,P3", help="Comma-separated priorities from product_gap_queue_latest.csv.")
    parser.add_argument("--limit", type=int, default=0, help="Optional product limit after priority filtering.")
    parser.add_argument("--specs-per-product", type=int, default=3)
    args = parser.parse_args()

    priorities = [part.strip() for part in args.priorities.split(",") if part.strip()]
    priority_set = set(priorities)
    promoted_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    products = load_csv(PRODUCT_MASTER_PATH)
    product_by_id = {norm(row.get("product_id")): row for row in products if norm(row.get("product_id"))}
    product_by_seed = {norm(row.get("seed_record_id")): row for row in products if norm(row.get("seed_record_id"))}
    sku_rows = load_generated_csv(PRODUCT_SKU_MASTER_PATH)
    family_map = product_family_to_product_ids(products, sku_rows)
    gap_rows = [row for row in load_csv(GAP_QUEUE_PATH) if norm(row.get("priority")) in priority_set]
    gap_rows.sort(key=lambda row: (norm(row.get("priority")), -int(float(row.get("gap_score") or 0))))
    if args.limit > 0:
        gap_rows = gap_rows[: args.limit]
    target_ids = {norm(row.get("product_id")) for row in gap_rows if norm(row.get("product_id"))}
    priority_by_product = {norm(row.get("product_id")): norm(row.get("priority")) for row in gap_rows if norm(row.get("product_id"))}

    company_websites = load_generated_csv(COMPANY_OFFICIAL_WEBSITE_PATH)
    company_domains = build_company_domains(company_websites)
    website_rows = load_generated_csv(OFFICIAL_WEBSITE_MASTER_PATH)
    source_rows = load_company_official_source_evidence()
    spec_rows = load_generated_csv(PRODUCT_SPECIFICATION_EVIDENCE_PATH)

    accepted_urls_by_product: dict[str, set[str]] = defaultdict(set)
    facts: list[dict[str, Any]] = []
    skipped: Counter = Counter()

    for row in website_rows:
        if norm(row.get("entity_scope")) != "product_line":
            skipped["website_non_product_line"] += 1
            continue
        if not is_accepted_official_source(row, company_domains):
            skipped["website_not_official_enough"] += 1
            continue
        product_ids = product_ids_for_source(row, target_ids, family_map, product_by_seed, product_by_id)
        if not product_ids:
            skipped["website_no_target_product"] += 1
            continue
        for product_id in product_ids:
            product = product_by_id.get(product_id)
            if not product:
                continue
            value = norm(row.get("official_website_url"))
            if not value:
                continue
            fact = make_fact_row(
                row,
                product,
                priority_by_product.get(product_id, ""),
                "official_product_page",
                "official_product_page",
                value,
                "official_product_page",
                promoted_at,
                "Official product or portfolio page accepted by domain and entity matching; not regulatory approval.",
            )
            facts.append(fact)
            accepted_urls_by_product[product_id].add(value)

    for row in source_rows:
        query_type = norm(row.get("query_type"))
        if query_type not in OFFICIAL_PAGE_QUERY_TYPES | OFFICIAL_DOCUMENT_QUERY_TYPES:
            continue
        if not is_accepted_official_source(row, company_domains):
            skipped["source_not_official_enough"] += 1
            continue
        product_ids = product_ids_for_source(row, target_ids, family_map, product_by_seed, product_by_id)
        if not product_ids:
            skipped["source_no_target_product"] += 1
            continue
        source_type = "official_product_document" if query_type in OFFICIAL_DOCUMENT_QUERY_TYPES else "official_product_page"
        field_name = "official_document" if source_type == "official_product_document" else "official_product_page"
        value = norm(row.get("url"))
        if not value:
            continue
        for product_id in product_ids:
            product = product_by_id.get(product_id)
            if not product:
                continue
            facts.append(
                make_fact_row(
                    row,
                    product,
                    priority_by_product.get(product_id, ""),
                    source_type,
                    field_name,
                    value,
                    source_type,
                    promoted_at,
                    "Official product document/page accepted by domain and entity matching; evidence remains separate from regulatory approval.",
                )
            )
            accepted_urls_by_product[product_id].add(value)

    specs_by_product: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in spec_rows:
        category = norm(row.get("spec_category"))
        if category not in SPEC_CATEGORIES:
            skipped["spec_category_not_targeted"] += 1
            continue
        if norm(row.get("confidence")) == "official_search_excerpt_spec_candidate":
            skipped["spec_search_excerpt_only"] += 1
            continue
        if noisy_spec_text(row):
            skipped["spec_noisy"] += 1
            continue
        product_ids = product_ids_for_source(row, target_ids, family_map, product_by_seed, product_by_id)
        if not product_ids:
            skipped["spec_no_target_product"] += 1
            continue
        host = domain_from_url(row.get("source_page_url"))
        for product_id in product_ids:
            if host and (
                any(host_matches_domain(host, domain_from_url(url)) for url in accepted_urls_by_product.get(product_id, set()))
                or host_in_company_domains(host, norm(product_by_id.get(product_id, {}).get("company_id")), company_domains)
                or token_score(host, {**row, **product_by_id.get(product_id, {})}) >= 2
            ):
                specs_by_product[product_id].append(row)
            else:
                skipped["spec_source_not_accepted"] += 1

    for product_id, rows in specs_by_product.items():
        product = product_by_id.get(product_id)
        if not product:
            continue
        dedup: dict[str, dict[str, Any]] = {}
        for row in rows:
            value = spec_value(row)
            if not value:
                continue
            key = stable_id("specpick", product_id, norm(row.get("spec_category")), value)
            dedup[key] = row
        selected = sorted(
            dedup.values(),
            key=lambda row: (
                norm(row.get("spec_category")),
                norm(row.get("spec_name")),
                norm(row.get("source_page_url")),
            ),
        )[: max(0, args.specs_per_product)]
        for row in selected:
            facts.append(
                make_fact_row(
                    row,
                    product,
                    priority_by_product.get(product_id, ""),
                    "official_specification_candidate",
                    norm(row.get("spec_category")) or "official_specification",
                    spec_value(row),
                    "official_specification_candidate",
                    promoted_at,
                    "Clean official-site specification candidate retained for traceability; not written as a hard Product_Master spec field.",
                )
            )

    refresh_groups = {"official_product_page", "official_product_document", "official_specification_candidate"}
    existing_facts = []
    for row in load_csv(MANUAL_PRODUCT_FACT_EVIDENCE_PATH):
        is_refreshable_fact = norm(row.get("fact_id")).startswith("pfact_") and norm(row.get("fact_group")) in refresh_groups
        if is_refreshable_fact and norm(row.get("product_id")) in target_ids:
            continue
        existing_facts.append(row)
    merged_facts = merge_rows(existing_facts, facts, "fact_id")
    write_csv(MANUAL_PRODUCT_FACT_EVIDENCE_PATH, FACT_FIELDS, merged_facts)

    existing_logs = []
    for row in load_csv(MANUAL_EVIDENCE_PROMOTION_LOG_PATH):
        is_refreshable_log = norm(row.get("source_key")) in refresh_groups
        if is_refreshable_log and norm(row.get("product_id")) in target_ids:
            continue
        existing_logs.append(row)
    new_logs = [promotion_log_from_fact(row) for row in facts]
    merged_logs = merge_rows(existing_logs, new_logs, "promotion_id")
    write_csv(MANUAL_EVIDENCE_PROMOTION_LOG_PATH, PROMOTION_LOG_FIELDS, merged_logs)

    by_priority = Counter(row.get("priority") or "unknown" for row in facts)
    by_fact = Counter(row.get("fact_group") or "unknown" for row in facts)
    products_with_facts = {row.get("product_id") for row in facts if row.get("product_id")}
    summary = {
        "promoted_at": promoted_at,
        "priorities": priorities,
        "target_products": len(target_ids),
        "fact_rows": len(facts),
        "products_with_facts": len(products_with_facts),
        "manual_fact_total_rows": len(merged_facts),
        "manual_log_total_rows": len(merged_logs),
    }
    write_summary(summary, by_priority, by_fact, skipped)
    print(json.dumps({**summary, "by_priority": dict(by_priority), "by_fact": dict(by_fact), "skipped": dict(skipped)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
