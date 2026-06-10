#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from apply_e_group_live_url_indications_20260601 import extract_best_candidate
from apply_e_group_local_spec_indication_candidates_20260601 import (
    INDICATION_FIELDS,
    PRODUCT_MASTER,
    REACQUIRE_QUEUE,
    clean,
    has_indication,
    make_manual_row,
    product_tokens,
    read_csv,
    stable_id,
    write_csv,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

COMPANY_SOURCE_JSONL = DATA_DIR / "company_official_source_evidence.jsonl"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_company_source_indication_apply_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_company_source_indication_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_company_source_indication_skipped_latest.csv"
CANDIDATES_CSV = AUDIT_DIR / "e_group_company_source_indication_candidates_latest.csv"


ACCEPTED_OFFICIAL_CANDIDATES = {"likely", "possible"}
ACCEPTED_CONFIDENCE = {
    "official_domain_candidate",
    "product_official_domain_candidate",
    "product_official_search_candidate",
    "brand_official_search_candidate",
}
ACCEPTED_QUERY_TYPES = {
    "product_ifu_labeling",
    "product_official_page",
    "official_ifu_catalog",
    "official_product_portfolio",
    "product_certificate_registration",
}


def text_blob(row: dict[str, Any]) -> str:
    return " ".join(
        clean(row.get(key))
        for key in ["title", "url", "evidence_excerpt", "raw_text"]
        if clean(row.get(key))
    )


def source_matches_product(row: dict[str, Any], product: dict[str, str]) -> bool:
    blob = text_blob(row).casefold().replace("-", " ")
    tokens = product_tokens(product)
    return bool(tokens) and any(token in blob for token in tokens)


def main() -> None:
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, queue_rows = read_csv(REACQUIRE_QUEUE)

    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}
    company_to_products: dict[str, list[dict[str, str]]] = defaultdict(list)
    existing_seed_with_indication = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if clean(row.get("seed_record_id")) and has_indication(row)
    }
    target_seeds = {clean(row.get("seed_record_id")) for row in queue_rows if clean(row.get("seed_record_id"))} - existing_seed_with_indication
    for seed in target_seeds:
        product = product_by_seed.get(seed)
        if product:
            company_to_products[clean(product.get("company_id"))].append(product)

    candidates: list[dict[str, str]] = []
    best_by_seed: dict[str, tuple[int, dict[str, Any], str]] = {}
    skip_counter: Counter[str] = Counter()
    scanned_rows = 0
    matched_source_rows = 0

    with COMPANY_SOURCE_JSONL.open("r", encoding="utf-8") as handle:
        for line in handle:
            scanned_rows += 1
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                skip_counter["bad_jsonl"] += 1
                continue
            company_id = clean(row.get("company_id"))
            products = company_to_products.get(company_id, [])
            if not products:
                continue
            if clean(row.get("official_candidate")) not in ACCEPTED_OFFICIAL_CANDIDATES:
                continue
            if clean(row.get("confidence")) not in ACCEPTED_CONFIDENCE:
                continue
            if clean(row.get("query_type")) not in ACCEPTED_QUERY_TYPES:
                continue
            matched_products = [product for product in products if source_matches_product(row, product)]
            if not matched_products:
                continue
            matched_source_rows += 1
            fetch = {
                "url": clean(row.get("url")),
                "final_url": clean(row.get("url")),
                "title": clean(row.get("title")),
                "text": clean(row.get("evidence_excerpt") or row.get("raw_text")),
            }
            for product in matched_products:
                seed = clean(product.get("seed_record_id"))
                indication, reason, score = extract_best_candidate(product, fetch)
                if not indication:
                    skip_counter[reason] += 1
                    continue
                source_score = score
                if clean(row.get("official_candidate")) == "likely":
                    source_score += 8
                if clean(row.get("confidence")) == "product_official_domain_candidate":
                    source_score += 6
                candidate = {
                    "seed_record_id": seed,
                    "product_id": clean(product.get("product_id")),
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "score": str(source_score),
                    "source_url": clean(row.get("url")),
                    "title": clean(row.get("title")),
                    "official_candidate": clean(row.get("official_candidate")),
                    "confidence": clean(row.get("confidence")),
                    "query_type": clean(row.get("query_type")),
                    "indication": indication,
                }
                candidates.append(candidate)
                current = best_by_seed.get(seed)
                if current is None or source_score > current[0]:
                    best_by_seed[seed] = (source_score, row, indication)

    existing_keys = {
        (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")),
        )
        for row in manual_rows
    }

    new_rows: list[dict[str, str]] = []
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for seed, (score, source, indication) in sorted(best_by_seed.items(), key=lambda item: (-item[1][0], item[0])):
        product = product_by_seed.get(seed)
        if not product:
            skipped.append({"seed_record_id": seed, "reason": "product_not_found"})
            continue
        source_url = clean(source.get("url"))
        source_row = {
            "source_page_url": source_url,
            "source_query_type": clean(source.get("query_type")) or "company_official_source_evidence",
            "source_title": clean(source.get("title")),
            "evidence_excerpt": indication,
        }
        manual = make_manual_row(product, source_row, indication, checked_at)
        manual["source_key"] = stable_id("egroup_company_source_indication", clean(product.get("product_id")), source_url, indication)
        manual["source_type"] = "company_official_source_evidence"
        manual["regulatory_pathway"] = "company official source pool text extraction"
        manual["official_description_source_field"] = "company_official_source_evidence.raw_text"
        manual["reviewed_by"] = "auto_company_source_indication_extraction_20260601"
        manual["review_status"] = "auto_promoted_company_official_source_indication"
        manual["confidence"] = "high_confidence_company_official_source_text"
        key = (
            clean(manual.get("product_id")),
            clean(manual.get("source_url")),
            clean(manual.get("official_description_exact")),
        )
        if key in existing_keys:
            skipped.append({"seed_record_id": seed, "reason": "duplicate_exact_key"})
            continue
        existing_keys.add(key)
        new_rows.append(manual)
        applied.append(
            {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "score": str(score),
                "source_url": source_url,
                "indication": indication,
            }
        )

    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_company_source_indication_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        output_fields = manual_fields or INDICATION_FIELDS
        for field in INDICATION_FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, manual_rows + new_rows)
    else:
        backup_path = None

    write_csv(
        CANDIDATES_CSV,
        [
            "seed_record_id",
            "product_id",
            "company",
            "brand",
            "standard_product_name",
            "score",
            "source_url",
            "title",
            "official_candidate",
            "confidence",
            "query_type",
            "indication",
        ],
        candidates,
    )
    write_csv(
        APPLIED_CSV,
        ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "score", "source_url", "indication"],
        applied,
    )
    write_csv(SKIPPED_CSV, ["seed_record_id", "reason"], skipped)

    summary = {
        "checked_at": checked_at,
        "target_products": len(target_seeds),
        "scanned_company_source_rows": scanned_rows,
        "matched_source_rows": matched_source_rows,
        "candidate_rows": len(candidates),
        "candidate_products": len({row["seed_record_id"] for row in candidates}),
        "applied_rows": len(applied),
        "skipped_rows": len(skipped),
        "backup_path": str(backup_path) if backup_path else "",
        "skip_reasons": dict(skip_counter.most_common()),
        "outputs": {
            "summary_json": str(SUMMARY_JSON),
            "applied_csv": str(APPLIED_CSV),
            "skipped_csv": str(SKIPPED_CSV),
            "candidates_csv": str(CANDIDATES_CSV),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
