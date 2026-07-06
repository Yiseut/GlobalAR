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


OFFICIAL_NOTE = (
    "Resolved from official regulator/product-document evidence during registration seed evidence enrichment; "
    "jurisdiction is represented by the cited EU/EEA/UK medicines authorisation record."
)


UPDATES = {
    ("REC_0387", "EU"): {
        "regulator": "European Commission / Notified Body",
        "regulatory_pathway": "Decentralised Procedure",
        "status": "Marketing authorisation confirmed",
        "registration_no": "SE/H/1547/001",
        "approval_date": "2016-10-05",
        "registered_name": "Belkyra 10 mg/ml solution for injection",
        "approved_indication": (
            "Belkyra is used for the treatment of submental fat (unwanted fat under the chin) "
            "when its presence has a psychological impact for the patient."
        ),
        "intended_use": (
            "Treatment of submental fat (unwanted fat under the chin) when its presence has "
            "a psychological impact for the patient."
        ),
        "local_holder": "Allergan Pharmaceutical International Limited",
        "source_key": "official_mpa_belkyra_spar_20260629",
        "source_url": "https://docetp.mpa.se/LMF/Belkyra%20solution%20for%20injection%20ENG%20sPAR_09001bee807a0b0b.pdf",
        "source_type": "official_regulator_record",
        "evidence_title": "Swedish MPA Summary Public Assessment Report - Belkyra",
        "evidence_excerpt": (
            "Swedish MPA Summary PAR identifies Belkyra, procedure SE/H/1547/01/DC, use for "
            "submental fat, and Swedish marketing authorisation granted on 2016-10-05."
        ),
    },
    ("REC_0094", "EU"): {
        "regulator": "European Commission / Notified Body",
        "regulatory_pathway": "Mutual Recognition / National marketing authorisation",
        "status": "Marketing authorisation confirmed",
        "registration_no": "FR/H/0230/001; PA1824/020/001",
        "registered_name": "VISTABEL, 4 Allergan Units/0.1 ml, Powder for solution for injection",
        "approved_indication": (
            "Temporary improvement in the appearance of facial lines, including glabellar, "
            "crow's feet and forehead lines, when the severity has an important psychological impact."
        ),
        "intended_use": (
            "Temporary improvement in the appearance of moderate to severe upper facial lines "
            "in adult patients when the severity has an important psychological impact."
        ),
        "legal_manufacturer": "AbbVie / Allergan",
        "local_holder": "AbbVie Limited",
        "source_key": "official_hpra_vistabel_licence_20260629",
        "source_url": "https://www.medicines.ie/medicines/vistabel-4-allergan-units-0-1-ml-powder-for-solution-for-injection-34207/license-info",
        "source_type": "official_product_page",
        "evidence_title": "HPRA medicines.ie licence info - VISTABEL",
        "evidence_excerpt": (
            "HPRA medicines.ie product page lists VISTABEL with licence PA1824/020/001; "
            "EMA nationally authorised-products list identifies procedure FR/H/0230/001."
        ),
    },
    ("REC_0211", "EU"): {
        "regulator": "European Commission / Notified Body",
        "regulatory_pathway": "Mutual Recognition / National marketing authorisation",
        "status": "Marketing authorisation confirmed",
        "registration_no": "FR/H/0341/001; PL 06958/0031",
        "approval_date": "2009-02-26",
        "registered_name": "Azzalure, 125 Speywood units, powder for solution for injection",
        "approved_indication": (
            "Azzalure is indicated for the temporary improvement in the appearance of moderate "
            "to severe glabellar lines and/or lateral canthal lines in adult patients under 65 years, "
            "when the severity has an important psychological impact."
        ),
        "intended_use": (
            "Temporary improvement in the appearance of moderate to severe glabellar lines and/or "
            "lateral canthal lines in adult patients under 65 years."
        ),
        "legal_manufacturer": "Ipsen / Galderma",
        "local_holder": "Ipsen Ltd / Galderma (U.K.) Limited",
        "source_key": "official_emc_azzalure_smpc_20260629",
        "source_url": "https://www.medicines.org.uk/emc/product/6584/smpc",
        "source_type": "official_product_smpc",
        "evidence_title": "eMC SmPC - Azzalure 125 Speywood units",
        "evidence_excerpt": (
            "eMC SmPC lists Azzalure PL 06958/0031 and first authorisation 2009-02-26; "
            "EMA nationally authorised-products list identifies procedure FR/H/0341/001."
        ),
    },
    ("REC_0772", "EU"): {
        "regulator": "European Commission / Notified Body",
        "regulatory_pathway": "National marketing authorisation",
        "status": "Marketing authorisation confirmed",
        "registration_no": "PL 29978/0002; PL 29978/0005",
        "approval_date": "2010-06-29",
        "registered_name": "BOCOUTURE 50 units / 100 units powder for solution for injection",
        "approved_indication": (
            "BOCOUTURE is indicated for the temporary improvement in the appearance of upper "
            "facial lines in adults below 65 years when the severity has an important psychological impact."
        ),
        "intended_use": (
            "Temporary improvement in the appearance of upper facial lines in adults below 65 years."
        ),
        "legal_manufacturer": "Merz Pharmaceuticals GmbH",
        "local_holder": "Merz Aesthetics UK Ltd",
        "source_key": "official_emc_bocouture_smpc_20260629",
        "source_url": "https://www.medicines.org.uk/emc/product/600/smpc",
        "source_type": "official_product_smpc",
        "evidence_title": "eMC SmPC - BOCOUTURE 50/100 units",
        "evidence_excerpt": (
            "eMC SmPC lists BOCOUTURE marketing authorisation numbers PL 29978/0002 and "
            "PL 29978/0005, with 50-unit first authorisation on 2010-06-29."
        ),
    },
    ("REC_0395", "EU"): {
        "regulator": "European Commission / Notified Body",
        "regulatory_pathway": "National marketing authorisation",
        "status": "Marketing authorisation confirmed",
        "registration_no": "PL 29863/0002",
        "approval_date": "2022-03-22",
        "registered_name": "Letybo 50 units powder for solution for injection",
        "approved_indication": (
            "Letybo is indicated for the temporary improvement in the appearance of moderate "
            "to severe vertical lines between the eyebrows in adults <75 years old seen at maximum frown, "
            "when the severity has an important psychological impact."
        ),
        "intended_use": (
            "Temporary improvement in the appearance of moderate to severe vertical lines between "
            "the eyebrows in adults under 75 years old."
        ),
        "legal_manufacturer": "Hugel / CROMA-PHARMA GmbH",
        "local_holder": "CROMA-PHARMA GmbH",
        "source_key": "official_emc_letybo_smpc_20260629",
        "source_url": "https://www.medicines.org.uk/emc/product/13707/smpc",
        "source_type": "official_product_smpc",
        "evidence_title": "eMC SmPC - Letybo 50 units",
        "evidence_excerpt": (
            "eMC SmPC lists Letybo PL 29863/0002, first authorisation 2022-03-22, "
            "and the glabellar-lines indication."
        ),
    },
}


REASON_BY_JURISDICTION = {
    "EU": "No public CE certificate, EU/NCA authorisation number, or jurisdiction-matched official wording confirmed in this pass.",
    "KR": "No public MFDS permit number and exact jurisdiction-matched official wording confirmed in this pass.",
    "CN": "No public NMPA registration number or jurisdiction-matched official wording confirmed in this pass.",
    "US": "No public FDA clearance/listing number or jurisdiction-matched official wording confirmed in this pass.",
}


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
    fields, seed_rows = read_rows(REGISTRATION_PATH)
    manual_fields, manual_rows = read_rows(MANUAL_OFFICIAL_PATH)
    if manual_fields:
        fields = manual_fields
    backup = MANUAL_OFFICIAL_PATH.with_name(
        f"manual_official_indication_evidence.backup_before_seed_enrichment_20260629_{datetime.now().strftime('%H%M%S')}.csv"
    )
    shutil.copy2(MANUAL_OFFICIAL_PATH, backup)

    updated_manual_rows = list(manual_rows)
    resolved = []
    for seed_row in seed_rows:
        key = (seed_row.get("seed_record_id", "").strip(), seed_row.get("jurisdiction", "").strip())
        update = UPDATES.get(key)
        if not update:
            continue
        if seed_row.get("review_status") != "needs_review" or seed_row.get("source_type") != "seed_workbook":
            continue
        row = {field: seed_row.get(field, "") for field in fields}
        row.update(update)
        row["official_description_exact"] = update["approved_indication"]
        row["official_description_source_field"] = "approved_indication"
        row["field_note"] = OFFICIAL_NOTE
        row["checked_at"] = CHECKED_AT
        row["reviewed_by"] = "codex_registration_seed_enrichment_20260629"
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
            }
        )

    write_rows(MANUAL_OFFICIAL_PATH, fields, updated_manual_rows)

    remaining = []
    resolved_keys = set(UPDATES)
    for row in seed_rows:
        key = (row.get("seed_record_id", "").strip(), row.get("jurisdiction", "").strip())
        if key in resolved_keys:
            continue
        if row.get("review_status") == "needs_review" and row.get("source_type") == "seed_workbook":
            jurisdiction = row.get("jurisdiction", "").strip()
            remaining.append(
                {
                    "seed_record_id": row.get("seed_record_id", ""),
                    "company": row.get("company", ""),
                    "brand": row.get("brand", ""),
                    "jurisdiction": jurisdiction,
                    "reason": REASON_BY_JURISDICTION.get(
                        jurisdiction,
                        "No official registration number and exact jurisdiction-matched official wording confirmed in this pass.",
                    ),
                }
            )

    sources_used = [
        {
            "label": "Swedish MPA Belkyra Summary PAR",
            "url": "https://docetp.mpa.se/LMF/Belkyra%20solution%20for%20injection%20ENG%20sPAR_09001bee807a0b0b.pdf",
        },
        {
            "label": "EMA deoxycholic acid nationally authorised products list",
            "url": "https://www.ema.europa.eu/en/documents/psusa/deoxycholic-acid-list-nationally-authorised-medicinal-products-psusa00010525202104_en.pdf",
        },
        {
            "label": "EMA botulinum toxin A nationally authorised products list",
            "url": "https://www.ema.europa.eu/en/documents/psusa/botulinum-toxin-except-centrally-authorised-products-list-nationally-authorised-products-psusa-00000426-202412_en.pdf",
        },
        {
            "label": "HPRA medicines.ie VISTABEL licence info",
            "url": "https://www.medicines.ie/medicines/vistabel-4-allergan-units-0-1-ml-powder-for-solution-for-injection-34207/license-info",
        },
        {
            "label": "eMC Azzalure SmPC",
            "url": "https://www.medicines.org.uk/emc/product/6584/smpc",
        },
        {
            "label": "eMC Bocouture SmPC",
            "url": "https://www.medicines.org.uk/emc/product/600/smpc",
        },
        {
            "label": "eMC Letybo SmPC",
            "url": "https://www.medicines.org.uk/emc/product/13707/smpc",
        },
    ]
    summary = {
        "generated_at": CHECKED_AT,
        "reviewed_by": "codex_registration_seed_enrichment_20260629",
        "source_csv_backup": str(backup.relative_to(PROJECT_DIR)),
        "resolved_count": len(resolved),
        "remaining_count": len(remaining),
        "resolved_rows": resolved,
        "remaining_rows": remaining,
        "unresolved_reason_counts": dict(Counter(item["reason"] for item in remaining)),
        "sources_used": sources_used,
        "durable_input_updated": str(MANUAL_OFFICIAL_PATH.relative_to(PROJECT_DIR)),
    }
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    dated = AUDIT_DIR / "registration_seed_evidence_enrichment_20260629.json"
    latest = AUDIT_DIR / "registration_seed_evidence_enrichment_latest.json"
    for path in (dated, latest):
        path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
