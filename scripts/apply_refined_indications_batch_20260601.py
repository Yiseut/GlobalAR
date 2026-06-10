#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER = DATA_DIR / "product_master.csv"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"
REVIEW_PACK = AUDIT_DIR / "e_group_remaining_review_pack_latest.csv"
SUMMARY_JSON = AUDIT_DIR / "refined_indications_batch_20260601_latest.json"
APPLIED_CSV = AUDIT_DIR / "refined_indications_batch_20260601_latest.csv"
EXCLUDED_CHECK_CSV = AUDIT_DIR / "refined_indications_excluded_check_20260601_latest.csv"

REFINED = [
    ("REC_0849", "Alma Lasers - Alma Duo", "Indicated for the stimulation of blood flow to support sexual function and restore spontaneity in both men and women using focused low-intensity shock wave therapy (LI-ESWT).", "user_confirmed_refined_clinical_path_keep"),
    ("REC_0859", "Candela - CO2RE Intima", "Indicated for the treatment of genitourinary syndrome of menopause (GSM) and stress urinary incontinence (SUI) in adult women.", "user_confirmed_refined_clinical_path_keep"),
    ("REC_0336", "Halozyme Therapeutics - Hylenex", "Indicated as an adjuvant in subcutaneous fluid administration for achieving hydration and to increase the dispersion and absorption of other injected drugs.", "user_confirmed_refined_clinical_path_keep"),
    ("REC_0818", "Solta Medical - VASERlipo", "Indicated for the fragmentation, emulsification and aspiration of soft tissues in plastic and reconstructive surgery.", "user_confirmed_refined_clinical_path_keep"),
    ("REC_0931", "Caregen - DR. CYJ Hair Filler", "Indicated for the treatment of scalp and hair lesions caused by external aggressions and for hair revitalization.", "user_confirmed_refined_quality_repair"),
    ("REC_0561", "Cocoon Medical - Primelase HR excellence", "Intended for the permanent reduction in hair regrowth.", "user_confirmed_refined_quality_repair"),
    ("REC_0834", "Cutera - truSculpt flex+", "Indicated for the improvement of abdominal tone, strengthening of the abdominal muscles, and development of a firmer abdomen.", "user_confirmed_refined_quality_repair"),
    ("REC_0892", "IBSA Derma - Aliaxin EV", "Indicated for the correction of deep skin damage in the face and for facial volume enhancement.", "user_confirmed_refined_quality_repair"),
    ("REC_0890", "IBSA Derma - Aliaxin SR", "Indicated for the correction of medium and deep skin damages of the face and to increase the volume and contour of the lips.", "user_confirmed_refined_quality_repair"),
    ("REC_0316", "APS - Hifu Top", "Indicated for non-invasive lifting and tightening of loose skin around the neck and eyes, correction of downturned mouth, jowls, and perioral wrinkles.", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0853", "Alma Lasers - Alma PrimeX", "Indicated for comprehensive body and facial contouring using combined guided ultrasound and deep radiofrequency heating.", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0041", "Asterasys - Aqua Peel Tera", "Indicated for exfoliation and sebum removal to enhance absorption of skincare products, improvement of skin tone, and treatment of acne, whiteheads, and blackheads.", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0869", "BTL - EMFEMME 360", "适用于改善阴道松弛、性交疼痛、更年期泌尿生殖综合征 (GSM) 及女性尿渗漏/尿失禁问题。", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0957", "Beauty Health - HydraFacial Keravive", "Indicated for improving the appearance of wrinkles and mild-to-moderate acne, reducing temporary redness, and targeting oily skin, congestions, and blemishes.", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0047", "CMed Aesthetics - ARES", "Indicated as an antioxidant and anti-aging mesotherapy treatment for chronologically aged or photoaged skin lacking radiance.", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0477", "Fillmed - NCTF 135 HA", "Indicated for dermal injection into the face, neck, and decollete for intense tissue revitalization, hydration of tired or dull skin, and treatment of superficial wrinkles.", "user_confirmed_refined_not_explicit_rewrite"),
    ("REC_0807", "Galderma - Restylane SHAYPE", "Indicated for chin augmentation and the correction of chin recessions using NASHA HD hyaluronic acid technology.", "user_confirmed_refined_not_explicit_rewrite"),
]

EXCLUDED_CHECK = {
    "REC_0773": "Biovico Xerthra/AOORA remains excluded: ophthalmology and orthopedics path.",
    "REC_0045": "Contura Aquamid reconstruction remains excluded: orthopaedics, animal health and urinary incontinence path.",
}

UPDATEABLE_REVIEW_STATUS_PREFIXES = (
    "user_confirmed_path_keep",
    "user_confirmed_quality_repair",
    "user_confirmed_not_explicit_rewrite",
    "user_confirmed_refined_",
)


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def strip_cites(value: str) -> str:
    return re.sub(r"\s*\[cite:\s*\d+\]\s*", "", clean(value)).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    blob = "||".join(clean(part).casefold() for part in parts)
    return f"{prefix}_{hashlib.sha1(blob.encode('utf-8')).hexdigest()[:12]}"


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
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


def make_row(product: dict[str, str], source: dict[str, str], label: str, indication: str, review_status: str, checked_at: str) -> dict[str, str]:
    product_id = clean(product.get("product_id"))
    source_url = clean(source.get("source_url"))
    return {
        "product_id": product_id,
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "jurisdiction": "Global",
        "regulator": "Official source / user-confirmed refinement",
        "regulatory_pathway": "User-confirmed refined indication normalization",
        "status": "User-confirmed refined official indication/use wording",
        "registration_no": "",
        "approval_date": "",
        "expiry_date": "",
        "registered_name": clean(product.get("registered_name") or product.get("standard_product_name")),
        "approved_indication": indication,
        "intended_use": indication,
        "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("company")),
        "local_holder": clean(product.get("local_holder")),
        "source_key": stable_id("refined_indication", product_id, source_url, indication),
        "source_url": source_url,
        "source_type": clean(source.get("source_type")) or "existing_candidate_source",
        "evidence_title": clean(source.get("evidence_title")) or label,
        "evidence_excerpt": clean(source.get("candidate_text")),
        "official_description_exact": indication,
        "official_description_source_field": "user_refined_normalization_20260601",
        "field_note": "User feedback 2026-06-01 refined the indication wording; cite markers were removed before database writeback.",
        "checked_at": checked_at,
        "reviewed_by": "user_feedback_20260601",
        "review_status": review_status,
        "confidence": "user_confirmed_refined_indication",
    }


def source_for_seed(seed: str, review_by_seed: dict[str, dict[str, str]], manual_rows: list[dict[str, str]]) -> dict[str, str]:
    if seed in review_by_seed:
        return review_by_seed[seed]
    for row in manual_rows:
        if clean(row.get("seed_record_id")) == seed and clean(row.get("source_url")):
            return {
                "source_url": clean(row.get("source_url")),
                "source_type": clean(row.get("source_type")),
                "evidence_title": clean(row.get("evidence_title")),
                "candidate_text": clean(row.get("evidence_excerpt") or row.get("official_description_exact") or row.get("approved_indication")),
            }
    return {}


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, review_rows = read_csv(REVIEW_PACK)

    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}
    review_by_seed = {clean(row.get("seed_record_id")): row for row in review_rows if clean(row.get("seed_record_id"))}

    changed = 0
    added = 0
    applied: list[dict[str, str]] = []

    for seed, label, raw_indication, review_status in REFINED:
        indication = strip_cites(raw_indication)
        product = product_by_seed.get(seed)
        if not product:
            applied.append({"seed_record_id": seed, "label": label, "action": "not_found_or_excluded", "old_indication": "", "new_indication": indication, "source_url": ""})
            continue
        source = source_for_seed(seed, review_by_seed, manual_rows)
        matching_indexes = [
            idx
            for idx, row in enumerate(manual_rows)
            if clean(row.get("seed_record_id")) == seed
            and clean(row.get("approved_indication") or row.get("official_description_exact"))
            and clean(row.get("review_status")).startswith(UPDATEABLE_REVIEW_STATUS_PREFIXES)
        ]
        if matching_indexes:
            idx = matching_indexes[-1]
            row = manual_rows[idx]
            old_indication = clean(row.get("approved_indication") or row.get("official_description_exact"))
            for field in ["approved_indication", "intended_use", "official_description_exact"]:
                row[field] = indication
            row["review_status"] = review_status
            row["confidence"] = "user_confirmed_refined_indication"
            row["checked_at"] = checked_at
            row["field_note"] = "User feedback 2026-06-01 refined the indication wording; cite markers were removed before database writeback."
            changed += 1
            applied.append({"seed_record_id": seed, "label": label, "action": "updated", "old_indication": old_indication, "new_indication": indication, "source_url": clean(row.get("source_url"))})
            continue

        new_row = make_row(product, source, label, indication, review_status, checked_at)
        manual_rows.append(new_row)
        added += 1
        applied.append({"seed_record_id": seed, "label": label, "action": "added", "old_indication": "", "new_indication": indication, "source_url": clean(new_row.get("source_url"))})

    backup = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_refined_batch_{stamp}.csv"
    shutil.copy2(MANUAL_INDICATION, backup)
    write_csv(MANUAL_INDICATION, manual_fields, manual_rows)

    excluded_check_rows = []
    for seed, note in EXCLUDED_CHECK.items():
        product = product_by_seed.get(seed)
        excluded_check_rows.append(
            {
                "seed_record_id": seed,
                "active_product_found": "yes" if product else "no",
                "product_id": clean(product.get("product_id")) if product else "",
                "note": note,
            }
        )

    write_csv(APPLIED_CSV, ["seed_record_id", "label", "action", "old_indication", "new_indication", "source_url"], applied)
    write_csv(EXCLUDED_CHECK_CSV, ["seed_record_id", "active_product_found", "product_id", "note"], excluded_check_rows)

    summary = {
        "checked_at": checked_at,
        "refined_items": len(REFINED),
        "updated_existing_rows": changed,
        "new_manual_indication_rows_added": added,
        "not_found_or_excluded": sum(1 for row in applied if row["action"] == "not_found_or_excluded"),
        "manual_backup": str(backup),
        "applied_csv": str(APPLIED_CSV),
        "excluded_check_csv": str(EXCLUDED_CHECK_CSV),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
