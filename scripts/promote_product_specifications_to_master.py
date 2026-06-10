#!/usr/bin/env python3
"""Promote product specification evidence into the product fact layer.

The 50k+ Product_Spec_Evidence rows are noisy by design: they are extractor
candidates, not all master facts. This script gives every row an operational
status, promotes conservative high-confidence rows into
manual_product_fact_evidence.csv, and produces a medium-confidence review
sample for human checking.
"""

from __future__ import annotations

import csv
import json
import random
import re
import urllib.parse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_SPEC_PATH = DATA_DIR / "product_specification_evidence.csv"
PRODUCT_MASTER_PATH = DATA_DIR / "product_master.csv"
PRODUCT_FAMILY_MASTER_PATH = DATA_DIR / "product_family_master.csv"
PRODUCT_SKU_MASTER_PATH = DATA_DIR / "product_sku_master.csv"
COMPANY_OFFICIAL_WEBSITE_PATH = DATA_DIR / "company_official_website.csv"
MANUAL_PRODUCT_FACT_PATH = DATA_DIR / "manual_product_fact_evidence.csv"
PROMOTION_AUDIT_PATH = AUDIT_DIR / "product_spec_promotion_latest.csv"
OPERATIONAL_STATUS_PATH = AUDIT_DIR / "product_spec_operational_status_latest.csv"
MEDIUM_REVIEW_SAMPLE_PATH = AUDIT_DIR / "product_spec_medium_review_sample_latest.csv"
SUMMARY_PATH = AUDIT_DIR / "product_spec_promotion_summary_latest.md"

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

AUTO_SPEC_CATEGORIES = {
    "material_or_ingredient",
    "device_energy",
    "dose_strength",
    "volume_packaging",
    "commercial_certification",
}

MEDIUM_SPEC_CATEGORIES = AUTO_SPEC_CATEGORIES | {"packaging"}

HIGH_QUERY_TYPES = {
    "product_official_page",
    "product_ifu_labeling",
    "product_certificate_registration",
    "official_product_portfolio",
    "official_ifu_catalog",
}

STRICT_INFERRED_QUERY_TYPES = {
    "product_official_page",
    "product_ifu_labeling",
    "product_certificate_registration",
    "official_ifu_catalog",
}

GENERIC_MATERIAL_VALUES = {
    "collagen",
    "cryolipolysis",
    "gel",
    "ha",
    "hyaluronic acid",
    "lidocaine",
    "lido",
    "radiofrequency",
    "saline",
    "sodium chloride",
    "ultrasound",
    "water",
}

DISTINCTIVE_MATERIAL_TERMS = {
    "caha",
    "calcium hydroxyapatite",
    "carbon dioxide",
    "co2",
    "exosome",
    "hydroxyapatite",
    "pcl",
    "pdo",
    "pdlla",
    "pdrn",
    "plla",
    "pn",
    "abobotulinumtoxina",
    "botulinum toxin",
    "incobotulinumtoxina",
    "letibotulinumtoxina",
    "onabotulinumtoxina",
    "prabotulinumtoxina",
    "poly-d-lactic",
    "poly-l-lactic",
    "polycaprolactone",
    "polylactic",
    "polynucleotide",
}

GENERIC_TOKENS = {
    "aesthetic",
    "aesthetics",
    "beauty",
    "company",
    "corp",
    "dermal",
    "filler",
    "fillers",
    "global",
    "group",
    "injectable",
    "lab",
    "laboratories",
    "ltd",
    "medical",
    "pharma",
    "product",
    "products",
    "skin",
    "solution",
    "solutions",
    "technology",
}

FAMILY_MATCH_STOP_TOKENS = GENERIC_TOKENS | {
    "collection",
    "cosmetic",
    "derma",
    "device",
    "devices",
    "home",
    "laser",
    "official",
    "page",
    "therapy",
    "treatment",
    "treatments",
    "type",
}

BLOCKED_DOMAINS = {
    "aiqixie.com",
    "beyondmedicalaesthetics.uk",
    "clinicaltrials.gov",
    "cosmodirectsupply.com",
    "fda.innolitics.com",
    "fda.report",
    "medicalexpo.com",
    "mitoconbiomed.in",
    "prnewswire.com",
    "sigma-stat.com",
    "tradekorea.com",
}

NOISY_PATTERNS = [
    r"box-sizing",
    r"breadcrumblist",
    r"consent\s+b",
    r"font-family",
    r"function\s*\(",
    r"homepage\s*>",
    r"javascript",
    r"mailing list",
    r"schema\.org",
    r"window\.",
    r"\b(endobj|endstream|xref)\b",
    r"/FlateDecode",
    r"\{\s*\"@type\"",
]


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    import hashlib

    raw = "|".join(norm(part).lower() for part in parts if norm(part))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12] if raw else "0" * 12
    return f"{prefix}_{digest}"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def host(url: Any) -> str:
    parsed = urllib.parse.urlparse(norm(url))
    return parsed.netloc.lower().removeprefix("www.")


def host_matches(hostname: str, domain: str) -> bool:
    hostname = hostname.lower().removeprefix("www.")
    domain = domain.lower().removeprefix("www.")
    return hostname == domain or hostname.endswith("." + domain)


def tokenise(value: Any) -> set[str]:
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", norm(value).lower())
    return {part for part in text.split() if len(part) >= 3 and part not in GENERIC_TOKENS}


def family_match_tokens(value: Any) -> set[str]:
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", norm(value).lower())
    return {part for part in text.split() if len(part) >= 3 and part not in FAMILY_MATCH_STOP_TOKENS}


def token_score(hostname: str, row: dict[str, Any]) -> int:
    key = re.sub(r"[^a-z0-9]+", "", hostname.lower())
    if not key:
        return 0
    score = 0
    for weight, field in [(3, "company"), (3, "brand"), (2, "product_family"), (2, "standard_product_name")]:
        for token in tokenise(row.get(field)):
            token_key = re.sub(r"[^a-z0-9]+", "", token)
            if token_key and token_key in key:
                score += weight
    return score


def company_domains(rows: list[dict[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        company_id = norm(row.get("company_id"))
        if not company_id:
            continue
        for field in [
            "primary_official_domain",
            "operating_company_domain",
            "listed_parent_domain",
            "primary_official_url",
            "operating_company_url",
            "listed_parent_url",
        ]:
            value = norm(row.get(field))
            if not value:
                continue
            out[company_id].add(host(value) or value.lower().removeprefix("www."))
    return out


def source_alignment(row: dict[str, Any], domains: dict[str, set[str]]) -> str:
    hostname = host(row.get("source_page_url"))
    if not hostname:
        return "no_source_host"
    if any(host_matches(hostname, blocked) for blocked in BLOCKED_DOMAINS):
        return "blocked_domain"
    company_id = norm(row.get("company_id"))
    if any(host_matches(hostname, domain) for domain in domains.get(company_id, set())):
        return "company_official_domain"
    if token_score(hostname, row) >= 2:
        return "domain_token_match"
    return "source_not_cross_checked"


def clean_text(value: Any, limit: int = 1000) -> str:
    text = re.sub(r"\s+", " ", norm(value))
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text[:limit].strip()


def noisy_spec(row: dict[str, Any]) -> bool:
    value = norm(row.get("spec_value"))
    if not value:
        return True
    text = " | ".join(
        norm(row.get(field))
        for field in ["spec_name", "spec_value", "spec_unit", "source_title"]
        if norm(row.get(field))
    )
    if len(value) > 120 or text.count("{") + text.count("}") > 2:
        return True
    if any(re.search(pattern, text, re.IGNORECASE) for pattern in NOISY_PATTERNS):
        return True
    lower = value.lower().strip(" .,:;")
    if lower in {"box", "boxes", "model", "models", "needle", "syringe", "label", "download"}:
        return True
    if re.fullmatch(r"\d+[a-z]?", value, flags=re.IGNORECASE) and len(value) <= 2:
        return True
    if "http" in lower or "www." in lower:
        return True
    return False


def strict_inferred_value_ok(row: dict[str, Any]) -> bool:
    value = norm(row.get("spec_value")).strip()
    value_lower = value.lower().strip(" .,:;")
    category = norm(row.get("spec_category"))
    context = " ".join(
        norm(row.get(field)).lower()
        for field in [
            "company",
            "brand",
            "product_family",
            "standard_product_name",
            "spec_name",
            "source_title",
            "source_page_url",
            "evidence_excerpt",
        ]
        if norm(row.get(field))
    )

    if category == "commercial_certification":
        return bool(
            re.search(
                r"\b(ce|mdr|iso\s*13485|fda|510\s*\(?k\)?|nmpa|mfds|kfda|pma)\b",
                value_lower,
                re.IGNORECASE,
            )
        )
    if category == "volume_packaging":
        return bool(
            re.search(
                r"\b\d+(?:\.\d+)?\s*(?:ml|cc|vials?|syringes?|ampoules?|amps?|pcs|units?|ea)\b|\b\d+\s*[x×]\s*\d+",
                value_lower,
                re.IGNORECASE,
            )
        )
    if category == "dose_strength":
        return bool(
            re.search(
                r"\b\d+(?:\.\d+)?\s*(?:mg/ml|mg|µg|mcg|ml|iu|u|units?|%)\b",
                value_lower,
                re.IGNORECASE,
            )
        )
    if category == "device_energy":
        return bool(
            re.search(
                r"\b\d+(?:\.\d+)?\s*(?:nm|mhz|khz|ghz|hz|w|kw|j|mj|j/cm2|j/cm²|kpa|bar|mpa|mmhg|pa|°c|celsius)\b",
                value_lower,
                re.IGNORECASE,
            )
        )
    if category == "material_or_ingredient":
        normalized_value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value_lower).strip()
        if not normalized_value or normalized_value in GENERIC_MATERIAL_VALUES:
            return False
        for term in DISTINCTIVE_MATERIAL_TERMS:
            if term in value_lower:
                if term in {"co2", "carbon dioxide"}:
                    negative_context = "not a co2" in context or "not co2" in context or "non co2" in context
                    direct_context = "carboxy" in context or "co2" in norm(row.get("product_family")).lower()
                    return direct_context and not negative_context
                return True
        return False
    return False


def strict_product_context_ok(row: dict[str, Any]) -> bool:
    source_context = " ".join(
        norm(row.get(field)).lower()
        for field in ["source_title", "source_page_url", "evidence_excerpt"]
        if norm(row.get(field))
    )
    if not source_context:
        return False

    for field in ["brand", "standard_product_name", "product_family"]:
        phrase = norm(row.get(field)).lower()
        if len(phrase) >= 5 and phrase not in {"n/a", "unknown"} and phrase in source_context:
            return True

    target_tokens: set[str] = set()
    for field in ["brand", "standard_product_name", "product_family"]:
        target_tokens |= family_match_tokens(row.get(field))
    target_tokens = {
        token
        for token in target_tokens
        if len(token) >= 4 and token not in {"filler", "fillers", "skin", "type"}
    }
    if not target_tokens:
        return True
    source_tokens = family_match_tokens(source_context)
    return bool(target_tokens & source_tokens)


def strict_value_neighborhood_ok(row: dict[str, Any]) -> bool:
    category = norm(row.get("spec_category"))
    if category not in {"dose_strength", "volume_packaging", "material_or_ingredient", "device_energy"}:
        return True

    value = norm(row.get("spec_value")).lower().strip()
    excerpt = norm(row.get("evidence_excerpt")).lower()
    if len(value) < 2 or not excerpt:
        return True

    value_variants = {value, re.sub(r"\s+", "", value)}
    excerpt_compact = re.sub(r"\s+", "", excerpt)
    if not any(variant and variant in excerpt for variant in value_variants) and not any(
        variant and variant in excerpt_compact for variant in value_variants
    ):
        return True

    target_tokens: set[str] = set()
    for field in ["brand", "standard_product_name", "product_family"]:
        target_tokens |= family_match_tokens(row.get(field))
    target_tokens = {
        token
        for token in target_tokens
        if len(token) >= 4 and token not in {"filler", "fillers", "skin", "type"}
    }
    if not target_tokens:
        return True

    positions: list[tuple[int, int]] = []
    for variant in value_variants:
        if not variant:
            continue
        start = 0
        while True:
            pos = excerpt.find(variant, start)
            if pos < 0:
                break
            positions.append((pos, len(variant)))
            start = pos + max(1, len(variant))
    if not positions:
        return True
    pos, length = min(positions, key=lambda item: item[0])
    window = excerpt[max(0, pos - 120) : pos]
    token_positions = [(window.rfind(token), token) for token in target_tokens if window.rfind(token) >= 0]
    if not token_positions:
        return False
    last_pos, last_token = max(token_positions, key=lambda item: item[0])
    tail_after_target = window[last_pos + len(last_token) :]
    if category in {"dose_strength", "volume_packaging"} and ("®" in tail_after_target or "™" in tail_after_target):
        return False
    return True


def strict_inferred_family_auto_promotion(row: dict[str, Any], alignment: str) -> bool:
    """Only promote inferred-family rows when the remaining uncertainty is low."""
    return (
        alignment == "company_official_domain"
        and norm(row.get("confidence")) == "official_site_spec_candidate"
        and norm(row.get("source_query_type")) in STRICT_INFERRED_QUERY_TYPES
        and norm(row.get("spec_category")) in AUTO_SPEC_CATEGORIES
        and strict_inferred_value_ok(row)
        and strict_product_context_ok(row)
        and strict_value_neighborhood_ok(row)
    )


def spec_fact_value(row: dict[str, Any]) -> str:
    name = norm(row.get("spec_name")) or norm(row.get("spec_category")) or "spec"
    value = norm(row.get("spec_value"))
    unit = norm(row.get("spec_unit"))
    if unit and unit.lower() not in value.lower():
        value = f"{value} {unit}"
    return clean_text(f"{name}: {value}", 500)


def family_product_map(product_rows: list[dict[str, str]], sku_rows: list[dict[str, str]]) -> dict[str, set[str]]:
    product_ids = {norm(row.get("product_id")) for row in product_rows if norm(row.get("product_id"))}
    mapping: dict[str, set[str]] = defaultdict(set)
    for row in sku_rows:
        family_id = norm(row.get("product_family_id"))
        sku_id = norm(row.get("sku_id"))
        if family_id and sku_id in product_ids:
            mapping[family_id].add(sku_id)
    return mapping


def product_family_inference_index(family_rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for family in family_rows:
        if norm(family.get("inclusion_status")).lower() in {"deleted", "excluded"}:
            continue
        token_set: set[str] = set()
        for field in ["brand", "product_family", "sku_candidate_names"]:
            token_set |= family_match_tokens(family.get(field))
        if not token_set:
            continue
        item = dict(family)
        item["_match_tokens"] = token_set
        index[norm(family.get("company_id"))].append(item)
    return index


def infer_product_family(row: dict[str, Any], family_index: dict[str, list[dict[str, Any]]]) -> tuple[dict[str, Any], str] | None:
    if norm(row.get("product_family_id")):
        return None
    haystack = " | ".join(
        norm(row.get(field))
        for field in [
            "brand",
            "standard_product_name",
            "product_family",
            "source_title",
            "source_page_url",
            "evidence_excerpt",
        ]
        if norm(row.get(field))
    )
    haystack_lower = haystack.lower()
    haystack_tokens = family_match_tokens(haystack)
    matches: list[tuple[int, dict[str, Any], set[str], int]] = []
    for family in family_index.get(norm(row.get("company_id")), []):
        family_tokens = set(family.get("_match_tokens") or set())
        common = family_tokens & haystack_tokens
        phrase_score = 0
        for field in ["brand", "product_family"]:
            value = norm(family.get(field)).lower()
            if len(value) >= 5 and value in haystack_lower:
                phrase_score += 4
        distinctive = [token for token in common if len(token) >= 6 or re.search(r"\d", token)]
        if phrase_score >= 4 or (distinctive and len(common) >= 2) or len(distinctive) >= 2:
            score = phrase_score + len(common) + len(distinctive)
            matches.append((score, family, common, phrase_score))
    if len(matches) != 1:
        return None
    score, family, common, phrase_score = matches[0]
    reason = f"inferred_family_from_source_text score={score} phrase={phrase_score} tokens={','.join(sorted(common)[:6])}"
    return family, reason


def fact_row(row: dict[str, str], product: dict[str, str], promoted_at: str, confidence_tier: str) -> dict[str, str]:
    field_value = spec_fact_value(row)
    source_url = norm(row.get("source_page_url"))
    fact_id = stable_id(
        "pfact",
        product.get("product_id"),
        "product_spec_evidence",
        row.get("spec_id"),
        field_value,
    )
    note = "product_spec_evidence_promotion_20260527; high-confidence official-site spec promoted to Product_Master technical specs."
    if row.get("_inferred_family_auto_promoted"):
        note = (
            "product_spec_evidence_promotion_20260527; inferred product-family mapping passed strict official-domain "
            "and value-format gates before promotion."
        )
    return {
        "fact_id": fact_id,
        "product_id": norm(product.get("product_id")),
        "seed_record_id": norm(product.get("seed_record_id")),
        "company_id": norm(product.get("company_id")),
        "company": norm(product.get("company")),
        "brand": norm(product.get("brand")),
        "product_family_id": norm(row.get("product_family_id")),
        "standard_product_name": norm(product.get("standard_product_name")),
        "priority": "P2",
        "fact_group": "official_specification_candidate",
        "field_name": norm(row.get("spec_category")) or "official_specification",
        "field_value": field_value,
        "source_url": source_url,
        "evidence_title": norm(row.get("source_title")) or norm(row.get("standard_product_name")),
        "evidence_excerpt": clean_text(row.get("evidence_excerpt"), 1000),
        "source_type": "official_specification_candidate",
        "confidence": confidence_tier,
        "captured_at": norm(row.get("captured_at")),
        "promoted_at": promoted_at,
        "review_status": "auto_cross_checked",
        "note": note,
    }


def merge_by_key(existing: list[dict[str, str]], new_rows: list[dict[str, str]], key_field: str) -> list[dict[str, str]]:
    merged = {norm(row.get(key_field)): row for row in existing if norm(row.get(key_field))}
    for row in new_rows:
        key = norm(row.get(key_field))
        if key:
            merged[key] = row
    return list(merged.values())


def product_spec_pipeline_fact(row: dict[str, str]) -> bool:
    return (
        norm(row.get("source_type")) == "official_specification_candidate"
        and "product_spec_evidence_promotion_20260527" in norm(row.get("note"))
    )


def run() -> int:
    promoted_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    specs = read_csv(PRODUCT_SPEC_PATH)
    products = read_csv(PRODUCT_MASTER_PATH)
    families = read_csv(PRODUCT_FAMILY_MASTER_PATH)
    skus = read_csv(PRODUCT_SKU_MASTER_PATH)
    product_by_id = {norm(row.get("product_id")): row for row in products if norm(row.get("product_id"))}
    family_map = family_product_map(products, skus)
    family_index = product_family_inference_index(families)
    domains = company_domains(read_csv(COMPANY_OFFICIAL_WEBSITE_PATH))

    high_by_product: dict[str, list[dict[str, str]]] = defaultdict(list)
    operational_rows: list[dict[str, Any]] = []
    medium_pool: list[dict[str, Any]] = []
    status_counts = Counter()
    inferred_family_counts = Counter()

    for raw_row in specs:
        row = dict(raw_row)
        inferred_family = infer_product_family(row, family_index)
        inferred_reason = ""
        if inferred_family:
            family, inferred_reason = inferred_family
            row["product_family_id"] = norm(family.get("product_family_id"))
            row["product_family"] = norm(family.get("product_family"))
            row["brand"] = norm(row.get("brand")) or norm(family.get("brand"))
        family_id = norm(row.get("product_family_id"))
        product_ids = sorted(pid for pid in family_map.get(family_id, set()) if pid in product_by_id)
        category = norm(row.get("spec_category"))
        alignment = source_alignment(row, domains)
        confidence = norm(row.get("confidence"))
        query_type = norm(row.get("source_query_type"))
        reason = ""
        status = "planned"
        target_product_id = ""
        if category not in MEDIUM_SPEC_CATEGORIES:
            status = "out_of_scope_spec_category"
            reason = "spec category is not targeted for master technical specs"
        elif noisy_spec(row):
            status = "filtered_noise"
            reason = "spec value/title failed quality filters"
        elif not family_id:
            status = "plan_missing_product_family"
            reason = "spec row lacks product_family_id"
        elif not product_ids:
            status = "plan_family_to_product_mapping"
            reason = "family id has no Product_Master product mapping"
        elif len(product_ids) > 1:
            status = "medium_multi_product_family"
            reason = "family maps to multiple product rows; needs SKU-level review"
        elif alignment in {"blocked_domain", "source_not_cross_checked", "no_source_host"}:
            status = "medium_source_crosscheck"
            reason = f"source alignment is {alignment}"
        elif confidence == "official_site_spec_candidate" and query_type in HIGH_QUERY_TYPES and category in AUTO_SPEC_CATEGORIES:
            target_product_id = product_ids[0]
            if strict_inferred_value_ok(row) and strict_product_context_ok(row) and strict_value_neighborhood_ok(row):
                status = "promote_high_confidence"
                reason = "official-site spec, accepted source, single product family, strict value and product-context gates passed"
                high_by_product[target_product_id].append(row)
            else:
                status = "medium_auto_promotion_guardrail_review"
                reason = "official-site spec source accepted, but value or product context failed conservative auto-promotion gate"
        else:
            status = "medium_review_sample_pool"
            reason = "search-excerpt confidence, packaging field, or non-auto query type"
            target_product_id = product_ids[0] if product_ids else ""
        if inferred_family and status == "promote_high_confidence":
            target_product_id = product_ids[0] if product_ids else ""
            if strict_inferred_family_auto_promotion(row, alignment):
                status = "promote_inferred_family_high_confidence"
                reason = f"{inferred_reason}; strict official-domain inferred-family gate passed"
                row["_inferred_family_auto_promoted"] = "1"
            else:
                status = "medium_inferred_family_review"
                reason = f"{inferred_reason}; review inferred family mapping before master promotion"
                if high_by_product.get(target_product_id) and row in high_by_product[target_product_id]:
                    high_by_product[target_product_id].remove(row)
        elif inferred_family and status == "medium_source_crosscheck":
            status = "medium_inferred_family_source_crosscheck"
            reason = f"{inferred_reason}; source alignment is {alignment}"
        elif inferred_family and status == "medium_multi_product_family":
            status = "medium_inferred_multi_product_family"
            reason = f"{inferred_reason}; family maps to multiple product rows"
        elif inferred_family and status == "medium_auto_promotion_guardrail_review":
            status = "medium_inferred_family_review"
            reason = f"{inferred_reason}; value/context failed conservative auto-promotion gate"
        elif inferred_family and status == "medium_review_sample_pool":
            status = "medium_inferred_family_review"
            reason = f"{inferred_reason}; review inferred family mapping before master promotion"
        if inferred_family:
            inferred_family_counts[status] += 1
        status_counts[status] += 1
        operational = {
            "spec_id": row.get("spec_id", ""),
            "company_id": row.get("company_id", ""),
            "company": row.get("company", ""),
            "brand": row.get("brand", ""),
            "product_family_id": family_id,
            "product_family": row.get("product_family", ""),
            "target_product_id": target_product_id,
            "spec_name": row.get("spec_name", ""),
            "spec_value": row.get("spec_value", ""),
            "spec_unit": row.get("spec_unit", ""),
            "spec_category": category,
            "confidence": confidence,
            "source_query_type": query_type,
            "source_alignment": alignment,
            "operational_status": status,
            "responsible_module": {
                "promote_high_confidence": "promote_product_specifications_to_master.py",
                "promote_inferred_family_high_confidence": "promote_product_specifications_to_master.py",
                "medium_review_sample_pool": "manual_product_spec_review",
                "medium_auto_promotion_guardrail_review": "manual_product_spec_review",
                "medium_inferred_family_review": "manual_product_spec_review",
                "medium_inferred_family_source_crosscheck": "official_source_crosscheck",
                "medium_inferred_multi_product_family": "sku_split_review",
                "medium_multi_product_family": "sku_split_review",
                "medium_source_crosscheck": "official_source_crosscheck",
                "plan_missing_product_family": "product_family_mapping_backfill",
                "plan_family_to_product_mapping": "product_hierarchy_mapping_backfill",
                "filtered_noise": "spec_extractor_quality_filter",
                "out_of_scope_spec_category": "spec_taxonomy_scope_filter",
            }.get(status, "data_stewardship"),
            "next_action": reason,
            "source_page_url": row.get("source_page_url", ""),
            "source_title": row.get("source_title", ""),
        }
        operational_rows.append(operational)
        if status.startswith("medium_"):
            medium_pool.append(operational)

    facts: list[dict[str, str]] = []
    promotion_rows: list[dict[str, Any]] = []
    per_product_limit = 12
    per_category_limit = 3
    for product_id, rows in high_by_product.items():
        product = product_by_id.get(product_id)
        if not product:
            continue
        by_category: dict[str, list[dict[str, str]]] = defaultdict(list)
        seen_values: set[tuple[str, str]] = set()
        for row in sorted(rows, key=lambda item: (norm(item.get("spec_category")), norm(item.get("spec_name")), norm(item.get("spec_value")))):
            value = spec_fact_value(row)
            key = (norm(row.get("spec_category")).casefold(), value.casefold())
            if key in seen_values:
                continue
            seen_values.add(key)
            category = norm(row.get("spec_category"))
            if len(by_category[category]) < per_category_limit:
                by_category[category].append(row)
        selected: list[dict[str, str]] = []
        for category in sorted(by_category):
            selected.extend(by_category[category])
        selected = selected[:per_product_limit]
        for row in selected:
            confidence_tier = (
                "high_conf_inferred_family_official_domain"
                if row.get("_inferred_family_auto_promoted")
                else "high_conf_official_site_cross_checked"
            )
            fact = fact_row(row, product, promoted_at, confidence_tier)
            facts.append(fact)
            promotion_rows.append(
                {
                    "spec_id": row.get("spec_id", ""),
                    "fact_id": fact["fact_id"],
                    "product_id": product_id,
                    "seed_record_id": product.get("seed_record_id", ""),
                    "company": product.get("company", ""),
                    "brand": product.get("brand", ""),
                    "standard_product_name": product.get("standard_product_name", ""),
                    "field_name": fact["field_name"],
                    "field_value": fact["field_value"],
                    "source_url": fact["source_url"],
                    "promoted_at": promoted_at,
                }
            )

    manual_rows = [row for row in read_csv(MANUAL_PRODUCT_FACT_PATH) if not product_spec_pipeline_fact(row)]
    merged = merge_by_key(manual_rows, facts, "fact_id")
    write_csv(MANUAL_PRODUCT_FACT_PATH, FACT_FIELDS, merged)
    write_csv(PROMOTION_AUDIT_PATH, list(promotion_rows[0].keys()) if promotion_rows else ["spec_id"], promotion_rows)
    write_csv(
        OPERATIONAL_STATUS_PATH,
        [
            "spec_id",
            "company_id",
            "company",
            "brand",
            "product_family_id",
            "product_family",
            "target_product_id",
            "spec_name",
            "spec_value",
            "spec_unit",
            "spec_category",
            "confidence",
            "source_query_type",
            "source_alignment",
            "operational_status",
            "responsible_module",
            "next_action",
            "source_page_url",
            "source_title",
        ],
        operational_rows,
    )

    rng = random.Random(20260527)
    sample_rows: list[dict[str, Any]] = []
    by_bucket: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in medium_pool:
        by_bucket[(row["operational_status"], row["spec_category"])].append(row)
    for bucket_rows in by_bucket.values():
        rng.shuffle(bucket_rows)
        sample_rows.extend(bucket_rows[: min(12, len(bucket_rows))])
    sample_rows = sample_rows[:360]
    write_csv(MEDIUM_REVIEW_SAMPLE_PATH, list(operational_rows[0].keys()) if operational_rows else ["spec_id"], sample_rows)

    lines = [
        "# Product Specification Promotion",
        "",
        f"- Promoted at: {promoted_at}",
        f"- Product_Spec_Evidence rows assessed: {len(specs)}",
        f"- New/updated high-confidence fact rows: {len(facts)}",
        f"- Products receiving technical specs: {len({row['product_id'] for row in facts})}",
        f"- Manual product fact rows after merge: {len(merged)}",
        f"- Medium-confidence sample rows: {len(sample_rows)}",
        "",
        "## Operational Status",
        "",
    ]
    for status, count in status_counts.most_common():
        lines.append(f"- {status}: {count}")
    lines.extend(["", "## Inferred Product Family Mapping", ""])
    if inferred_family_counts:
        for status, count in inferred_family_counts.most_common():
            lines.append(f"- {status}: {count}")
    else:
        lines.append("- none: 0")
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Promotion audit: `{PROMOTION_AUDIT_PATH}`",
            f"- Operational status: `{OPERATIONAL_STATUS_PATH}`",
            f"- Medium review sample: `{MEDIUM_REVIEW_SAMPLE_PATH}`",
        ]
    )
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "promoted_at": promoted_at,
                "assessed_rows": len(specs),
                "fact_rows_written": len(facts),
                "products_with_specs": len({row["product_id"] for row in facts}),
                "manual_fact_rows_after": len(merged),
                "medium_sample_rows": len(sample_rows),
                "status_counts": dict(status_counts),
                "inferred_family_counts": dict(inferred_family_counts),
                "summary": str(SUMMARY_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
