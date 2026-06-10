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
BRIEFING = DATA_DIR / "briefing_update_candidates.csv"
PRODUCT_MASTER = DATA_DIR / "product_master.csv"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    _, active_rows = read_csv(PRODUCT_MASTER)
    active_ids = {clean(row.get("product_id")) for row in active_rows if clean(row.get("product_id"))}

    fields, rows = read_csv(BRIEFING)
    backup = BRIEFING.with_name(f"{BRIEFING.stem}_backup_before_next_confirmation_unlink_{stamp}{BRIEFING.suffix}")
    shutil.copy2(BRIEFING, backup)

    counts: Counter[str] = Counter()
    changed = []
    for row in rows:
        product_id = clean(row.get("product_id"))
        if not product_id or product_id in active_ids:
            continue
        counts[product_id] += 1
        changed.append(
            {
                "candidate_id": clean(row.get("candidate_id")),
                "product_id": product_id,
                "company": clean(row.get("company")),
                "brand": clean(row.get("brand")),
                "product_name": clean(row.get("product_name")),
                "old_status": clean(row.get("status")),
                "old_promotion_target": clean(row.get("promotion_target")),
            }
        )
        row["product_id"] = ""
        row["status"] = "excluded_scope_unlinked"
        row["promotion_target"] = "excluded_or_noise"

    write_csv(BRIEFING, fields, rows)

    summary = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "file": str(BRIEFING),
        "backup": str(backup),
        "rows_unlinked": len(changed),
        "by_original_product_id": dict(counts),
        "sample": changed[:50],
    }
    latest = AUDIT_DIR / "briefing_update_candidates_next_confirmation_unlink_latest.json"
    stamped = AUDIT_DIR / f"briefing_update_candidates_next_confirmation_unlink_{stamp}.json"
    latest.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    stamped.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
