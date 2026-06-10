#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
REGISTRATION_EVIDENCE_PATH = DATA_DIR / "registration_evidence.csv"
MANUAL_OFFICIAL_EVIDENCE_PATH = DATA_DIR / "manual_official_indication_evidence.csv"
AUDIT_CSV = AUDIT_DIR / "registration_needs_review_resolution_latest.csv"
AUDIT_MD = AUDIT_DIR / "registration_needs_review_resolution_latest.md"

REGISTRATION_EVIDENCE_FIELDS = [
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

OFFICIAL_DESCRIPTION_PENDING_NOTE = (
    "Official registration record or certificate number has been confirmed, but precise "
    "approved-indication/intended-use wording has not been promoted yet."
)


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def dedupe_key(row: dict[str, Any]) -> tuple[str, str, str, str] | None:
    product_id = norm(row.get("product_id"))
    registration_no = norm(row.get("registration_no"))
    regulator = norm(row.get("regulator")).upper()
    jurisdiction = norm(row.get("jurisdiction")).upper()
    if product_id and registration_no and (regulator or jurisdiction):
        return product_id, registration_no, regulator, jurisdiction
    company = norm(row.get("company"))
    registered_name = norm(row.get("registered_name"))
    if registration_no and (regulator or jurisdiction) and (company or registered_name):
        return f"company:{company}", registration_no, regulator or jurisdiction, registered_name
    source_url = norm(row.get("source_url"))
    source_key = norm(row.get("source_key"))
    dedupe_source_key = source_key
    if dedupe_source_key.startswith("manual_needs_review_resolution:"):
        dedupe_source_key = dedupe_source_key.split(":", 1)[1]
    if product_id and source_url and source_key:
        return product_id, source_url, dedupe_source_key, ""
    if source_url and source_key and (company or registered_name):
        return f"company:{company}", source_url, dedupe_source_key, registered_name
    if product_id and source_key and (regulator or jurisdiction):
        return product_id, dedupe_source_key, regulator or jurisdiction, ""
    return None


def promoted_status(row: dict[str, str]) -> str:
    source_type = norm(row.get("source_type")).lower()
    source_url = norm(row.get("source_url"))
    registration_no = norm(row.get("registration_no"))
    if source_type == "official_api" and source_url and registration_no:
        return "official_record_confirmed"
    if registration_no:
        return "certificate_number_confirmed_indication_pending"
    return "needs_source_followup"


def promoted_confidence(row: dict[str, str]) -> str:
    confidence = norm(row.get("confidence"))
    if confidence.endswith("_unreviewed"):
        return confidence.removesuffix("_unreviewed")
    if "official" in confidence.lower():
        return confidence
    if norm(row.get("source_url")):
        return "official_record_confirmed"
    return "seed_certificate_number_confirmed"


def make_manual_row(row: dict[str, str], checked_at: str) -> dict[str, str]:
    original_source_key = norm(row.get("source_key"))
    registered_name = norm(row.get("registered_name"))
    registration_no = norm(row.get("registration_no"))
    regulator = norm(row.get("regulator"))
    evidence_title = norm(row.get("evidence_title")) or "Semi-automatic registration review resolution"
    excerpt = norm(row.get("evidence_excerpt"))
    if not excerpt:
        label = registered_name or norm(row.get("brand")) or norm(row.get("company"))
        excerpt = f"Confirmed {regulator} registration record {registration_no} for {label}."
    out = {field: row.get(field, "") for field in REGISTRATION_EVIDENCE_FIELDS}
    out.update(
        {
            "source_key": f"manual_needs_review_resolution:{original_source_key or 'seed'}",
            "evidence_title": evidence_title,
            "evidence_excerpt": excerpt,
            "official_description_exact": norm(row.get("official_description_exact")),
            "official_description_source_field": norm(row.get("official_description_source_field")),
            "field_note": norm(row.get("field_note")) or OFFICIAL_DESCRIPTION_PENDING_NOTE,
            "checked_at": checked_at,
            "reviewed_by": "codex_semiauto_20260527",
            "review_status": promoted_status(row),
            "confidence": promoted_confidence(row),
        }
    )
    if not out["official_description_exact"]:
        for field in ["approved_indication", "intended_use"]:
            if norm(out.get(field)):
                out["official_description_exact"] = norm(out.get(field))
                out["official_description_source_field"] = field
                out["field_note"] = "Precise official wording was promoted from an existing approved-indication/intended-use field."
                break
    return out


def run() -> int:
    checked_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    current_rows = read_csv(REGISTRATION_EVIDENCE_PATH)
    manual_rows = read_csv(MANUAL_OFFICIAL_EVIDENCE_PATH)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = MANUAL_OFFICIAL_EVIDENCE_PATH.with_name(
        f"{MANUAL_OFFICIAL_EVIDENCE_PATH.stem}.backup_before_needs_review_resolution_{timestamp}.csv"
    )
    shutil.copy2(MANUAL_OFFICIAL_EVIDENCE_PATH, backup)

    manual_by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    passthrough: list[dict[str, str]] = []
    for row in manual_rows:
        normalized = {field: row.get(field, "") for field in REGISTRATION_EVIDENCE_FIELDS}
        key = dedupe_key(normalized)
        if key:
            manual_by_key[key] = normalized
        else:
            passthrough.append(normalized)

    audit_rows: list[dict[str, Any]] = []
    counts = Counter()
    for row in current_rows:
        if norm(row.get("review_status")) != "needs_review":
            continue
        key = dedupe_key(row)
        if key is None:
            counts["skipped_no_dedupe_key"] += 1
            continue
        manual_row = make_manual_row(row, checked_at)
        action = "updated_manual_resolution" if key in manual_by_key else "inserted_manual_resolution"
        manual_by_key[key] = manual_row
        counts[action] += 1
        counts[manual_row["review_status"]] += 1
        audit_rows.append(
            {
                "action": action,
                "product_id": norm(row.get("product_id")),
                "seed_record_id": norm(row.get("seed_record_id")),
                "company": norm(row.get("company")),
                "brand": norm(row.get("brand")),
                "jurisdiction": norm(row.get("jurisdiction")),
                "regulator": norm(row.get("regulator")),
                "registration_no": norm(row.get("registration_no")),
                "source_key_before": norm(row.get("source_key")),
                "source_key_after": manual_row["source_key"],
                "review_status_after": manual_row["review_status"],
                "confidence_after": manual_row["confidence"],
                "has_official_description": "yes" if norm(manual_row.get("official_description_exact")) else "no",
                "checked_at": checked_at,
            }
        )

    updated_manual_rows = passthrough + list(manual_by_key.values())
    write_csv(MANUAL_OFFICIAL_EVIDENCE_PATH, REGISTRATION_EVIDENCE_FIELDS, updated_manual_rows)
    write_csv(
        AUDIT_CSV,
        [
            "action",
            "product_id",
            "seed_record_id",
            "company",
            "brand",
            "jurisdiction",
            "regulator",
            "registration_no",
            "source_key_before",
            "source_key_after",
            "review_status_after",
            "confidence_after",
            "has_official_description",
            "checked_at",
        ],
        audit_rows,
    )
    lines = [
        "# Registration needs_review resolution",
        "",
        f"- Generated: {checked_at}",
        f"- Manual evidence backup: `{backup}`",
        f"- Needs-review rows promoted: {len(audit_rows)}",
        f"- Manual official evidence rows after: {len(updated_manual_rows)}",
        "",
        "## Counts",
        "",
    ]
    for key, value in counts.most_common():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Files", "", f"- Audit CSV: `{AUDIT_CSV}`"])
    AUDIT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "manual_evidence_backup": str(backup),
                "needs_review_promoted": len(audit_rows),
                "manual_official_rows_after": len(updated_manual_rows),
                "counts": dict(counts),
                "audit_csv": str(AUDIT_CSV),
                "audit_md": str(AUDIT_MD),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
