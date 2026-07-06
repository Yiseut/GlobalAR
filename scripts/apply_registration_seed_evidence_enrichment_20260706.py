#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
REGISTRATION_PATH = DATA_DIR / "registration_evidence.csv"
MANUAL_OFFICIAL_PATH = DATA_DIR / "manual_official_indication_evidence.csv"

CHECKED_AT = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
RUN_ID = "codex_registration_seed_enrichment_20260706"

HYDRAFACIAL_SOURCE_URL = (
    "https://api.fda.gov/device/registrationlisting.json"
    "?search=proprietary_name:%22HYDRAFACIAL%22&limit=10"
)

UPDATES = {
    ("REC_0334", "US"): {
        "regulator": "FDA",
        "regulatory_pathway": "Establishment Registration & Device Listing",
        "status": "Listed; active establishment registration through 2026",
        "registration_no": "3016453096",
        "registered_name": "HydraFacial Syndeo / HydraFacial MD Elite / HydraFacial Elite",
        "approved_indication": "",
        "intended_use": "Powered dermabrasion brush; product code GFE; 21 CFR 878.4820; Class I.",
        "legal_manufacturer": "HydraFacial LLC",
        "local_holder": "HydraFacial LLC",
        "source_key": "official_fda_registrationlisting_hydrafacial_20260706",
        "source_url": HYDRAFACIAL_SOURCE_URL,
        "source_type": "official_api",
        "evidence_title": "openFDA device registration and listing - HydraFacial LLC",
        "evidence_excerpt": (
            "openFDA registration/listing record identifies HydraFacial LLC registration number "
            "3016453096, owner-operator 9032809, proprietary names including HydraFacial "
            "Syndeo and HydraFacial MD Elite, and product code GFE for Brush, Dermabrasion, Powered."
        ),
        "official_description_exact": "Brush, Dermabrasion, Powered; product code GFE; 21 CFR 878.4820; Class I.",
        "official_description_source_field": "openfda.device_name/product_code/regulation_number/device_class",
        "field_note": (
            "Resolved from FDA establishment registration and device listing evidence. This is a "
            "device listing/registration record, not a 510(k) clearance."
        ),
    }
}

REASON_BY_JURISDICTION = {
    "EU": "No public CE certificate, EU/NCA authorisation number, or jurisdiction-matched official wording confirmed in this pass.",
    "KR": "No public MFDS permit number and exact jurisdiction-matched official wording confirmed in this pass.",
    "CN": "No public NMPA registration number or jurisdiction-matched official wording confirmed in this pass.",
    "US": "No public FDA clearance/listing number or jurisdiction-matched official wording confirmed in this pass.",
}

SPECIFIC_REASONS = {
    ("REC_0044", "US"): (
        "FDA warning-letter evidence discusses AQUAGOLD fine touch listing/product code GAA, "
        "but no exact FDA establishment registration/listing number or 510(k) number was confirmed."
    ),
    ("REC_0453", "US"): (
        "FDA warning-letter evidence says the A.S.A.P. Micro Infusion System was not listed; "
        "no exact FDA listing or clearance number was confirmed for the seed row."
    ),
    ("TOPLINE_MEDYTOX_NEWLUX_20260530", "KR"): (
        "Medytox official product page confirms NEWLUX indication and points to MFDS, "
        "but no public MFDS permit number was confirmed."
    ),
}

SOURCES_USED = [
    {
        "label": "openFDA device registrationlisting API - HydraFacial search",
        "url": HYDRAFACIAL_SOURCE_URL,
    },
    {
        "label": "FDA warning letter - Aquavit Pharmaceuticals, Inc. 607150",
        "url": "https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters/aquavit-pharmaceuticals-inc-607150-06172021",
    },
    {
        "label": "Medytox official NEWLUX product page",
        "url": "https://medytox.com/page/newlux?site_id=en",
    },
]


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def main() -> int:
    registration_fields, seed_rows = read_rows(REGISTRATION_PATH)
    manual_fields, manual_rows = read_rows(MANUAL_OFFICIAL_PATH)
    fields = manual_fields or [
        field for field in registration_fields if field not in {"fda_product_code", "fda_regulation_number", "fda_device_class", "fda_submission_type", "original_approval_date"}
    ]

    backup = MANUAL_OFFICIAL_PATH.with_name(
        f"manual_official_indication_evidence.backup_before_seed_enrichment_20260706_{datetime.now().strftime('%H%M%S')}.csv"
    )
    shutil.copy2(MANUAL_OFFICIAL_PATH, backup)

    updated_manual_rows = list(manual_rows)
    resolved = []
    target_rows = []
    for seed_row in seed_rows:
        if seed_row.get("review_status") == "needs_review" and seed_row.get("source_type") == "seed_workbook":
            target_rows.append(seed_row)
        key = (seed_row.get("seed_record_id", "").strip(), seed_row.get("jurisdiction", "").strip())
        update = UPDATES.get(key)
        if not update:
            continue
        if seed_row.get("review_status") != "needs_review" or seed_row.get("source_type") != "seed_workbook":
            continue
        row = {field: seed_row.get(field, "") for field in fields}
        row.update(update)
        row["checked_at"] = CHECKED_AT
        row["reviewed_by"] = RUN_ID
        row["review_status"] = "official_record_confirmed"
        row["confidence"] = "official_record_confirmed"

        replaced = False
        for index, existing in enumerate(updated_manual_rows):
            existing_key = (existing.get("seed_record_id", "").strip(), existing.get("jurisdiction", "").strip())
            if existing_key == key and existing.get("source_key", "").strip() == row["source_key"]:
                updated_manual_rows[index] = row
                replaced = True
                break
        if not replaced:
            updated_manual_rows.append(row)
        resolved.append(
            {
                "seed_record_id": row["seed_record_id"],
                "company": row["company"],
                "brand": row["brand"],
                "jurisdiction": row["jurisdiction"],
                "registration_no": row["registration_no"],
                "source_url": row["source_url"],
                "description": row["official_description_exact"],
            }
        )

    write_rows(MANUAL_OFFICIAL_PATH, fields, updated_manual_rows)

    resolved_keys = set(UPDATES)
    remaining = []
    for row in target_rows:
        key = (row.get("seed_record_id", "").strip(), row.get("jurisdiction", "").strip())
        if key in resolved_keys:
            continue
        jurisdiction = row.get("jurisdiction", "").strip()
        remaining.append(
            {
                "seed_record_id": row.get("seed_record_id", ""),
                "company": row.get("company", ""),
                "brand": row.get("brand", ""),
                "jurisdiction": jurisdiction,
                "reason": SPECIFIC_REASONS.get(
                    key,
                    REASON_BY_JURISDICTION.get(
                        jurisdiction,
                        "No official registration number and exact jurisdiction-matched official wording confirmed in this pass.",
                    ),
                ),
            }
        )

    summary = {
        "generated_at": CHECKED_AT,
        "reviewed_by": RUN_ID,
        "source_csv_backup": str(backup.relative_to(PROJECT_DIR)),
        "resolved_count": len(resolved),
        "remaining_count": len(remaining),
        "resolved_rows": resolved,
        "remaining_rows": remaining,
        "unresolved_reason_counts": dict(Counter(item["reason"] for item in remaining)),
        "sources_used": SOURCES_USED,
        "durable_input_updated": str(MANUAL_OFFICIAL_PATH.relative_to(PROJECT_DIR)),
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    dated = AUDIT_DIR / "registration_seed_evidence_enrichment_20260706.json"
    latest = AUDIT_DIR / "registration_seed_evidence_enrichment_latest.json"
    for path in (dated, latest):
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
