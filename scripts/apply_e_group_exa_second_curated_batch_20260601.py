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


SUMMARY_JSON = AUDIT_DIR / "e_group_exa_second_curated_batch_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_exa_second_curated_batch_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_exa_second_curated_batch_skipped_latest.csv"


CURATED_ROWS: list[dict[str, str]] = [
    {
        "seed_record_id": "REC_0029",
        "source_url": "https://almainc.com/product/alma-ted/",
        "indication": "Intended for non-invasive hair restoration support through ultrasound-based trans-epidermal delivery, with clinical use focused on improvement of hair density and hair regrowth.",
    },
    {
        "seed_record_id": "REC_0281",
        "source_url": "https://www.fotona.com/en/campaigns/6235/starwalker-r-maqx-the-best-tool-for-pigmented-lesions/",
        "indication": "Intended for treatment of pigmented lesions, including challenging indications such as melasma, and for tattoo removal applications.",
    },
    {
        "seed_record_id": "REC_0361",
        "source_url": "https://www.jeisys-us.com/density",
        "indication": "Cleared for dermatologic and general surgical procedures.",
    },
    {
        "seed_record_id": "REC_0432",
        "source_url": "https://accessgudid.nlm.nih.gov/devices/04058784000279",
        "indication": "Intended for hair removal, permanent hair reduction, and treatment of benign pigmented and vascular lesions.",
    },
    {
        "seed_record_id": "REC_0623",
        "source_url": "https://www.skintechpharmagroup.com/new-rrs-ha-long-lasting-2/",
        "indication": "Indicated for treatment of skin photoaging and its consequences, dermal atrophy, soft filling of skin depressions and wrinkles, and restoration of skin hydration.",
    },
    {
        "seed_record_id": "REC_0739",
        "source_url": "https://www.canfieldscientific.com/imaging-systems/vectra-xt-3d-imaging-system/",
        "indication": "Intended for three-dimensional imaging, simulation, and assessment of breast asymmetry, including visualization of volume differences and implant parameter adjustments.",
    },
    {
        "seed_record_id": "REC_0742",
        "source_url": "https://www.veinlite.com/dfu/led-plus/index.html",
        "indication": "Indicated for improved visualization of veins in geriatric patients, patients with different pigmented skin types, patients with difficult venous access, and pediatric or adult venous access.",
    },
    {
        "seed_record_id": "REC_0748",
        "source_url": "https://sinclair.com/media/dfjgkkdw/reaction-safetyandperformaceinformation-2025.pdf",
        "indication": "Indicated for temporary reduction of cellulite and body contouring through temporary circumference reduction.",
    },
    {
        "seed_record_id": "REC_0902",
        "source_url": "https://asclepion.com/en/mediostar_en/",
        "indication": "Intended for hair removal and treatment of benign vascular and pigmented lesions.",
    },
    {
        "seed_record_id": "REC_0940",
        "source_url": "https://www.accessdata.fda.gov/cdrh_docs/pdf24/K241144.pdf",
        "indication": "Indicated for tattoo removal at 1064 nm and 532 nm for specified Fitzpatrick skin types and tattoo colors, and for treatment of benign pigmented lesions for Fitzpatrick skin types I-IV.",
    },
    {
        "seed_record_id": "TOPLINE_SINCLAIR_LANLUMA_20260530",
        "source_url": "https://sinclair.com/uk/brands/injectables-and-threads/lanluma/",
        "indication": "Indicated as a poly-L-lactic acid implant suitable for increasing the volume of depressed areas, particularly to correct skin depressions.",
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
        row["source_type"] = "exa_second_pass_official_source_curated"
        row["regulatory_pathway"] = "Exa API second-pass official/regulatory source extraction"
        row["reviewed_by"] = "auto_exa_second_curated_batch_20260601"
        row["review_status"] = "auto_promoted_exa_second_source_curated"
        row["confidence"] = "high_confidence_exa_second_source_curated"
        row["field_note"] = "Second-pass Exa API candidate promoted only after source/product alignment checks; reseller-only and wrong-product candidates were left in the reacquisition queue."
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
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_exa_second_curated_{stamp}.csv"
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
