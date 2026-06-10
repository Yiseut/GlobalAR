#!/usr/bin/env python3
"""Repair conservative, already-verified staging-to-product links.

This script only handles deterministic link repairs where the source record,
company, product name, and current Product_Master row make the target clear.
It does not promote candidate evidence or infer new products.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STAGING_PATH = DATA_DIR / "verification_evidence_staging.jsonl"
REPORT_PATH = DATA_DIR / "audits" / "verified_staging_link_fixes_latest.md"


FIXES = [
    {
        "source_key": "fda_openfda_510k",
        "source_record_id": "K203441",
        "company_id": "co_83052922054b",
        "old_product_id": "prod_7fb0f117908c",
        "new_product_id": "prod_fe1881c6377d",
        "new_brand": "Alma Hybrid",
        "reason": "Alma Hybrid current Product_Master row is REC_0847 / prod_fe1881c6377d; old staging product_id no longer exists.",
    }
]


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing staging file: {path}")
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    text = "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows)
    path.write_text(text + ("\n" if text else ""), encoding="utf-8")


def apply_fixes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    changed: list[dict[str, Any]] = []
    fixed_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    for row in rows:
        for fix in FIXES:
            if norm(row.get("source_key")) != fix["source_key"]:
                continue
            if norm(row.get("source_record_id")) != fix["source_record_id"]:
                continue
            if norm(row.get("company_id")) != fix["company_id"]:
                continue
            if norm(row.get("product_id")) != fix["old_product_id"]:
                continue
            row["product_id"] = fix["new_product_id"]
            row["brand"] = fix["new_brand"]
            row["link_fix_note"] = fix["reason"]
            row["link_fixed_at"] = fixed_at
            changed.append(
                {
                    "source_record_id": fix["source_record_id"],
                    "company_id": fix["company_id"],
                    "old_product_id": fix["old_product_id"],
                    "new_product_id": fix["new_product_id"],
                    "brand": fix["new_brand"],
                    "reason": fix["reason"],
                    "fixed_at": fixed_at,
                }
            )
    return changed


def write_report(changed: list[dict[str, Any]]) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Verified staging link fixes",
        "",
        f"- Generated at: {datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}",
        f"- Changed rows: {len(changed)}",
        "",
    ]
    if changed:
        lines.extend(["| source_record_id | old_product_id | new_product_id | brand | reason |", "|---|---|---|---|---|"])
        for row in changed:
            lines.append(
                "| "
                + " | ".join(
                    [
                        row["source_record_id"],
                        row["old_product_id"],
                        row["new_product_id"],
                        row["brand"],
                        row["reason"],
                    ]
                )
                + " |"
            )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    rows = load_jsonl(STAGING_PATH)
    changed = apply_fixes(rows)
    if changed:
        write_jsonl(STAGING_PATH, rows)
    write_report(changed)
    print(json.dumps({"changed_rows": len(changed), "report": str(REPORT_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
