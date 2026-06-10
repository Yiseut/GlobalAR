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
REVIEW_PACK = AUDIT_DIR / "e_group_remaining_review_pack_latest.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_not_explicit_direct_batch_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_not_explicit_direct_batch_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_not_explicit_direct_batch_skipped_latest.csv"


DIRECT_REWRITES: list[tuple[str, str]] = [
    (
        "REC_0517",
        "Intended for localized adipose-tissue treatment using Coolwaves energy focused in subcutaneous fat while preserving adjacent tissues.",
    ),
    ("REC_0241", "Intended for skin rejuvenation and ablative Er:YAG laser treatments."),
    ("REC_0065", "Intended for simultaneous laser-assisted liposuction, fat reduction and skin tightening."),
    ("REC_0465", "Intended for breast augmentation or reconstruction using silicone breast implants."),
    ("REC_0534", "Cosmetic transdermal delivery products intended for professional use."),
    ("REC_0774", "Intended for laser treatment of skin lesions and cosmetic blemishes."),
    ("REC_0034", "Intended for skin analysis of pores, oil, wrinkles, pigmentation, moisture, elasticity, skin temperature and skin tone."),
    ("REC_0911", "Intended for wrinkle improvement using the ULTRAFORMER/Shurink focused-ultrasound platform."),
    ("REC_0516", "Intended for treatment of cellulite and localized adiposity using microwave energy."),
    ("REC_0135", "Indicated for treatment of pseudogynecomastia and for reduction of localized fat deposits on the abdomen, thighs, arms, flanks, chin and knees."),
    ("REC_0524", "Indicated for inflammatory acne, scar attenuation and melasma treatment, and for aesthetic treatment of sagging or aging skin, skin rejuvenation, tightening and stretch marks."),
    ("REC_0133", "Intended as a superficial chemical peel for wrinkles, texture irregularities, smoker's complexion and pigment disorders."),
    ("REC_0200", "Indicated for brightening and lightening the appearance of uneven skin tone and visibly reducing the appearance of hyperpigmented skin concerns."),
    ("REC_0175", "Indicated for microneedling treatment of scars, especially acne scars, injury scars, burn scars and stretch marks."),
    ("REC_0219", "Intended for safe and long-lasting filling of moderate wrinkles using a cross-linked hyaluronic acid gel with lidocaine."),
    ("REC_0383", "Intended for contact surgery or vaporization of lesions such as condylomas, fibromas, vascular lesions, pigmented spots, keratoses and warts, and for photobiomodulation applications."),
    ("REC_0243", "Intended for Endolift laser treatment of progressive lipodystrophy, acne scars and cutaneous ptosis using a 1470 nm wavelength."),
    ("REC_0998", "Intended for skin toning, photorejuvenation and treatment of pigmented lesions, scars and tattoos."),
    ("REC_0810", "Intended to assist recovery from surgical body procedures."),
    ("REC_0224", "Intended for hyaluronic acid dermal-filler augmentation of the cheeks, chin, forehead, jawline or nose."),
    ("REC_0263", "Intended for skin rejuvenation with Exolure exosome products."),
    ("REC_0889", "Intended to restore loss of fullness, shape facial contours and restore depressions in skin and tissue."),
    ("REC_0887", "Indicated for structural tissue support and optimization of tissue quality, with focus on age-related changes in superficial adipose compartments."),
    ("REC_0839", "Intended to improve and treat skin irregularities including sun spots, age spots, freckles, pigmentation and superficial veins."),
    ("REC_0466", "Cleared for dermatological and general surgical procedures for electrocoagulation and hemostasis."),
    ("REC_0122", "FDA-cleared to improve the appearance of facial acne scars in adults aged 22 years and older with Fitzpatrick skin types I-III."),
    ("REC_0696", "Indicated for glabellar lines; development indications include facial wrinkles, masseter muscle reduction, spasticity, spasm or pain, hair loss and scars."),
    ("REC_0486", "Intended to improve the appearance of fine lines and wrinkles, skin clarity, dark spots, mild to moderate acne, superficial acne scarring, keratoses, benign lentigines, pseudofolliculitis and keratosis pilaris."),
    ("REC_0460", "Intended for administering pharmaceuticals through a device designed to come into direct contact with the drug."),
    ("REC_0440", "Indicated for melasma, post-inflammatory hyperpigmentation, age spots, visible signs of aging, uneven skin tone, photoaging, dehydrated or malnourished skin and decreased collagen production."),
    ("REC_0483", "Indicated as a biorevitalizing solution for discolored skin."),
    ("REC_0983", "Intended for personalized body contouring through radiofrequency heating of subcutaneous fat, including targeting stubborn fat cells."),
    ("REC_1008", "Intended as an 830 nm LED low-level light therapy system to enhance aesthetic treatment results and minimize downtime."),
    ("REC_1007", "Intended for muscle activation treatment of the abdominal and oblique muscle groups."),
    ("REC_1009", "Intended for non-ablative fractional resurfacing to revitalize and brighten skin by stimulating collagen and elastin in the mid-dermis."),
    ("REC_0703", "Intended to increase skin elasticity and density."),
    ("REC_0218", "Indicated for cutaneous rejuvenation, prevention of photoaging damage, treatment of stretch marks and preparation before intradermal fillers."),
    ("REC_0129", "Indicated for temporary improvement of moderate to severe glabellar wrinkles related to corrugator and/or procerus muscle activity in adults aged 20 to 65."),
    ("REC_0489", "Intended for skin rejuvenation, wrinkle correction and volume augmentation."),
    ("REC_0885", "Intended for skin rejuvenation, wrinkle correction and volume augmentation."),
    ("REC_0884", "Intended for skin rejuvenation, wrinkle correction and volume augmentation."),
    ("REC_0886", "Indicated for restoring facial volume and redefining facial contours."),
    ("REC_0746", "Intended for modern liposuction procedures using Vibrasat Pro cannulas."),
    ("REC_0208", "Intended for treatment of vascular and pigmented lesions."),
    ("REC_0503", "Intended for non-invasive body contouring to reduce cellulite and volume while promoting tissue regeneration."),
    ("REC_0397", "Intended as a 3D aesthetic photography system for face consultation and pre-operative consultation workflows."),
    ("REC_0628", "Intended for subcutaneous injection of hyaluronic acid with lidocaine for temporary improvement of medium to severe nasolabial folds in adults via tissue restoration."),
    ("REC_0625_CELLUTRIX", "Indicated for edematous fibrosclerotic panniculopathy on the legs, buttocks, abdomen and arms."),
    ("REC_0627", "Indicated for heavy skin toning, tightening and hydration."),
    ("REC_0918", "Intended for strengthening, firming and toning the muscles of the abdomen, thighs and buttocks, including improvement of abdominal tone and strengthening of abdominal muscles."),
    ("REC_0679", "Indicated for prevention and treatment of abnormal and excessive scar formation, including scars resulting from general or cosmetic surgery."),
    ("REC_0681", "Intended for treatment of forehead lines and crow's feet with the STYLAGE S hyaluronic acid filler."),
    ("REC_0924", "Indicated for harvesting hair follicles from the scalp in men with androgenic alopecia and for assisting hair follicle extraction, recipient-site creation and implantation during hair transplantation."),
    ("REC_0925", "Indicated for suction-assisted follicular extraction and re-implantation in male and female patients."),
    ("REC_0922", "The SR515 and SR580 applicators are CE-marked for treatment of benign pigmented epidermal and cutaneous lesions and benign cutaneous vascular lesions."),
    ("REC_0743", "Cleared for non-invasive treatment of moderate to severe facial wrinkles and rhytides in females with Fitzpatrick skin types I-IV and for temporary reduction in the appearance of cellulite."),
    ("REC_0299", "Intended as an implantable hyaluronic acid body filler for body re-sculpting."),
    ("REC_0785", "Intended to temporarily reduce the appearance of cellulite and enhance body-shaping results."),
    ("REC_0745", "Intended for professional carboxytherapy treatments using the Venusian CO2 medical device."),
    ("REC_0756", "Indicated for improvement in the appearance of moderate to severe convexity or fullness associated with submental fat in adults."),
    ("REC_0372", "Intended to address sensitized skin following aesthetic procedures."),
    ("REC_0159", "Intended for treatment of the vaginal mucosa using the MonaLisa Touch DEKA-Pulse mode with controlled penetration depth and thermal effect."),
    ("REC_0584", "Intended for treatment of benign pigmented lesions and facial treatments using Discovery PICO handpieces."),
    ("REC_0581", "Intended for treatment of benign pigmented lesions and facial treatments using Discovery PICO handpieces."),
    ("REC_0254", "Intended for non-surgical body contouring and muscle stimulation treatments."),
    ("REC_0324", "Intended to correct moderate wrinkles and restore facial contours."),
    ("REC_0990", "Intended for skin renewal by addressing multiple skin layers and a broad range of skin concerns in a single laser session."),
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
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def has_indication(row: dict[str, str]) -> bool:
    return bool(clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")))


def make_row(product: dict[str, str], source: dict[str, str], indication: str, checked_at: str) -> dict[str, str]:
    product_id = clean(product.get("product_id"))
    source_url = clean(source.get("source_url"))
    return {
        "product_id": product_id,
        "seed_record_id": clean(product.get("seed_record_id")),
        "company_id": clean(product.get("company_id")),
        "company": clean(product.get("company")),
        "brand": clean(product.get("brand")),
        "jurisdiction": "Global",
        "regulator": "Official product/IFU/source text",
        "regulatory_pathway": "direct normalization of existing not-explicit-enough evidence",
        "status": "Official use/indication wording normalized from existing source evidence",
        "registration_no": "",
        "approval_date": "",
        "expiry_date": "",
        "registered_name": clean(product.get("registered_name") or product.get("standard_product_name") or product.get("brand")),
        "approved_indication": indication,
        "intended_use": indication,
        "legal_manufacturer": clean(product.get("legal_manufacturer") or product.get("manufactured_by") or product.get("company")),
        "local_holder": clean(product.get("local_holder")),
        "source_key": stable_id("egroup_direct_refined", product_id, source_url, indication),
        "source_url": source_url,
        "source_type": clean(source.get("source_type")) or "existing_candidate_source",
        "evidence_title": clean(source.get("evidence_title")) or f"{clean(product.get('company'))} {clean(product.get('brand'))}",
        "evidence_excerpt": clean(source.get("candidate_text"))[:1200],
        "official_description_exact": indication,
        "official_description_source_field": "direct_existing_text_normalization_20260601",
        "field_note": (
            "Directly normalized from an existing candidate text that already stated the product use/indication. "
            "Rows with vague marketing text, mismatched pages or incomplete wording were intentionally left for source reacquisition."
        ),
        "checked_at": checked_at,
        "reviewed_by": "auto_direct_not_explicit_batch_20260601",
        "review_status": "auto_refined_not_explicit_direct_existing_text",
        "confidence": "high_confidence_existing_text_direct_normalization",
    }


def main() -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, review_rows = read_csv(REVIEW_PACK)

    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}
    review_by_seed = {clean(row.get("seed_record_id")): row for row in review_rows if clean(row.get("seed_record_id"))}
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

    for seed, indication in DIRECT_REWRITES:
        product = product_by_seed.get(seed)
        source = review_by_seed.get(seed)
        if not product:
            skipped.append({"seed_record_id": seed, "reason": "active_product_not_found_or_excluded", "indication": indication})
            continue
        if not source:
            skipped.append({"seed_record_id": seed, "reason": "review_source_not_found", "indication": indication})
            continue
        if seed in existing_seed_with_indication:
            skipped.append({"seed_record_id": seed, "reason": "already_has_manual_indication", "indication": indication})
            continue
        row = make_row(product, source, indication, checked_at)
        key = (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact")),
        )
        if key in existing_keys:
            skipped.append({"seed_record_id": seed, "reason": "duplicate_exact_key", "indication": indication})
            continue
        existing_keys.add(key)
        existing_seed_with_indication.add(seed)
        new_rows.append(row)
        applied.append(
            {
                "seed_record_id": seed,
                "product_id": clean(row.get("product_id")),
                "company": clean(row.get("company")),
                "brand": clean(row.get("brand")),
                "indication": indication,
                "source_url": clean(row.get("source_url")),
            }
        )

    backup = ""
    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_not_explicit_direct_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        write_csv(MANUAL_INDICATION, manual_fields, [*manual_rows, *new_rows])
        backup = str(backup_path)

    write_csv(APPLIED_CSV, ["seed_record_id", "product_id", "company", "brand", "indication", "source_url"], applied)
    write_csv(SKIPPED_CSV, ["seed_record_id", "reason", "indication"], skipped)

    summary = {
        "checked_at": checked_at,
        "rewrite_candidates": len(DIRECT_REWRITES),
        "new_manual_indication_rows_added": len(new_rows),
        "skipped": len(skipped),
        "manual_backup": backup,
        "applied_csv": str(APPLIED_CSV),
        "skipped_csv": str(SKIPPED_CSV),
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
