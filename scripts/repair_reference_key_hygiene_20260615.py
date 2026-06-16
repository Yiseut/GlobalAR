#!/usr/bin/env python3
"""Repair residual company_id/product_family_id orphans in reference sources.

The v4 acceptance checks only require product_id integrity. This companion
repair handles older evidence/reference pools where stale company or product
family IDs still point outside the current master tables.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import io
import json
import re
import shutil
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
DB_PATH = DATA_DIR / "global_aesthetics.db"
MARKER = "ref_hygiene_20260615"


@dataclass(frozen=True)
class SourceSpec:
    filename: str
    table_name: str
    key_field: str
    note_field: str | None = None
    drop_if_unresolved_company_pk: bool = False

    @property
    def path(self) -> Path:
        return DATA_DIR / self.filename


CSV_SOURCES = [
    SourceSpec("manual_product_fact_evidence.csv", "manual_product_fact_evidence", "fact_id", "note"),
    SourceSpec("product_specification_evidence.csv", "product_specification_evidence", "spec_id", "notes"),
    SourceSpec("manual_evidence_promotion_log.csv", "manual_evidence_promotion_log", "promotion_id", "note"),
    SourceSpec("manual_nmpa_registration_evidence.csv", "manual_nmpa_registration_evidence", "source_key", "field_note"),
    SourceSpec("manual_registration_name_evidence.csv", "manual_registration_name_evidence", "source_key", "field_note"),
    SourceSpec("manual_official_indication_evidence.csv", "manual_official_indication_evidence", "source_key", "field_note"),
    SourceSpec("company_media_asset_index.csv", "company_media_asset_index", "asset_id", "notes"),
    SourceSpec("official_website_master.csv", "official_website_master", "website_id", "relationship_notes"),
    SourceSpec("company_official_source_plan.csv", "company_official_source_plan", "plan_id", "notes"),
    SourceSpec("mdr_ce_search_plan.csv", "mdr_ce_search_plan", "plan_id", "notes"),
    SourceSpec("company_official_website.csv", "company_official_website", "company_id", "notes", True),
    SourceSpec("company_capital_structure.csv", "company_capital_structure", "company_id", "notes", True),
    SourceSpec("listed_company_batch.csv", "listed_company_batch", "batch_id", "notes"),
    SourceSpec("company_financial_metrics.csv", "company_financial_metrics", "company_id", "note"),
    SourceSpec("registration_evidence.csv", "registration_evidence", "product_id", "field_note"),
    SourceSpec("briefing_update_candidates.csv", "briefing_update_candidates", "candidate_id", None),
]

JSONL_SOURCES = [
    SourceSpec("company_official_source_evidence.jsonl", "company_official_source_evidence", "evidence_id", None),
    SourceSpec("mdr_ce_evidence_candidates.jsonl", "mdr_ce_evidence_candidates", "evidence_id", None),
    SourceSpec("company_background_evidence.jsonl", "company_background_evidence", "source_url", None),
    SourceSpec("verification_evidence_staging.jsonl", "verification_evidence_staging", "source_record_id", None),
]


def text(value: Any) -> str:
    return str(value or "").replace("\x00", "").strip()


def key_text(value: Any) -> str:
    value = text(value).lower()
    value = value.replace("&", " and ")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


COMPANY_SUFFIX_RE = re.compile(
    r"\b("
    r"co|company|corp|corporation|inc|incorporated|ltd|limited|llc|plc|"
    r"gmbh|ag|sa|sas|srl|spa|holdings?|group|medical|medicals|meditech|"
    r"pharma|pharmaceuticals?|biologics|aesthetics?|technologies?|technology|"
    r"systems?|systeme"
    r")\b\.?$"
)


def company_name_keys(value: Any) -> list[str]:
    """Return conservative name keys, including a suffix-stripped variant."""
    base = key_text(value)
    if not base:
        return []
    variants = [base]
    stripped = base
    while True:
        next_value = COMPANY_SUFFIX_RE.sub("", stripped).strip(" .,-")
        next_value = re.sub(r"\s+", " ", next_value).strip()
        if not next_value or next_value == stripped:
            break
        stripped = next_value
        variants.append(stripped)
    seen = set()
    output = []
    for item in variants:
        if item and item not in seen:
            output.append(item)
            seen.add(item)
    return output


def present(value: Any) -> bool:
    return bool(text(value))


def split_aliases(raw: Any) -> list[str]:
    value = text(raw)
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, list):
        return [text(item) for item in parsed if text(item)]
    return [item.strip() for item in re.split(r"[|;,]", value) if item.strip()]


def unique_map(pairs: list[tuple[tuple[Any, ...], str]]) -> dict[tuple[Any, ...], str]:
    values: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for key, value in pairs:
        if all(present(part) for part in key) and present(value):
            values[key].add(value)
    return {key: next(iter(ids)) for key, ids in values.items() if len(ids) == 1}


def load_reference_maps() -> dict[str, Any]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Missing SQLite database: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    company_rows = cur.execute(
        "SELECT company_id, canonical_name, aliases FROM company_master"
    ).fetchall()
    family_rows = cur.execute(
        """
        SELECT product_family_id, company_id, company, brand, product_family
        FROM product_family_master
        """
    ).fetchall()
    sku_rows = cur.execute(
        "SELECT sku_id, product_family_id FROM product_sku_master"
    ).fetchall()
    product_rows = cur.execute("SELECT product_id FROM product_master").fetchall()
    conn.close()

    company_ids = {row["company_id"] for row in company_rows if present(row["company_id"])}
    family_ids = {row["product_family_id"] for row in family_rows if present(row["product_family_id"])}
    product_ids = {row["product_id"] for row in product_rows if present(row["product_id"])}

    company_pairs: list[tuple[tuple[Any, ...], str]] = []
    for row in company_rows:
        cid = text(row["company_id"])
        names = [row["canonical_name"], *split_aliases(row["aliases"])]
        for name in names:
            for name_key in company_name_keys(name):
                company_pairs.append(((name_key,), cid))
    company_by_name = unique_map(company_pairs)

    family_by_id: dict[str, dict[str, str]] = {}
    by_company_brand_family: list[tuple[tuple[Any, ...], str]] = []
    by_company_family: list[tuple[tuple[Any, ...], str]] = []
    by_company_name_brand_family: list[tuple[tuple[Any, ...], str]] = []
    by_company_name_family: list[tuple[tuple[Any, ...], str]] = []
    by_global_brand_family: list[tuple[tuple[Any, ...], str]] = []
    for row in family_rows:
        fid = text(row["product_family_id"])
        cid = text(row["company_id"])
        company = key_text(row["company"])
        brand = key_text(row["brand"])
        family = key_text(row["product_family"])
        family_by_id[fid] = {
            "company_id": cid,
            "company": text(row["company"]),
            "brand": text(row["brand"]),
            "product_family": text(row["product_family"]),
        }
        by_company_brand_family.append(((cid, brand, family), fid))
        by_company_family.append(((cid, family), fid))
        by_company_name_brand_family.append(((company, brand, family), fid))
        by_company_name_family.append(((company, family), fid))
        by_global_brand_family.append(((brand, family), fid))

    product_to_family: dict[str, str] = {}
    for row in sku_rows:
        product_id = text(row["sku_id"])
        family_id = text(row["product_family_id"])
        if product_id in product_ids and family_id in family_ids:
            product_to_family[product_id] = family_id

    return {
        "company_ids": company_ids,
        "family_ids": family_ids,
        "product_ids": product_ids,
        "company_by_name": company_by_name,
        "family_by_id": family_by_id,
        "product_to_family": product_to_family,
        "family_by_company_brand_family": unique_map(by_company_brand_family),
        "family_by_company_family": unique_map(by_company_family),
        "family_by_company_name_brand_family": unique_map(by_company_name_brand_family),
        "family_by_company_name_family": unique_map(by_company_name_family),
        "family_by_global_brand_family": unique_map(by_global_brand_family),
    }


def row_key(row: dict[str, Any], spec: SourceSpec, row_number: int) -> str:
    for field in [spec.key_field, "evidence_id", "website_id", "plan_id", "asset_id", "promotion_id", "fact_id", "spec_id", "candidate_id", "product_id", "source_url"]:
        if field in row and present(row.get(field)):
            return text(row.get(field))
    return f"row_{row_number}"


def add_audit(
    audit_rows: list[dict[str, Any]],
    spec: SourceSpec,
    row: dict[str, Any],
    row_number: int,
    action: str,
    field_name: str,
    old_value: Any,
    new_value: Any,
    reason: str,
) -> None:
    audit_rows.append(
        {
            "source_file": spec.filename,
            "table_name": spec.table_name,
            "row_number": row_number,
            "row_key": row_key(row, spec, row_number),
            "action": action,
            "field_name": field_name,
            "old_value": text(old_value),
            "new_value": text(new_value),
            "company": text(row.get("company")),
            "brand": text(row.get("brand")),
            "product_family": text(row.get("product_family")),
            "product_id": text(row.get("product_id")),
            "reason": reason,
        }
    )


def append_note(row: dict[str, Any], spec: SourceSpec, actions: list[dict[str, str]]) -> None:
    if not spec.note_field or spec.note_field not in row or not actions:
        return
    if MARKER in text(row.get(spec.note_field)):
        return
    fragments = []
    for action in actions:
        old_value = action["old_value"]
        new_value = action["new_value"]
        if new_value:
            fragments.append(f"{action['field_name']} {old_value}->{new_value}")
        else:
            fragments.append(f"{action['field_name']} cleared {old_value}")
    note = f"{MARKER}: " + "; ".join(fragments[:4])
    existing = text(row.get(spec.note_field))
    row[spec.note_field] = f"{existing}; {note}" if existing else note


def candidate_company_ids(
    row: dict[str, Any],
    refs: dict[str, Any],
    fields: list[str] | None = None,
) -> list[tuple[str, str]]:
    candidates = []
    fields = fields or ["company", "canonical_name", "company_name", "listed_parent_company", "related_company", "legal_manufacturer", "marketing_holder"]
    for field in fields:
        for name_key in company_name_keys(row.get(field)):
            lookup_key = (name_key,)
            if name_key and lookup_key in refs["company_by_name"]:
                candidates.append((refs["company_by_name"][lookup_key], f"matched current company_master by {field}"))
    seen = set()
    unique = []
    for cid, reason in candidates:
        if cid not in seen:
            unique.append((cid, reason))
            seen.add(cid)
    return unique


def remap_company_reference_if_needed(
    row: dict[str, Any],
    spec: SourceSpec,
    refs: dict[str, Any],
    row_number: int,
    audit_rows: list[dict[str, Any]],
    field_name: str = "company_id",
    candidate_fields: list[str] | None = None,
    drop_if_unresolved_primary: bool = False,
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    old_company_id = text(row.get(field_name))
    if not old_company_id or old_company_id in refs["company_ids"]:
        return actions

    matches = candidate_company_ids(row, refs, candidate_fields)
    if len(matches) == 1:
        new_company_id, reason = matches[0]
        row[field_name] = new_company_id
        add_audit(
            audit_rows,
            spec,
            row,
            row_number,
            f"{field_name}_remap_by_name",
            field_name,
            old_company_id,
            new_company_id,
            reason,
        )
        actions.append({"field_name": field_name, "old_value": old_company_id, "new_value": new_company_id})
        return actions

    if drop_if_unresolved_primary:
        add_audit(
            audit_rows,
            spec,
            row,
            row_number,
            "drop_unresolved_company_pk_row",
            field_name,
            old_company_id,
            "",
            f"{field_name} is the source row key and no unique current company match was found",
        )
        actions.append({"field_name": field_name, "old_value": old_company_id, "new_value": ""})
        return actions

    row[field_name] = ""
    reason = f"orphan {field_name} had no unique current company_master name match"
    if len(matches) > 1:
        reason = f"orphan {field_name} matched multiple current company candidates"
    add_audit(
        audit_rows,
        spec,
        row,
        row_number,
        f"{field_name}_clear_orphan",
        field_name,
        old_company_id,
        "",
        reason,
    )
    actions.append({"field_name": field_name, "old_value": old_company_id, "new_value": ""})
    return actions


def remap_company_if_needed(
    row: dict[str, Any],
    spec: SourceSpec,
    refs: dict[str, Any],
    row_number: int,
    audit_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    return remap_company_reference_if_needed(
        row,
        spec,
        refs,
        row_number,
        audit_rows,
        "company_id",
        None,
        spec.drop_if_unresolved_company_pk,
    )


def family_match(row: dict[str, Any], refs: dict[str, Any]) -> tuple[str, str]:
    product_id = text(row.get("product_id"))
    if product_id and product_id in refs["product_to_family"]:
        return refs["product_to_family"][product_id], "matched product_sku_master by product_id"

    company_id = text(row.get("company_id"))
    brand = key_text(row.get("brand"))
    family = key_text(row.get("product_family") or row.get("standard_product_name"))
    company_name = key_text(row.get("company"))

    lookups = [
        (refs["family_by_company_brand_family"], (company_id, brand, family), "matched product_family_master by company_id + brand + family"),
        (refs["family_by_company_family"], (company_id, family), "matched product_family_master by company_id + family"),
        (refs["family_by_company_name_brand_family"], (company_name, brand, family), "matched product_family_master by company name + brand + family"),
        (refs["family_by_company_name_family"], (company_name, family), "matched product_family_master by company name + family"),
        (refs["family_by_global_brand_family"], (brand, family), "matched unique product_family_master by brand + family"),
    ]
    for mapping, key, reason in lookups:
        if all(present(part) for part in key) and key in mapping:
            return mapping[key], reason
    return "", ""


def remap_family_if_needed(
    row: dict[str, Any],
    spec: SourceSpec,
    refs: dict[str, Any],
    row_number: int,
    audit_rows: list[dict[str, Any]],
) -> list[dict[str, str]]:
    actions: list[dict[str, str]] = []
    old_family_id = text(row.get("product_family_id"))
    if not old_family_id or old_family_id in refs["family_ids"]:
        return actions

    new_family_id, reason = family_match(row, refs)
    if new_family_id:
        row["product_family_id"] = new_family_id
        add_audit(
            audit_rows,
            spec,
            row,
            row_number,
            "product_family_id_remap",
            "product_family_id",
            old_family_id,
            new_family_id,
            reason,
        )
        actions.append({"field_name": "product_family_id", "old_value": old_family_id, "new_value": new_family_id})

        current_company_id = text(row.get("company_id"))
        family_company_id = refs["family_by_id"].get(new_family_id, {}).get("company_id", "")
        if family_company_id and (not current_company_id or current_company_id not in refs["company_ids"]):
            row["company_id"] = family_company_id
            add_audit(
                audit_rows,
                spec,
                row,
                row_number,
                "company_id_fill_from_family",
                "company_id",
                current_company_id,
                family_company_id,
                "filled company_id from remapped product_family_id owner",
            )
            actions.append({"field_name": "company_id", "old_value": current_company_id, "new_value": family_company_id})
        return actions

    row["product_family_id"] = ""
    add_audit(
        audit_rows,
        spec,
        row,
        row_number,
        "product_family_id_clear_orphan",
        "product_family_id",
        old_family_id,
        "",
        "orphan product_family_id had no unique current product_family_master match",
    )
    actions.append({"field_name": "product_family_id", "old_value": old_family_id, "new_value": ""})
    return actions


def read_csv_source(path: Path) -> tuple[list[str], list[dict[str, Any]], bool]:
    raw = path.read_bytes()
    has_bom = raw.startswith(codecs.BOM_UTF8)
    content = raw.decode("utf-8-sig" if has_bom else "utf-8").replace("\x00", "")
    reader = csv.DictReader(io.StringIO(content))
    return list(reader.fieldnames or []), list(reader), has_bom


def write_csv_source(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], has_bom: bool) -> None:
    encoding = "utf-8-sig" if has_bom else "utf-8"
    with path.open("w", encoding=encoding, newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_jsonl_source(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def write_jsonl_source(path: Path, rows: list[dict[str, Any]]) -> None:
    content = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    path.write_text(content + ("\n" if content else ""), encoding="utf-8")


def process_rows(
    rows: list[dict[str, Any]],
    spec: SourceSpec,
    refs: dict[str, Any],
    audit_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Counter, int]:
    output_rows = []
    action_counter: Counter = Counter()
    changed_rows = 0

    for row_number, row in enumerate(rows, start=2):
        row_actions: list[dict[str, str]] = []
        original = dict(row)
        drop_row = False

        if "company_id" in row:
            company_actions = remap_company_if_needed(row, spec, refs, row_number, audit_rows)
            row_actions.extend(company_actions)
            if company_actions and any(
                item["field_name"] == "company_id" and item["new_value"] == "" for item in company_actions
            ) and spec.drop_if_unresolved_company_pk:
                drop_row = True

        if not drop_row and "related_company_id" in row:
            row_actions.extend(
                remap_company_reference_if_needed(
                    row,
                    spec,
                    refs,
                    row_number,
                    audit_rows,
                    "related_company_id",
                    ["related_company", "company", "listed_parent_company", "canonical_name", "company_name"],
                    False,
                )
            )

        if not drop_row and "product_family_id" in row:
            row_actions.extend(remap_family_if_needed(row, spec, refs, row_number, audit_rows))

        if not drop_row and "company_id" in row and "product_family_id" in row:
            current_company_id = text(row.get("company_id"))
            current_family_id = text(row.get("product_family_id"))
            family_company_id = refs["family_by_id"].get(current_family_id, {}).get("company_id", "")
            if current_family_id in refs["family_ids"] and (
                not current_company_id or current_company_id not in refs["company_ids"]
            ) and family_company_id:
                row["company_id"] = family_company_id
                add_audit(
                    audit_rows,
                    spec,
                    row,
                    row_number,
                    "company_id_fill_from_existing_family",
                    "company_id",
                    current_company_id,
                    family_company_id,
                    "filled company_id from already-valid product_family_id owner",
                )
                row_actions.append({"field_name": "company_id", "old_value": current_company_id, "new_value": family_company_id})

        if row_actions:
            changed_rows += 1
            append_note(row, spec, row_actions)
            for item in audit_rows[-len(row_actions) :]:
                action_counter[item["action"]] += 1

        if drop_row:
            action_counter["rows_dropped"] += 1
        else:
            output_rows.append(row)

        # Defensive: avoid retaining accidental keys introduced by transforms.
        for key in list(row):
            if key not in original and key not in {"company_id", "product_family_id"}:
                row.pop(key, None)

    return output_rows, action_counter, changed_rows


def backup_file(path: Path, timestamp: str) -> Path:
    backup = path.with_name(f"{path.stem}_backup_before_reference_key_hygiene_20260615_{timestamp}{path.suffix}")
    shutil.copy2(path, backup)
    return backup


def write_audit_files(audit_rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    plan_path = AUDIT_DIR / "reference_key_hygiene_plan_20260615_latest.csv"
    summary_path = AUDIT_DIR / "reference_key_hygiene_summary_20260615_latest.json"
    fields = [
        "source_file",
        "table_name",
        "row_number",
        "row_key",
        "action",
        "field_name",
        "old_value",
        "new_value",
        "company",
        "brand",
        "product_family",
        "product_id",
        "reason",
    ]
    with plan_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(audit_rows)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write repaired source files")
    args = parser.parse_args()

    refs = load_reference_maps()
    audit_rows: list[dict[str, Any]] = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    generated_at = datetime.now(timezone.utc).isoformat()
    summary: dict[str, Any] = {
        "generated_at": generated_at,
        "apply": args.apply,
        "db_path": str(DB_PATH),
        "marker": MARKER,
        "files": {},
        "totals": {"audit_actions": 0, "changed_rows": 0, "rows_dropped": 0},
    }

    for spec in [*CSV_SOURCES, *JSONL_SOURCES]:
        if not spec.path.exists():
            summary["files"][spec.filename] = {"status": "missing"}
            continue

        if spec.filename.endswith(".csv"):
            fieldnames, rows, has_bom = read_csv_source(spec.path)
            if "company_id" not in fieldnames and "related_company_id" not in fieldnames and "product_family_id" not in fieldnames:
                summary["files"][spec.filename] = {"status": "skipped_no_reference_fields", "rows": len(rows)}
                continue
            processed, counter, changed_rows = process_rows(rows, spec, refs, audit_rows)
            if args.apply and (changed_rows or counter.get("rows_dropped")):
                backup = backup_file(spec.path, timestamp)
                write_csv_source(spec.path, fieldnames, processed, has_bom)
            else:
                backup = None
        else:
            rows = read_jsonl_source(spec.path)
            if not rows:
                summary["files"][spec.filename] = {"status": "empty"}
                continue
            if not any("company_id" in row or "related_company_id" in row or "product_family_id" in row for row in rows):
                summary["files"][spec.filename] = {"status": "skipped_no_reference_fields", "rows": len(rows)}
                continue
            processed, counter, changed_rows = process_rows(rows, spec, refs, audit_rows)
            if args.apply and (changed_rows or counter.get("rows_dropped")):
                backup = backup_file(spec.path, timestamp)
                write_jsonl_source(spec.path, processed)
            else:
                backup = None

        file_summary = {
            "status": "changed" if changed_rows or counter.get("rows_dropped") else "unchanged",
            "input_rows": len(rows),
            "output_rows": len(processed),
            "changed_rows": changed_rows,
            "actions": dict(counter),
        }
        if backup:
            file_summary["backup"] = str(backup)
        summary["files"][spec.filename] = file_summary
        summary["totals"]["changed_rows"] += changed_rows
        summary["totals"]["rows_dropped"] += int(counter.get("rows_dropped", 0))

    summary["totals"]["audit_actions"] = len(audit_rows)
    summary["totals"]["actions"] = dict(Counter(row["action"] for row in audit_rows))
    write_audit_files(audit_rows, summary)
    print(json.dumps(summary["totals"], ensure_ascii=False, indent=2))
    print(f"audit_plan={AUDIT_DIR / 'reference_key_hygiene_plan_20260615_latest.csv'}")
    print(f"audit_summary={AUDIT_DIR / 'reference_key_hygiene_summary_20260615_latest.json'}")


if __name__ == "__main__":
    main()
