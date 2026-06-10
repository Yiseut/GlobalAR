#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
from datetime import datetime

from apply_e_group_live_url_curated_batch_20260601 import (
    AUDIT_DIR,
    FIELDS,
    MANUAL_INDICATION,
    PRODUCT_MASTER,
    clean,
    has_indication,
    make_row,
    read_csv,
    write_csv,
)


SUMMARY_JSON = AUDIT_DIR / "e_group_exa_curated_batch_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_exa_curated_batch_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_exa_curated_batch_skipped_latest.csv"


CURATED_ROWS: list[dict[str, str]] = [
    {
        "seed_record_id": "REC_0105",
        "source_url": "https://suisselle.com/product/cellbooster-hair/",
        "indication": "Indicated as a resorbable injectable implant for prevention and treatment of scalp and hair problems such as hair loss, hair breakage, scalp dehydration, dandruff, and premature graying.",
    },
    {
        "seed_record_id": "REC_0115",
        "source_url": "https://biotecitaliauk.co.uk/cfu-elife/",
        "indication": "Indicated for treatment of skin ageing, reduction of wrinkle depth in the face and neck area, and reshaping of the body profile using high-intensity focused ultrasound.",
    },
    {
        "seed_record_id": "REC_0134",
        "source_url": "https://www.deleo-medical.com/en/cristal-fit/",
        "indication": "Indicated for treatment of urinary incontinence and strengthening of pelvic floor muscles.",
    },
    {
        "seed_record_id": "REC_0185",
        "source_url": "https://dermoaroma.com/peeling-system-radiance/",
        "indication": "Indicated for melasma and post-inflammatory hyperpigmentation.",
    },
    {
        "seed_record_id": "REC_0221",
        "source_url": "https://www.elementre-solutions.com/products/30-vitamin-c-brightening-serum",
        "indication": "Intended to brighten and energize the skin, protect against free radicals, and improve discoloration, fine lines, and wrinkles.",
    },
    {
        "seed_record_id": "REC_0274",
        "source_url": "https://medicalesthetics.biovico.com/product/flavya-excellence/",
        "indication": "Indicated for intradermal injection to improve skin hydration, elasticity, and density, protect cells against free radicals, revitalize cells, and support wound healing by initiating collagen and elastin synthesis.",
    },
    {
        "seed_record_id": "REC_0349",
        "source_url": "https://medytox.com/page/innotox_en?site_id=en",
        "indication": "Indicated to temporarily improve moderate to severe glabellar wrinkles related to corrugator and/or procerus muscle activity in adults aged 20 to 65.",
    },
    {
        "seed_record_id": "REC_0355",
        "source_url": "https://jalupro.fr/en/products/superhydro",
        "indication": "Indicated for photo-aging and anti-aging of the face and body, and for dry or dehydrated skin.",
    },
    {
        "seed_record_id": "REC_0384",
        "source_url": "https://fb-dermatology.com/en/healthcare-professional/kleresca/acne/faq/",
        "indication": "Indicated for treatment of acne.",
    },
    {
        "seed_record_id": "REC_0418",
        "source_url": "https://www.cynosure.com/product/ultra/",
        "indication": "Indicated for dermatological procedures requiring soft-tissue coagulation, treatment of actinic keratosis, and treatment of benign pigmented lesions including lentigos, solar lentigos, and ephelides.",
    },
    {
        "seed_record_id": "REC_0419",
        "source_url": "https://www.cynosure.com/product/genius/",
        "indication": "Intended for use in dermatologic and general surgical procedures for electrocoagulation and hemostasis.",
    },
    {
        "seed_record_id": "REC_0420",
        "source_url": "https://www.cynosure.com/product/hollywood-spectra/",
        "indication": "Intended for aesthetic, cosmetic, and surgical applications requiring incision, excision, ablation, or vaporization of soft tissues, and for coagulation and hemostasis in dermatology and general surgery.",
    },
    {
        "seed_record_id": "REC_0433",
        "source_url": "https://www.cynosure.com/product/medlite-c6/",
        "indication": "Indicated for treatment of multi-colored tattoos; the 532Lite handpiece is also used for small pigmented lesions requiring low fluences.",
    },
    {
        "seed_record_id": "REC_0521",
        "source_url": "https://inmodemd.in/workstation/optimasmax/",
        "indication": "Intended for dermatological applications requiring contraction or coagulation of soft tissue or hemostasis.",
    },
    {
        "seed_record_id": "REC_0736",
        "source_url": "https://alvi-prague.ae/cosmetic-lasers/vascular-laser/",
        "indication": "Indicated for vascular laser treatment of couperose, vascular nets and stars, rosacea in the telangiectatic stage, and other conditions involving dilated arterioles, capillaries, and venules.",
    },
    {
        "seed_record_id": "REC_0840",
        "source_url": "https://accessgudid.nlm.nih.gov/devices/07290019863359",
        "indication": "Indicated for temporary relief of minor muscle aches and pain, temporary relief of muscle spasms, and temporary improvement of local blood circulation.",
    },
    {
        "seed_record_id": "REC_0845",
        "source_url": "https://inmodemd.in/workstation/igniterf/",
        "indication": "Indicated for procedures requiring soft tissue contraction, electrocoagulation, hemostasis, and fractional treatments requiring penetration levels up to 60 mm.",
    },
    {
        "seed_record_id": "REC_0864",
        "source_url": "https://marketing.candelamedical.com/rs/620-HCU-218/images/PB83217EN-CN_APAC_VelaShapeIII_Brochure_LRPDF_2019.pdf",
        "indication": "Indicated for non-invasive body contouring through temporary cellulite and circumference reduction.",
    },
    {
        "seed_record_id": "REC_0891",
        "source_url": "https://www.ibsa-pharma.de/produkte/aliaxin-gp.html",
        "indication": "Indicated for marionette lines, nasolabial folds, glabellar lines, local volume restoration, and refresh treatments.",
    },
    {
        "seed_record_id": "REC_0910",
        "source_url": "https://www.quantasystem.com/us/laser/chrome/",
        "indication": "Intended for multiple dermatology and aesthetic laser treatments, including wrinkles, benign pigmented lesions, multicolor tattoo removal, acne scars, and hair removal depending on the selected module.",
    },
    {
        "seed_record_id": "REC_0915",
        "source_url": "https://eclassys.com/product/aquapure/",
        "indication": "Indicated to improve skin tone, texture, and elasticity and to treat uneven skin tone, sun damage or hyperpigmentation, dehydrated skin, oily and acne-prone skin, fine lines, and wrinkles.",
    },
    {
        "seed_record_id": "REC_0989",
        "source_url": "https://sciton.com/bbl-heroic/",
        "indication": "Indicated for telangiectasia, poikiloderma, cherry angiomas, and low-contrast recalcitrant pigmented lesions including seborrheic keratoses.",
    },
    {
        "seed_record_id": "REC_1046",
        "source_url": "https://www.accessdata.fda.gov/cdrh_docs/pdf24/K241918.pdf",
        "indication": "Indicated for breast reconstruction after mastectomy, correction of an underdeveloped breast, scar revision, and tissue defect procedures; intended for temporary subcutaneous or submuscular implantation not beyond six months.",
    },
    {
        "seed_record_id": "TOPLINE_ALLERGAN_JUVEDERM_ULTRA_XC_20260530",
        "source_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P050047S044",
        "indication": "Indicated for injection into the mid-to-deep dermis for correction of moderate to severe facial wrinkles and folds, such as nasolabial folds, and for injection into the lips and perioral area for lip augmentation in adults over 21.",
    },
    {
        "seed_record_id": "TOPLINE_ALLERGAN_JUVEDERM_VOLBELLA_20260530",
        "source_url": "https://www.fda.gov/medical-devices/recently-approved-devices/juvedermr-volbellar-xc-p110033-s053",
        "indication": "Approved for injection into the lips and skin around the lips to temporarily restore volume and fullness, and for use in the infraorbital hollow area under the eyes in adults over 21.",
    },
    {
        "seed_record_id": "TOPLINE_ALLERGAN_JUVEDERM_VOLLURE_20260530",
        "source_url": "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?id=P110033S020",
        "indication": "Indicated for injection into the mid-to-deep dermis for correction of moderate to severe facial wrinkles and folds, such as nasolabial folds, in adults over 21.",
    },
    {
        "seed_record_id": "TOPLINE_GALDERMA_RESTYLANE_KYSSE_20260530",
        "source_url": "https://www.galderma.com/us/sites/default/files/2020-04/Restylane_Kysse-IFU.pdf",
        "indication": "Indicated for injection into the lips for lip augmentation and correction of upper perioral rhytids in patients over 21.",
    },
    {
        "seed_record_id": "TOPLINE_GALDERMA_RESTYLANE_LYFT_20260530",
        "source_url": "https://www.galderma.com/us/sites/default/files/2023-06/Restylane_Lyft_e-IFU_USA.pdf",
        "indication": "Indicated for correction of moderate to severe facial folds and wrinkles such as nasolabial folds, cheek augmentation and correction of age-related midface contour deficiencies, and correction of dorsal hand volume deficit in patients over 21.",
    },
    {
        "seed_record_id": "TOPLINE_GALDERMA_RESTYLANE_REFYNE_20260530",
        "source_url": "https://www.galderma.com/us/sites/default/files/2023-06/Restylane_Refyne_e-IFU_USA.pdf",
        "indication": "Indicated for injection into the mid-to-deep dermis for correction of moderate to severe facial wrinkles and folds, such as nasolabial folds, in patients over 21.",
    },
]


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
        row["source_type"] = "exa_official_or_regulatory_source_curated"
        row["regulatory_pathway"] = "Exa API official/regulatory source extraction"
        row["reviewed_by"] = "auto_exa_curated_batch_20260601"
        row["review_status"] = "auto_promoted_exa_source_curated"
        row["confidence"] = "high_confidence_exa_source_curated"
        row["field_note"] = "Curated from Exa API search results and direct official/regulatory source verification; distributor, competitor-keyword, and wrong-product matches were excluded."
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

    backup_path = None
    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_exa_curated_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        output_fields = manual_fields or list(FIELDS)
        for field in FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, manual_rows + new_rows)

    write_csv(
        APPLIED_CSV,
        ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "source_url", "indication"],
        applied,
    )
    write_csv(SKIPPED_CSV, ["seed_record_id", "source_url", "indication", "reason"], skipped)
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
