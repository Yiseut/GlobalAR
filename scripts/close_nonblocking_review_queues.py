#!/usr/bin/env python3
"""Close non-blocking evidence queues after policy decisions.

This script does not delete evidence. It changes operational statuses for raw
candidate pools that should no longer appear as user review work:
- CE/MDR: official claims are accepted as sufficient; no public certificate
  number chase is required.
- Official-source search results: already mined by promotion scripts; keep as
  candidate/reference pool.
- Media downloads: failed image downloads are non-blocking visual retries.
"""

from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

MDR_PLAN = DATA_DIR / "mdr_ce_search_plan.csv"
MDR_CANDIDATES = DATA_DIR / "mdr_ce_evidence_candidates.jsonl"
OFFICIAL_PLAN = DATA_DIR / "company_official_source_plan.csv"
OFFICIAL_EVIDENCE = DATA_DIR / "company_official_source_evidence.jsonl"
MEDIA_INDEX = DATA_DIR / "company_media_asset_index.csv"


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def backup(path: Path, stamp: str) -> Path | None:
    if not path.exists():
        return None
    out = path.with_name(f"{path.stem}.backup_before_nonblocking_queue_close_{stamp}{path.suffix}")
    shutil.copy2(path, out)
    return out


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def close_mdr_plan(stamp_iso: str) -> dict[str, Any]:
    fieldnames, rows = read_csv(MDR_PLAN)
    counts = Counter()
    for row in rows:
        previous = norm(row.get("review_status"))
        if previous in {"needs_review", "queued", "pending", ""}:
            row["review_status"] = "policy_closed_no_public_number_chase"
            row["automation_status"] = "closed_by_user_policy_20260601"
            counts["closed"] += 1
        else:
            counts["unchanged"] += 1
        if "closed_at" in fieldnames:
            row["closed_at"] = stamp_iso
    write_csv(MDR_PLAN, fieldnames, rows)
    return {"rows": len(rows), **counts}


def classify_mdr_candidate(row: dict[str, Any]) -> str:
    official = norm(row.get("official_candidate")).lower()
    confidence = norm(row.get("confidence")).lower()
    if official in {"yes", "likely"} or confidence in {"official_regulator_candidate", "official_document_candidate"}:
        return "policy_accepted_official_claim_no_number_required"
    if official == "possible" or confidence == "company_official_search_candidate":
        return "policy_archived_company_claim_candidate"
    if official == "no" or confidence == "secondary_source_crosscheck":
        return "archived_secondary_or_nonofficial"
    return "archived_search_candidate_no_user_action"


def close_mdr_candidates(stamp_iso: str) -> dict[str, Any]:
    rows = read_jsonl(MDR_CANDIDATES)
    counts = Counter()
    for row in rows:
        status = classify_mdr_candidate(row)
        if norm(row.get("crosscheck_status")) != status:
            row["previous_crosscheck_status"] = norm(row.get("crosscheck_status"))
            row["crosscheck_status"] = status
            row["closed_at"] = stamp_iso
            row["closure_note"] = "Closed by user policy: official CE/MDR claim or IFU is enough; do not chase public certificate number."
            counts[status] += 1
        else:
            counts["unchanged"] += 1
    write_jsonl(MDR_CANDIDATES, rows)
    return {"rows": len(rows), **counts}


def close_official_plan(stamp_iso: str) -> dict[str, Any]:
    fieldnames, rows = read_csv(OFFICIAL_PLAN)
    counts = Counter()
    for row in rows:
        previous = norm(row.get("status"))
        if previous in {"ready", "queued", "pending", "needs_review", ""}:
            row["status"] = "completed_or_superseded"
            counts["closed"] += 1
        else:
            counts["unchanged"] += 1
        if "reviewer_note" in fieldnames and "non-blocking" not in norm(row.get("reviewer_note")).lower():
            row["reviewer_note"] = (norm(row.get("reviewer_note")) + " | non-blocking source plan closed after promotion pass").strip(" |")
        if "closed_at" in fieldnames:
            row["closed_at"] = stamp_iso
    write_csv(OFFICIAL_PLAN, fieldnames, rows)
    return {"rows": len(rows), **counts}


def classify_official_candidate(row: dict[str, Any]) -> str:
    official = norm(row.get("official_candidate")).lower()
    confidence = norm(row.get("confidence")).lower()
    if official in {"likely", "possible"} and "official" in confidence:
        return "official_candidate_pool_indexed"
    if official == "no" or confidence == "secondary_source_crosscheck":
        return "archived_secondary_or_nonofficial"
    return "archived_search_candidate_no_user_action"


def close_official_evidence(stamp_iso: str) -> dict[str, Any]:
    rows = read_jsonl(OFFICIAL_EVIDENCE)
    counts = Counter()
    for row in rows:
        status = classify_official_candidate(row)
        if norm(row.get("crosscheck_status")) != status:
            row["previous_crosscheck_status"] = norm(row.get("crosscheck_status"))
            row["crosscheck_status"] = status
            row["closed_at"] = stamp_iso
            row["closure_note"] = "Closed as non-blocking source pool after product fact/spec promotion."
            counts[status] += 1
        else:
            counts["unchanged"] += 1
    write_jsonl(OFFICIAL_EVIDENCE, rows)
    return {"rows": len(rows), **counts}


def close_media_retries(stamp_iso: str) -> dict[str, Any]:
    fieldnames, rows = read_csv(MEDIA_INDEX)
    counts = Counter()
    for row in rows:
        review = norm(row.get("review_status"))
        if review in {"error", "download_failed"}:
            row["review_status"] = "retry_closed_nonblocking"
            note = norm(row.get("notes"))
            suffix = f"Retry closed {stamp_iso}: media asset is non-blocking; keep source page/index trace."
            row["notes"] = f"{note} | {suffix}" if note else suffix
            counts["closed_retry"] += 1
        else:
            counts["unchanged"] += 1
    write_csv(MEDIA_INDEX, fieldnames, rows)
    return {"rows": len(rows), **counts}


def write_report(results: dict[str, dict[str, Any]], backups: dict[str, str | None], stamp: str) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = AUDIT_DIR / f"nonblocking_review_queue_close_{stamp}.csv"
    html_path = AUDIT_DIR / f"nonblocking_review_queue_close_{stamp}.html"
    json_path = AUDIT_DIR / f"nonblocking_review_queue_close_{stamp}_summary.json"
    rows = []
    for target, payload in results.items():
        for key, value in payload.items():
            if key == "rows":
                continue
            rows.append({"target": target, "metric": key, "value": value, "total_rows": payload.get("rows", 0), "backup": backups.get(target) or ""})
    write_csv(csv_path, ["target", "metric", "value", "total_rows", "backup"], rows)
    json_path.write_text(json.dumps({"results": results, "backups": backups}, ensure_ascii=False, indent=2), encoding="utf-8")
    html_rows = "\n".join(
        f"<tr><td>{row['target']}</td><td>{row['metric']}</td><td>{row['value']}</td><td>{row['total_rows']}</td><td>{row['backup']}</td></tr>"
        for row in rows
    )
    html_path.write_text(
        "<!doctype html><meta charset='utf-8'><title>Non-blocking queue close</title>"
        "<style>body{font-family:Arial,sans-serif;margin:24px}table{border-collapse:collapse;width:100%}"
        "td,th{border:1px solid #ddd;padding:8px}th{background:#f5f5f5;text-align:left}</style>"
        "<h1>Non-blocking Review Queue Close</h1>"
        "<p>Raw evidence pools were closed as reference/archived queues after user policy decisions. No evidence was deleted.</p>"
        "<table><thead><tr><th>Target</th><th>Metric</th><th>Value</th><th>Total rows</th><th>Backup</th></tr></thead>"
        f"<tbody>{html_rows}</tbody></table>",
        encoding="utf-8",
    )
    print(json.dumps({"csv": str(csv_path), "html": str(html_path), "summary": str(json_path), "results": results}, ensure_ascii=False, indent=2))


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stamp_iso = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    backups = {
        "mdr_ce_search_plan": str(backup(MDR_PLAN, stamp) or ""),
        "mdr_ce_evidence_candidates": str(backup(MDR_CANDIDATES, stamp) or ""),
        "company_official_source_plan": str(backup(OFFICIAL_PLAN, stamp) or ""),
        "company_official_source_evidence": str(backup(OFFICIAL_EVIDENCE, stamp) or ""),
        "company_media_asset_index": str(backup(MEDIA_INDEX, stamp) or ""),
    }
    results = {
        "mdr_ce_search_plan": close_mdr_plan(stamp_iso),
        "mdr_ce_evidence_candidates": close_mdr_candidates(stamp_iso),
        "company_official_source_plan": close_official_plan(stamp_iso),
        "company_official_source_evidence": close_official_evidence(stamp_iso),
        "company_media_asset_index": close_media_retries(stamp_iso),
    }
    write_report(results, backups, stamp)


if __name__ == "__main__":
    main()
