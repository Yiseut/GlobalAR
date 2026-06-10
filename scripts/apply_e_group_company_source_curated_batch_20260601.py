#!/usr/bin/env python3
from __future__ import annotations

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

import csv
import json
import shutil
from datetime import datetime
from pathlib import Path


SUMMARY_JSON = AUDIT_DIR / "e_group_company_source_curated_batch_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_company_source_curated_batch_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_company_source_curated_batch_skipped_latest.csv"


CURATED_ROWS = [
    {
        "seed_record_id": "REC_0053",
        "source_url": "https://asclepion.com/en/quadrostarpro_en/",
        "indication": "Indicated for treatment of superficial vessels and pigmented lesions.",
    },
    {
        "seed_record_id": "REC_0187",
        "source_url": "https://desirial.com/en/comfort-intimate-women-vivacy/",
        "indication": "Indicated for rehydration of vaginal and vestibular mucous membranes and slight hypotrophy of the vulvar labia majora and pubis by intradermal injections.",
    },
    {
        "seed_record_id": "REC_0360",
        "source_url": "https://www.linearz.co.kr/en/common/marketing.php",
        "indication": "Intended to use focused ultrasound to coagulate tissue for eyebrow lifting and thigh skin elasticity improvement.",
    },
    {
        "seed_record_id": "REC_0495",
        "source_url": "https://www.nithya.it/en/questions/",
        "indication": "Indicated for correction of blemishes related to ageing and for maintaining skin elasticity; may be used on the face, décolleté, neck, hands, arms and body at a physician's discretion.",
    },
    {
        "seed_record_id": "REC_0226",
        "source_url": "https://daltonmedical.nl/wp-content/uploads/2024/11/Emface_LF_One-sheeter_FA_EN102_preview.pdf",
        "indication": "Intended for aesthetic facial rejuvenation and contouring through wrinkle reduction and skin-laxity improvement by toning and lifting muscles and skin.",
    },
    {
        "seed_record_id": "REC_0228",
        "source_url": "https://rtaesthetics.co.uk/wp-content/uploads/2023/07/Emsculpt_Neo_CLIN_Mechanism-of-action-paper_EN101_preview.pdf",
        "indication": "Intended for treatment of obesity by fat reduction through neuromuscular stimulation, radiofrequency-induced lipolysis and increased blood flow.",
    },
    {
        "seed_record_id": "REC_0118",
        "source_url": "https://sinclair.com/brands/energy-devices/cooltech-define/",
        "indication": "Intended for treatment of localized adipose accumulations in patients with BMI greater than or equal to 30 through controlled cooling and adipose tissue reduction.",
    },
    {
        "seed_record_id": "REC_0168",
        "source_url": "https://www.mesoestetic.co.za/professional/dermamelan-intimate-pack.html",
        "indication": "Indicated for the external intimate area, inner thighs and groin to reduce pigmentary imperfections and improve skin quality, elasticity and appearance.",
    },
    {
        "seed_record_id": "REC_0442",
        "source_url": "https://www.mesoestetic-me.com/en/professional/mesohyal-nctc109.html",
        "indication": "Indicated as an intensive biorevitalization treatment for fine wrinkles, dull skin, anti-aging care and toning of skin tissue.",
    },
    {
        "seed_record_id": "REC_0616",
        "source_url": "https://inmodemd.com/workstation/workstation-bodytite",
        "indication": "Indicated for treatment of large body areas through soft tissue coagulation.",
    },
    {
        "seed_record_id": "REC_0770",
        "source_url": "https://dermaroller.com/medical-microneedling/medical-indications/",
        "indication": "Indicated for treatment of scars, especially acne scars, injury scars, burn scars and stretch marks.",
    },
    {
        "seed_record_id": "REC_0861",
        "source_url": "https://marketing.candelamedical.com/ANZ-Q2-Profound-Matrix-Technical-Bulletin_LP.html",
        "indication": "Indicated for general dermatological procedures for electrocoagulation and hemostasis.",
    },
    {
        "seed_record_id": "REC_0954",
        "source_url": "https://endymed.com/tc-applicators/",
        "indication": "Indicated for treatment of wrinkles and lax skin on the face, jawline and neck, including thin skin around the eyes and mouth.",
    },
    {
        "seed_record_id": "REC_1011",
        "source_url": "https://www.jeisys-us.com/edgeone",
        "indication": "Indicated for incision, excision, ablation, vaporization and coagulation of body soft tissues; with the scanning unit, indicated for ablative skin resurfacing.",
    },
    {
        "seed_record_id": "REC_0919",
        "source_url": "https://www.venusconcept.com/en-ie/aesthetic-devices.htm",
        "indication": "Indicated for treatment of benign pigmented epidermal and cutaneous lesions and benign cutaneous vascular lesions.",
    },
    {
        "seed_record_id": "REC_0255",
        "source_url": "https://evolysse.evolus.com/evolysse-difference",
        "indication": "Intended for dynamic wrinkles and folds such as nasolabial folds.",
    },
    {
        "seed_record_id": "REC_0762",
        "source_url": "https://www.med.wiqo.com/en/15890/prx-t33",
        "indication": "Indicated as a skin beautifier for face and body and for treatment of scars, stretch marks and prevention of dermal ageing.",
    },
]


def main() -> None:
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

    applied = []
    skipped = []
    new_rows = []
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
        row["source_type"] = "company_official_source_evidence_curated"
        row["regulatory_pathway"] = "curated company official source pool extraction"
        row["reviewed_by"] = "auto_company_source_curated_batch_20260601"
        row["review_status"] = "auto_promoted_company_source_curated"
        row["confidence"] = "high_confidence_company_source_curated"
        row["field_note"] = "Curated from company official source pool after rejecting broad same-company pages and wrong-product matches."
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
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_company_source_curated_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        output_fields = manual_fields or FIELDS
        for field in FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, manual_rows + new_rows)
    else:
        backup_path = None

    write_csv(APPLIED_CSV, ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "source_url", "indication"], applied)
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
