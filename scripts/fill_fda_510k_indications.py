#!/usr/bin/env python3
"""Fill missing FDA 510(k) indication wording in manual evidence rows."""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from promote_fda_gap_queue import (
    MANUAL_EVIDENCE_PATH,
    MANUAL_FIELDS,
    extract_510k_indication,
    norm,
    pmn_url,
)


ROOT = Path(__file__).resolve().parents[1]
AUDITS_DIR = ROOT / "data" / "audits"


def load_rows() -> list[dict[str, str]]:
    if not MANUAL_EVIDENCE_PATH.exists():
        return []
    with MANUAL_EVIDENCE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(rows: list[dict[str, str]], dry_run: bool) -> str:
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = MANUAL_EVIDENCE_PATH.with_suffix(f".pre_fda_indication_{batch_id}.csv")
    if not dry_run:
        shutil.copy2(MANUAL_EVIDENCE_PATH, backup)
        with MANUAL_EVIDENCE_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=MANUAL_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in MANUAL_FIELDS})
    return str(backup)


def write_rows_without_backup(rows: list[dict[str, str]]) -> None:
    with MANUAL_EVIDENCE_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANUAL_FIELDS})


def fill(args: argparse.Namespace) -> dict[str, Any]:
    rows = load_rows()
    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    report_rows: list[dict[str, str]] = []
    counters: Counter[str] = Counter()
    updated_indexes: set[int] = set()
    selected = []
    for idx, row in enumerate(rows):
        registration_no = norm(row.get("registration_no")).upper()
        if not re.match(r"^K\d{6}$", registration_no):
            continue
        if norm(row.get("intended_use")) or norm(row.get("approved_indication")):
            continue
        if not args.retry_not_found and norm(row.get("review_status")) == "pdf_indication_not_found":
            continue
        source_key = norm(row.get("source_key"))
        source_type = norm(row.get("source_type"))
        if args.only_gap_queue and source_key != "fda_510k_gap_queue_official":
            continue
        if "fda" not in f"{source_key} {source_type}".lower():
            continue
        selected.append((idx, row))
        if args.limit and len(selected) >= args.limit:
            break

    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ""
    if selected and not args.dry_run:
        backup_path = MANUAL_EVIDENCE_PATH.with_suffix(f".pre_fda_indication_{batch_id}.csv")
        shutil.copy2(MANUAL_EVIDENCE_PATH, backup_path)
        backup = str(backup_path)

    for idx, row in selected:
        k_number = norm(row.get("registration_no")).upper()
        indication, pdf_url, pdf_excerpt = extract_510k_indication(k_number)
        if indication:
            row["approved_indication"] = indication
            row["intended_use"] = indication
            row["source_url"] = pdf_url or row.get("source_url") or pmn_url(k_number)
            row["source_type"] = "official_fda_document"
            row["evidence_excerpt"] = " | ".join(
                part
                for part in [
                    norm(row.get("evidence_excerpt")),
                    f"FDA 510(k) PDF indication captured: {indication[:500]}",
                ]
                if part
            )[:1200]
            row["checked_at"] = checked_at
            row["reviewed_by"] = "codex_fda_pdf_indication_fill"
            row["review_status"] = "auto_cross_checked"
            row["confidence"] = "official_fda_document_promoted"
            updated_indexes.add(idx)
            counters["updated"] += 1
            if not args.dry_run:
                write_rows_without_backup(rows)
        else:
            row["checked_at"] = checked_at
            row["reviewed_by"] = "codex_fda_pdf_indication_fill"
            row["review_status"] = "pdf_indication_not_found"
            counters["not_found"] += 1
            if not args.dry_run:
                write_rows_without_backup(rows)
        report_rows.append(
            {
                "status": "updated" if idx in updated_indexes else "not_found",
                "company": norm(row.get("company")),
                "brand": norm(row.get("brand")),
                "product_id": norm(row.get("product_id")),
                "registration_no": k_number,
                "source_url": pdf_url or row.get("source_url") or pmn_url(k_number),
                "indication_excerpt": indication[:500],
            }
        )
        if args.sleep:
            time.sleep(args.sleep)

    report_path = AUDITS_DIR / f"fda_510k_indication_fill_{batch_id}.csv"
    with report_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["status", "company", "brand", "product_id", "registration_no", "source_url", "indication_excerpt"],
        )
        writer.writeheader()
        writer.writerows(report_rows)
    (AUDITS_DIR / "fda_510k_indication_fill_latest.csv").write_text(
        report_path.read_text(encoding="utf-8-sig"),
        encoding="utf-8-sig",
    )
    summary = {
        "rows_selected": len(selected),
        "updated": counters["updated"],
        "not_found": counters["not_found"],
        "dry_run": args.dry_run,
        "backup": backup,
        "report_csv": str(report_path),
    }
    (AUDITS_DIR / "fda_510k_indication_fill_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--sleep", type=float, default=0.02)
    parser.add_argument("--only-gap-queue", action="store_true")
    parser.add_argument("--retry-not-found", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(fill(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
