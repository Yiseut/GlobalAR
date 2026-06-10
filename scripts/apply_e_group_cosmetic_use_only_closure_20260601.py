#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER = DATA_DIR / "product_master.csv"
OFFICIAL_INDICATION = DATA_DIR / "official_indication_evidence.csv"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"
UNCERTAIN = AUDIT_DIR / "e_group_indication_extraction_uncertain_latest.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_cosmetic_use_only_closure_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_cosmetic_use_only_closure_latest.csv"

CLOSURE_TEXT = "Cosmetic Use Only / 无医疗适应症；官方来源仅提供美容用途或非诊断、非治疗免责声明。"


def clean(value: object) -> str:
    return str(value or "").strip()


def stable_id(prefix: str, *parts: object) -> str:
    blob = "||".join(clean(part).casefold() for part in parts)
    return f"{prefix}_{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, official_rows = read_csv(OFFICIAL_INDICATION)
    _, uncertain_rows = read_csv(UNCERTAIN)

    product_by_id = {clean(row.get("product_id")): row for row in product_rows if clean(row.get("product_id"))}
    existing_indication_ids = {
        clean(row.get("product_id"))
        for row in [*manual_rows, *official_rows]
        if clean(row.get("product_id")) and clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use"))
    }

    selected: dict[str, dict[str, str]] = {}
    for row in uncertain_rows:
        product_id = clean(row.get("product_id"))
        if clean(row.get("reason")) != "generic_or_negative_intended_use_text":
            continue
        if not product_id or product_id in existing_indication_ids or product_id not in product_by_id:
            continue
        selected.setdefault(product_id, row)

    new_rows: list[dict[str, str]] = []
    for product_id, source in sorted(selected.items(), key=lambda item: (clean(item[1].get("company")), clean(item[1].get("brand")))):
        product = product_by_id[product_id]
        source_url = clean(source.get("source_url"))
        row = {
            "product_id": product_id,
            "seed_record_id": clean(product.get("seed_record_id") or source.get("seed_record_id")),
            "company_id": clean(product.get("company_id")),
            "company": clean(product.get("company") or source.get("company")),
            "brand": clean(product.get("brand") or source.get("brand")),
            "jurisdiction": "Global",
            "regulator": "Not applicable",
            "regulatory_pathway": "Cosmetic-use closure from official/generic negative wording",
            "status": "No medical indication claimed in available official source",
            "registration_no": "",
            "approval_date": "",
            "expiry_date": "",
            "registered_name": clean(product.get("registered_name") or product.get("standard_product_name")),
            "approved_indication": CLOSURE_TEXT,
            "intended_use": CLOSURE_TEXT,
            "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("company")),
            "local_holder": clean(product.get("local_holder")),
            "source_key": stable_id("cosmetic_use_only", product_id, source_url, CLOSURE_TEXT),
            "source_url": source_url,
            "source_type": clean(source.get("source_type")) or "official_product_source",
            "evidence_title": clean(source.get("evidence_title")) or "Official cosmetic-use/no-medical-claim closure",
            "evidence_excerpt": clean(source.get("source_evidence_excerpt") or source.get("extracted_text")),
            "official_description_exact": CLOSURE_TEXT,
            "official_description_source_field": "existing_official_source_generic_or_negative_text",
            "field_note": (
                "User rule 2026-06-01: generic or negative medical-use statements should be closed as Cosmetic Use Only / "
                "no medical indication, not chased as disease-treatment indications."
            ),
            "checked_at": checked_at,
            "reviewed_by": "user_feedback_20260601",
            "review_status": "user_confirmed_cosmetic_use_only_no_medical_indication",
            "confidence": "user_confirmed_closure_from_generic_negative_official_text",
        }
        new_rows.append(row)

    backup = ""
    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_cosmetic_use_only_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        backup = str(backup_path)
        write_csv(MANUAL_INDICATION, manual_fields, [*manual_rows, *new_rows])

    applied_fields = [
        "product_id",
        "seed_record_id",
        "company",
        "brand",
        "standard_product_name",
        "source_url",
        "closure_text",
    ]
    write_csv(
        APPLIED_CSV,
        applied_fields,
        [
            {
                "product_id": row["product_id"],
                "seed_record_id": row["seed_record_id"],
                "company": row["company"],
                "brand": row["brand"],
                "standard_product_name": product_by_id[row["product_id"]].get("standard_product_name", ""),
                "source_url": row["source_url"],
                "closure_text": CLOSURE_TEXT,
            }
            for row in new_rows
        ],
    )

    summary = {
        "checked_at": checked_at,
        "eligible_generic_or_negative_products": len(selected),
        "new_manual_indication_rows_added": len(new_rows),
        "manual_backup": backup,
        "applied_csv": str(APPLIED_CSV),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
