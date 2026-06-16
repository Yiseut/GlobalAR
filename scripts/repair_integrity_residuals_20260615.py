#!/usr/bin/env python3
"""Repair v4 integrity residuals that are safe to close mechanically.

The script fixes two acceptance blockers:
- product_id references that no longer resolve to active Product_Master rows
- promoted manual facts that only lacked logs because their product_id was stale

It edits source CSV files, not the generated SQLite database. Run build_data.py
after applying the repair so the database and generated promotion log rebuild
from the corrected sources.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"

PRODUCT_MASTER_PATH = DATA_DIR / "product_master.csv"
PRODUCT_FAMILY_MASTER_PATH = DATA_DIR / "product_family_master.csv"
PRODUCT_SKU_MASTER_PATH = DATA_DIR / "product_sku_master.csv"

SOURCE_FILES = [
    {
        "name": "manual_product_fact_evidence",
        "path": DATA_DIR / "manual_product_fact_evidence.csv",
        "status_field": "review_status",
        "unlink_status": "orphan_product_id_unlinked",
        "note_field": "note",
    },
    {
        "name": "product_specification_evidence",
        "path": DATA_DIR / "product_specification_evidence.csv",
        "status_field": "review_status",
        "unlink_status": "orphan_product_id_unlinked",
        "note_field": "notes",
    },
    {
        "name": "manual_evidence_promotion_log",
        "path": DATA_DIR / "manual_evidence_promotion_log.csv",
        "status_field": None,
        "unlink_status": "",
        "note_field": "note",
    },
    {
        "name": "briefing_update_candidates",
        "path": DATA_DIR / "briefing_update_candidates.csv",
        "status_field": "status",
        "unlink_status": "orphan_product_id_unlinked",
        "note_field": "official_query",
    },
    {
        "name": "briefing_verified_update_events",
        "path": DATA_DIR / "briefing_verified_update_events.csv",
        "status_field": "mapping_status",
        "unlink_status": "multi_product_or_orphan_unlinked",
        "note_field": "remaining_gap",
    },
]

PROMOTION_LOG_FIELDS = [
    "promotion_id",
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "product_family_id",
    "source_key",
    "source_type",
    "field_name",
    "promoted_value",
    "source_url",
    "evidence_title",
    "confidence",
    "promoted_at",
    "note",
]


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def keynorm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", norm(value).casefold()).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]], int]:
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    nul_count = text.count("\x00")
    if nul_count:
        text = text.replace("\x00", "")
    reader = csv.DictReader(io.StringIO(text))
    return list(reader.fieldnames or []), list(reader), nul_count


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def append_note(existing: str, marker: str) -> str:
    existing = norm(existing)
    if marker in existing:
        return existing
    return f"{existing} | {marker}" if existing else marker


def stable_id(prefix: str, *parts: Any) -> str:
    payload = "|".join(norm(part) for part in parts)
    return f"{prefix}_{hashlib.sha1(payload.encode('utf-8')).hexdigest()[:12]}"


def split_product_ids(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"[;,|]+", norm(value)) if part.strip()]


def build_indexes() -> dict[str, Any]:
    _, product_rows, _ = read_csv(PRODUCT_MASTER_PATH)
    _, family_rows, _ = read_csv(PRODUCT_FAMILY_MASTER_PATH)
    _, sku_rows, _ = read_csv(PRODUCT_SKU_MASTER_PATH)

    active_products = {
        row["product_id"]: row
        for row in product_rows
        if norm(row.get("product_id")) and norm(row.get("inclusion_status")).casefold() == "active"
    }
    by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    by_name: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    by_company_brand: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in active_products.values():
        by_seed[norm(row.get("seed_record_id"))].append(row)
        by_name[(keynorm(row.get("company")), keynorm(row.get("brand")), keynorm(row.get("standard_product_name")))].append(row)
        by_company_brand[(keynorm(row.get("company")), keynorm(row.get("brand")))].append(row)

    family_by_product: dict[str, str] = {}
    for row in sku_rows:
        seed = norm(row.get("seed_record_id"))
        family_id = norm(row.get("product_family_id"))
        if not seed or not family_id:
            continue
        for product in by_seed.get(seed, []):
            family_by_product[product["product_id"]] = family_id
    for row in family_rows:
        family_id = norm(row.get("product_family_id"))
        for seed in re.split(r"[,;|]+", norm(row.get("source_record_ids"))):
            for product in by_seed.get(norm(seed), []):
                family_by_product.setdefault(product["product_id"], family_id)

    return {
        "active_products": active_products,
        "by_seed": by_seed,
        "by_name": by_name,
        "by_company_brand": by_company_brand,
        "family_by_product": family_by_product,
    }


def deterministic_remap(row: dict[str, str], indexes: dict[str, Any]) -> tuple[str, dict[str, str] | None]:
    old_product_id = norm(row.get("product_id"))
    by_seed = indexes["by_seed"]
    by_name = indexes["by_name"]
    by_company_brand = indexes["by_company_brand"]

    seed = norm(row.get("seed_record_id"))
    if seed and len(by_seed.get(seed, [])) == 1:
        product = by_seed[seed][0]
        if product["product_id"] != old_product_id:
            return "remap_by_seed_record_id", product

    product_name = norm(row.get("standard_product_name")) or norm(row.get("product_name"))
    name_key = (keynorm(row.get("company")), keynorm(row.get("brand")), keynorm(product_name))
    if product_name and len(by_name.get(name_key, [])) == 1:
        product = by_name[name_key][0]
        if product["product_id"] != old_product_id:
            return "remap_by_company_brand_product", product

    brand_key = (keynorm(row.get("company")), keynorm(row.get("brand")))
    if len(by_company_brand.get(brand_key, [])) == 1:
        product = by_company_brand[brand_key][0]
        if product["product_id"] != old_product_id:
            return "remap_by_unique_company_brand", product

    return "unlink_orphan_product_id", None


def plan_source_file(item: dict[str, Any], indexes: dict[str, Any]) -> tuple[list[str], list[dict[str, str]], list[dict[str, Any]], int]:
    fieldnames, rows, nul_count = read_csv(item["path"])
    active_products = indexes["active_products"]
    plan_rows: list[dict[str, Any]] = []

    if "product_id" not in fieldnames:
        return fieldnames, rows, plan_rows, nul_count

    for row_number, row in enumerate(rows, start=2):
        product_id = norm(row.get("product_id"))
        if not product_id:
            continue

        product_ids = split_product_ids(product_id)
        if len(product_ids) > 1:
            active_parts = [pid for pid in product_ids if pid in active_products]
            action = "unlink_multi_product_reference" if len(active_parts) == len(product_ids) else "unlink_orphan_product_id"
            plan_rows.append(
                {
                    "source_table": item["name"],
                    "source_file": str(item["path"]),
                    "row_number": row_number,
                    "old_product_id": product_id,
                    "action": action,
                    "new_product_id": "",
                    "new_product_family_id": "",
                    "company": norm(row.get("company")),
                    "brand": norm(row.get("brand")),
                    "record_key": norm(row.get("fact_id")) or norm(row.get("spec_id")) or norm(row.get("promotion_id")) or norm(row.get("candidate_id")) or norm(row.get("event_id")),
                    "reason": "product_id column contains multiple product ids; row is retained as non-product-level trace",
                }
            )
            continue

        if product_id in active_products:
            continue

        action, product = deterministic_remap(row, indexes)
        plan_rows.append(
            {
                "source_table": item["name"],
                "source_file": str(item["path"]),
                "row_number": row_number,
                "old_product_id": product_id,
                "action": action,
                "new_product_id": norm(product.get("product_id")) if product else "",
                "new_product_family_id": indexes["family_by_product"].get(norm(product.get("product_id")), "") if product else "",
                "company": norm(row.get("company")),
                "brand": norm(row.get("brand")),
                "record_key": norm(row.get("fact_id")) or norm(row.get("spec_id")) or norm(row.get("promotion_id")) or norm(row.get("candidate_id")) or norm(row.get("event_id")),
                "reason": "stale product_id no longer resolves to current active Product_Master",
            }
        )

    return fieldnames, rows, plan_rows, nul_count


def apply_plan_to_rows(
    item: dict[str, Any],
    fieldnames: list[str],
    rows: list[dict[str, str]],
    plan_rows: list[dict[str, Any]],
    stamp: str,
) -> Counter[str]:
    plan_by_row = {int(plan["row_number"]): plan for plan in plan_rows}
    counts: Counter[str] = Counter()
    marker_prefix = f"integrity_residual_repair_20260615:{stamp}"

    for row_number, row in enumerate(rows, start=2):
        plan = plan_by_row.get(row_number)
        if not plan:
            continue

        action = norm(plan.get("action"))
        note = (
            f"{marker_prefix}: {action}; old_product_id={plan['old_product_id']}; "
            f"{plan['reason']}."
        )
        if action.startswith("remap_"):
            row["product_id"] = norm(plan.get("new_product_id"))
            if "product_family_id" in fieldnames and norm(plan.get("new_product_family_id")):
                row["product_family_id"] = norm(plan.get("new_product_family_id"))
            if item.get("status_field") and item["status_field"] in fieldnames:
                row[item["status_field"]] = append_note(row.get(item["status_field"], ""), "remapped_product_id")
        else:
            row["product_id"] = ""
            if "product_family_id" in fieldnames:
                row["product_family_id"] = ""
            if item.get("status_field") and item["status_field"] in fieldnames:
                row[item["status_field"]] = item["unlink_status"]

        note_field = item.get("note_field")
        if note_field and note_field in fieldnames:
            row[note_field] = append_note(row.get(note_field, ""), note)
        counts[action] += 1

    return counts


def backfill_active_missing_logs(indexes: dict[str, Any], stamp: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    _, fact_rows, _ = read_csv(DATA_DIR / "manual_product_fact_evidence.csv")
    _, generated_log_rows, _ = read_csv(DATA_DIR / "evidence_promotion_log.csv")
    manual_fields, manual_log_rows, _ = read_csv(DATA_DIR / "manual_evidence_promotion_log.csv")
    active_products = indexes["active_products"]

    log_keys = {
        (
            norm(row.get("product_id")),
            norm(row.get("field_name")).casefold(),
            norm(row.get("promoted_value")).casefold(),
        )
        for row in generated_log_rows + manual_log_rows
        if norm(row.get("product_id")) and norm(row.get("field_name")) and norm(row.get("promoted_value"))
    }
    additions: list[dict[str, str]] = []
    audit_rows: list[dict[str, Any]] = []
    promoted_at = datetime.now().astimezone().isoformat(timespec="seconds")

    for row in fact_rows:
        product_id = norm(row.get("product_id"))
        field_name = norm(row.get("field_name"))
        field_value = norm(row.get("field_value"))
        review_status = norm(row.get("review_status")).casefold()
        if not product_id or product_id not in active_products or not field_name or not field_value:
            continue
        if "orphan" in review_status or "unlinked" in review_status:
            continue
        key = (product_id, field_name.casefold(), field_value.casefold())
        if key in log_keys:
            continue
        product = active_products[product_id]
        addition = {
            "promotion_id": stable_id("promo_manual_fact_repair", row.get("fact_id"), product_id, field_name, row.get("source_url"), field_value),
            "product_id": product_id,
            "seed_record_id": norm(row.get("seed_record_id")) or norm(product.get("seed_record_id")),
            "company_id": norm(row.get("company_id")) or norm(product.get("company_id")),
            "company": norm(row.get("company")) or norm(product.get("company")),
            "brand": norm(row.get("brand")) or norm(product.get("brand")),
            "product_family_id": norm(row.get("product_family_id")),
            "source_key": norm(row.get("fact_group")) or "manual_product_fact_evidence",
            "source_type": norm(row.get("source_type")),
            "field_name": field_name,
            "promoted_value": field_value,
            "source_url": norm(row.get("source_url")),
            "evidence_title": norm(row.get("evidence_title")),
            "confidence": norm(row.get("confidence")),
            "promoted_at": norm(row.get("promoted_at")) or promoted_at,
            "note": f"integrity_residual_repair_20260615:{stamp}: trace log backfilled from manual_product_fact_evidence fact_id={norm(row.get('fact_id'))}.",
        }
        additions.append(addition)
        audit_rows.append(
            {
                "source_table": "manual_evidence_promotion_log",
                "record_key": addition["promotion_id"],
                "old_product_id": "",
                "action": "add_missing_active_fact_trace_log",
                "new_product_id": product_id,
                "company": addition["company"],
                "brand": addition["brand"],
                "reason": "active manual fact had no matching promotion trace log",
            }
        )
        log_keys.add(key)

    if additions and set(manual_fields) != set(PROMOTION_LOG_FIELDS):
        raise RuntimeError("manual_evidence_promotion_log.csv has an unexpected schema")
    return additions, audit_rows


def write_audit(plan_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    plan_path = AUDIT_DIR / "integrity_residual_repair_plan_20260615_latest.csv"
    fieldnames = [
        "source_table",
        "source_file",
        "row_number",
        "record_key",
        "old_product_id",
        "action",
        "new_product_id",
        "new_product_family_id",
        "company",
        "brand",
        "reason",
    ]
    with plan_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in plan_rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})

    summary["plan_path"] = str(plan_path)
    summary_path = AUDIT_DIR / "integrity_residual_repair_summary_20260615_latest.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def run(apply: bool) -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    indexes = build_indexes()
    all_plan_rows: list[dict[str, Any]] = []
    planned_files: list[tuple[dict[str, Any], list[str], list[dict[str, str]], list[dict[str, Any]], int]] = []
    nul_counts: dict[str, int] = {}

    for item in SOURCE_FILES:
        fieldnames, rows, plan_rows, nul_count = plan_source_file(item, indexes)
        planned_files.append((item, fieldnames, rows, plan_rows, nul_count))
        all_plan_rows.extend(plan_rows)
        if nul_count:
            nul_counts[item["name"]] = nul_count

    log_additions, log_audit_rows = backfill_active_missing_logs(indexes, stamp)
    all_plan_rows.extend(log_audit_rows)

    summary: dict[str, Any] = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "mode": "apply" if apply else "dry_run",
        "planned_rows": len(all_plan_rows),
        "planned_actions": dict(Counter(norm(row.get("action")) for row in all_plan_rows)),
        "nul_chars_removed_when_applied": nul_counts,
        "backfill_log_additions": len(log_additions),
        "changed_files": [],
    }

    if apply:
        for item, fieldnames, rows, plan_rows, nul_count in planned_files:
            path = item["path"]
            if not plan_rows and not nul_count:
                continue
            backup = path.with_name(f"{path.stem}_backup_before_integrity_residual_repair_20260615_{stamp}{path.suffix}")
            shutil.copy2(path, backup)
            counts = apply_plan_to_rows(item, fieldnames, rows, plan_rows, stamp)
            write_csv(path, fieldnames, rows)
            summary["changed_files"].append(
                {
                    "file": str(path),
                    "backup": str(backup),
                    "rows_changed": sum(counts.values()),
                    "actions": dict(counts),
                    "nul_chars_removed": nul_count,
                }
            )

        if log_additions:
            manual_log_path = DATA_DIR / "manual_evidence_promotion_log.csv"
            fieldnames, rows, nul_count = read_csv(manual_log_path)
            backup = manual_log_path.with_name(
                f"{manual_log_path.stem}_backup_before_integrity_residual_log_backfill_20260615_{stamp}{manual_log_path.suffix}"
            )
            shutil.copy2(manual_log_path, backup)
            rows.extend(log_additions)
            write_csv(manual_log_path, fieldnames, rows)
            summary["changed_files"].append(
                {
                    "file": str(manual_log_path),
                    "backup": str(backup),
                    "rows_changed": len(log_additions),
                    "actions": {"add_missing_active_fact_trace_log": len(log_additions)},
                    "nul_chars_removed": nul_count,
                }
            )

    write_audit(all_plan_rows, summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Apply the repair. Default is dry-run.")
    args = parser.parse_args()
    run(apply=args.apply)


if __name__ == "__main__":
    main()
