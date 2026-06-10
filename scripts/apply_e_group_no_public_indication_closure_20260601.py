#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER = DATA_DIR / "product_master.csv"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"
REVIEW_PACK = AUDIT_DIR / "e_group_remaining_review_pack_latest.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_no_public_indication_closure_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_no_public_indication_closure_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_no_public_indication_closure_skipped_latest.csv"

UNAVAILABLE_STATUS = "unavailable_verified_no_public_indication_after_exa_api_search"

FIELDS = [
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "jurisdiction",
    "regulator",
    "regulatory_pathway",
    "status",
    "registration_no",
    "approval_date",
    "expiry_date",
    "registered_name",
    "approved_indication",
    "intended_use",
    "legal_manufacturer",
    "local_holder",
    "source_key",
    "source_url",
    "source_type",
    "evidence_title",
    "evidence_excerpt",
    "official_description_exact",
    "official_description_source_field",
    "field_note",
    "checked_at",
    "reviewed_by",
    "review_status",
    "confidence",
]


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    blob = "||".join(clean(part).casefold() for part in parts)
    return f"{prefix}_{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def has_indication(row: dict[str, str]) -> bool:
    return bool(clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")))


def main() -> None:
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, review_rows = read_csv(REVIEW_PACK)

    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}
    existing_seed_with_indication = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if clean(row.get("seed_record_id")) and has_indication(row)
    }
    existing_unavailable_seeds = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if UNAVAILABLE_STATUS in clean(row.get("review_status")).casefold()
    }
    existing_keys = {
        (
            clean(row.get("product_id")),
            clean(row.get("source_key")),
        )
        for row in manual_rows
    }

    new_rows: list[dict[str, str]] = []
    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    by_group: Counter[str] = Counter()

    for review in review_rows:
        seed = clean(review.get("seed_record_id"))
        product = product_by_seed.get(seed)
        if not seed or not product:
            skipped.append({**review, "skip_reason": "product_not_found"})
            continue
        if seed in existing_seed_with_indication:
            skipped.append({**review, "skip_reason": "already_has_indication"})
            continue
        if seed in existing_unavailable_seeds:
            skipped.append({**review, "skip_reason": "already_marked_unavailable"})
            continue

        product_id = clean(product.get("product_id"))
        action_group = clean(review.get("action_group"))
        reason = clean(review.get("reason"))
        source_url = clean(review.get("source_url"))
        candidate_text = clean(review.get("candidate_text"))
        source_key = stable_id("egroup_no_public_indication", product_id, action_group, reason, source_url, candidate_text[:240])
        key = (product_id, source_key)
        if key in existing_keys:
            skipped.append({**review, "skip_reason": "duplicate_key"})
            continue
        existing_keys.add(key)
        by_group[action_group] += 1

        note = (
            "After local evidence extraction plus two Exa API official-source passes on 2026-06-01, no reliable public "
            "official indication/IFU wording could be promoted for this product. This row closes the dashboard gap as "
            "publicly unavailable/unreliable, without inventing an indication."
        )
        row = {
            "product_id": product_id,
            "seed_record_id": seed,
            "company_id": clean(product.get("company_id")),
            "company": clean(product.get("company")),
            "brand": clean(product.get("brand")),
            "jurisdiction": "Global",
            "regulator": "No public official indication found",
            "regulatory_pathway": "Automated official-source reacquisition closure",
            "status": "No reliable public official indication text found after two API passes",
            "registration_no": "",
            "approval_date": "",
            "expiry_date": "",
            "registered_name": clean(product.get("registered_name") or product.get("standard_product_name") or product.get("brand")),
            "approved_indication": "",
            "intended_use": "",
            "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("manufactured_by") or product.get("company")),
            "local_holder": clean(product.get("local_holder")),
            "source_key": source_key,
            "source_url": source_url,
            "source_type": "no_public_official_indication_closure",
            "evidence_title": clean(review.get("evidence_title")) or "No public official indication closure",
            "evidence_excerpt": candidate_text or f"{action_group}: {reason}",
            "official_description_exact": "",
            "official_description_source_field": "not_promoted_no_reliable_public_official_indication",
            "field_note": note,
            "checked_at": checked_at,
            "reviewed_by": "auto_e_group_no_public_indication_closure_20260601",
            "review_status": UNAVAILABLE_STATUS,
            "confidence": "searched_no_reliable_public_official_indication",
        }
        new_rows.append(row)
        applied.append(
            {
                "seed_record_id": seed,
                "product_id": product_id,
                "company": row["company"],
                "brand": row["brand"],
                "standard_product_name": clean(product.get("standard_product_name")),
                "action_group": action_group,
                "reason": reason,
                "source_url": source_url,
            }
        )

    backup_path = ""
    if new_rows:
        backup = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_no_public_indication_closure_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup)
        backup_path = str(backup)
        output_fields = manual_fields or list(FIELDS)
        for field in FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, [*manual_rows, *new_rows])

    write_csv(
        APPLIED_CSV,
        ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "action_group", "reason", "source_url"],
        applied,
    )
    write_csv(
        SKIPPED_CSV,
        ["seed_record_id", "company", "brand", "standard_product_name", "action_group", "reason", "source_url", "skip_reason"],
        skipped,
    )
    summary = {
        "checked_at": checked_at,
        "review_pack_rows": len(review_rows),
        "applied_rows": len(applied),
        "skipped_rows": len(skipped),
        "applied_by_group": dict(by_group),
        "backup_path": backup_path,
        "status": UNAVAILABLE_STATUS,
        "outputs": {
            "summary_json": str(SUMMARY_JSON),
            "applied_csv": str(APPLIED_CSV),
            "skipped_csv": str(SKIPPED_CSV),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
