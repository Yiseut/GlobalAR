#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER = DATA_DIR / "product_master.csv"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_live_url_curated_batch_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_live_url_curated_batch_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_live_url_curated_batch_skipped_latest.csv"


CURATED_ROWS: list[dict[str, str]] = [
    {
        "seed_record_id": "REC_0018",
        "source_url": "https://lat.agnesmedical.com/product/agnes-s/",
        "indication": "Indicated for use in dermatological and general surgical procedures for electrocoagulation and hemostasis.",
    },
    {
        "seed_record_id": "REC_0119",
        "source_url": "https://sinclair.com/brands/energy-devices/primelase-excellence/",
        "indication": "Intended for the medical treatment of pseudofolliculitis and hirsutism; also intended for treatment of vascular lesions, pigmentary lesions, acne vulgaris, and follicular treatments.",
    },
    {
        "seed_record_id": "REC_0142",
        "source_url": "https://bodyhealth.com.ar/en/refreeze-en/",
        "indication": "Indicated for generalized adiposity, cellulite, and flaccidity.",
    },
    {
        "seed_record_id": "REC_0611",
        "source_url": "https://revanesse.com/ifu",
        "indication": "Approved in the U.S. to correct the appearance of facial wrinkles and creases, including nasolabial folds.",
    },
    {
        "seed_record_id": "REC_0828",
        "source_url": "https://www.cynosure.com/product/smartlipo-triplex/",
        "indication": "Intended for surgical incision, excision, vaporization, ablation, and coagulation of soft tissue.",
    },
    {
        "seed_record_id": "REC_0855",
        "source_url": "https://marketing.syneron-candela.com/Vbeam-Prima-Launch-Registration.html",
        "indication": "Indicated for treatment of vascular, pigmented, and certain non-pigmented lesions.",
    },
    {
        "seed_record_id": "REC_1004",
        "source_url": "https://www.cynosure.com/product/ultra/",
        "indication": "Indicated for dermatological procedures requiring soft-tissue coagulation, treatment of actinic keratosis, and treatment of benign pigmented lesions including lentigos, solar lentigos, and ephelides.",
    },
    {
        "seed_record_id": "REC_0048",
        "source_url": "https://uk.fillmed.com/art-filler/",
        "indication": "Indicated for soft lip volume, lip contour, and peri-oral wrinkles.",
    },
    {
        "seed_record_id": "REC_0075",
        "source_url": "https://bodyhealthgroup.es/en/himfu-en/",
        "indication": "Indicated for treatment of localized fat deposits.",
    },
    {
        "seed_record_id": "REC_0982",
        "source_url": "https://lumenis.com/aesthetics/products/legend-pro/",
        "indication": "Indications include skin resurfacing and treatment of mild to moderate wrinkles and rhytids.",
    },
]


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
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def has_indication(row: dict[str, str]) -> bool:
    return bool(clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")))


def make_row(product: dict[str, str], source_url: str, indication: str, checked_at: str) -> dict[str, str]:
    product_id = clean(product.get("product_id"))
    return {
        "product_id": product_id,
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "jurisdiction": "Global",
        "regulator": "Official product/IFU/source text",
        "regulatory_pathway": "curated live URL full-text extraction QA",
        "status": "Official use/indication wording curated from live fetched source text",
        "registration_no": "",
        "approval_date": "",
        "expiry_date": "",
        "registered_name": clean(product.get("registered_name") or product.get("standard_product_name") or product.get("brand")),
        "approved_indication": indication,
        "intended_use": indication,
        "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("manufactured_by") or product.get("company")),
        "local_holder": clean(product.get("local_holder")),
        "source_key": stable_id("egroup_live_url_curated", product_id, source_url, indication),
        "source_url": source_url,
        "source_type": "live_official_url_fetch_curated",
        "evidence_title": f"{clean(product.get('company'))} {clean(product.get('brand'))}".strip(),
        "evidence_excerpt": indication,
        "official_description_exact": indication,
        "official_description_source_field": "live fetched page/pdf text",
        "field_note": "Promoted only after the live URL batch was manually QA-sampled for product/source alignment; mismatched full-site pages were excluded.",
        "checked_at": checked_at,
        "reviewed_by": "auto_live_url_curated_batch_20260601",
        "review_status": "auto_promoted_live_source_curated",
        "confidence": "high_confidence_live_source_curated",
    }


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}
    existing_seed_with_indication = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if clean(row.get("seed_record_id")) and has_indication(row)
    }
    existing_keys = {
        (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")),
        )
        for row in manual_rows
    }

    applied: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    new_rows: list[dict[str, str]] = []

    for item in CURATED_ROWS:
        seed = clean(item.get("seed_record_id"))
        product = product_by_seed.get(seed)
        if not product:
            skipped.append({**item, "reason": "product_not_found_or_excluded"})
            continue
        if seed in existing_seed_with_indication:
            skipped.append({**item, "reason": "already_has_indication"})
            continue
        row = make_row(product, clean(item.get("source_url")), clean(item.get("indication")), checked_at)
        key = (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact")),
        )
        if key in existing_keys:
            skipped.append({**item, "reason": "duplicate_exact_key"})
            continue
        existing_keys.add(key)
        existing_seed_with_indication.add(seed)
        new_rows.append(row)
        applied.append(
            {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "source_url": clean(item.get("source_url")),
                "indication": clean(item.get("indication")),
            }
        )

    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_live_url_curated_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        output_fields = manual_fields or FIELDS
        for field in FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, manual_rows + new_rows)
    else:
        backup_path = None

    applied_fields = ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "source_url", "indication"]
    skipped_fields = ["seed_record_id", "source_url", "indication", "reason"]
    write_csv(APPLIED_CSV, applied_fields, applied)
    write_csv(SKIPPED_CSV, skipped_fields, skipped)

    summary = {
        "checked_at": checked_at,
        "input_rows": len(CURATED_ROWS),
        "applied_rows": len(applied),
        "skipped_rows": len(skipped),
        "backup_path": str(backup_path) if backup_path else "",
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
