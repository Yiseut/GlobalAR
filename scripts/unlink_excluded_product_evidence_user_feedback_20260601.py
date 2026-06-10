from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

ORPHAN_PRODUCT_IDS = {
    "prod_f3262e00d428": "REC_0963 Dongkook/Nabota wrong attribution; canonical active row is REC_0473 Daewoong / Nabota.",
    "prod_f2adaaca4e65": "REC_0965 Jetema/Yvoire wrong attribution; canonical active row is REC_0778 LG Chem / Yvoire.",
    "prod_8aca814d2399": "REC_0533 Daejoo PDRN/PN API raw-material line excluded from terminal aesthetic product master.",
    "prod_6232571cca15": "REC_0475 Arthrex/NanoScope generic endoscopic surgical device excluded from core aesthetics upstream scope.",
    "prod_ce8125425c4c": "REC_0101 Contura/Bulkamid urogynecology urethral bulking product excluded from core aesthetics upstream scope.",
}

FILES = [
    {
        "path": DATA_DIR / "manual_product_fact_evidence.csv",
        "note_field": "note",
        "status_field": "review_status",
    },
    {
        "path": DATA_DIR / "manual_evidence_promotion_log.csv",
        "note_field": "note",
        "status_field": None,
    },
    {
        "path": DATA_DIR / "product_specification_evidence.csv",
        "note_field": "notes",
        "status_field": "review_status",
    },
]


def append_note(existing: str, marker: str) -> str:
    existing = (existing or "").strip()
    if marker in existing:
        return existing
    if existing:
        return f"{existing} | {marker}"
    return marker


def process_file(path: Path, note_field: str, status_field: str | None, timestamp: str) -> dict:
    backup = path.with_name(f"{path.stem}_backup_before_user_feedback_excluded_unlink_{timestamp}{path.suffix}")
    shutil.copy2(path, backup)

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    by_id: Counter[str] = Counter()
    for row in rows:
        original_product_id = (row.get("product_id") or "").strip()
        if original_product_id not in ORPHAN_PRODUCT_IDS:
            continue

        reason = ORPHAN_PRODUCT_IDS[original_product_id]
        marker = (
            "excluded_product_unlink_user_feedback_20260601: "
            f"{reason} Retained as company/source-history evidence only, not active product evidence."
        )
        row["product_id"] = ""
        if "product_family_id" in row:
            row["product_family_id"] = ""
        if status_field and status_field in row:
            row[status_field] = "excluded_scope_unlinked"
        if note_field in row:
            row[note_field] = append_note(row.get(note_field, ""), marker)
        by_id[original_product_id] += 1

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    return {
        "file": str(path),
        "backup": str(backup),
        "rows_unlinked": sum(by_id.values()),
        "by_original_product_id": dict(by_id),
    }


def main() -> None:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now().replace(microsecond=0).isoformat()
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    changes = [
        process_file(item["path"], item["note_field"], item["status_field"], timestamp)
        for item in FILES
    ]

    summary = {
        "generated_at": generated_at,
        "reason": "A3 evidence product_id integrity: unlink evidence attached to newly excluded or wrong-attribution products from user feedback.",
        "orphan_product_ids": ORPHAN_PRODUCT_IDS,
        "changes": changes,
        "total_rows_unlinked": sum(change["rows_unlinked"] for change in changes),
    }

    json_path = AUDIT_DIR / "excluded_product_evidence_unlink_user_feedback_20260601_latest.json"
    json_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    csv_path = AUDIT_DIR / "excluded_product_evidence_unlink_user_feedback_20260601_latest.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        fieldnames = ["file", "original_product_id", "reason", "rows_unlinked", "backup"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for change in changes:
            for product_id, count in change["by_original_product_id"].items():
                writer.writerow(
                    {
                        "file": change["file"],
                        "original_product_id": product_id,
                        "reason": ORPHAN_PRODUCT_IDS[product_id],
                        "rows_unlinked": count,
                        "backup": change["backup"],
                    }
                )

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
