"""
Close historical evidence_staging needs_review rows that are already represented
by promoted FDA registration evidence.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "global_aesthetics.db"
STAGING_PATH = ROOT / "data" / "verification_evidence_staging.jsonl"
AUDIT_DIR = ROOT / "data" / "audits"
RUN_ID = "codex_duplicate_staging_close_20260602"
TZ = timezone(timedelta(hours=8))


def load_closable_keys() -> set[tuple[str, str, str]]:
    query = """
        select distinct
            es.source_record_id,
            es.product_id,
            es.company_id
        from evidence_staging es
        where es.review_status = 'needs_review'
          and es.merge_target = 'registration_evidence'
          and exists (
              select 1
              from registration_evidence re
              where re.registration_no = es.source_record_id
                and re.product_id = es.product_id
                and coalesce(re.review_status, '') <> 'needs_review'
          )
    """
    with sqlite3.connect(DB_PATH) as conn:
        return {
            (str(row[0] or ""), str(row[1] or ""), str(row[2] or ""))
            for row in conn.execute(query)
        }


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)
    if not STAGING_PATH.exists():
        raise FileNotFoundError(STAGING_PATH)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    now = datetime.now(TZ).replace(microsecond=0).isoformat()
    closable_keys = load_closable_keys()

    if not closable_keys:
        print(json.dumps({"closed": 0, "reason": "no_closable_rows"}, ensure_ascii=False))
        return

    backup_path = AUDIT_DIR / f"verification_evidence_staging.backup_before_duplicate_close_20260602_{datetime.now(TZ):%H%M%S}.jsonl"
    shutil.copy2(STAGING_PATH, backup_path)

    closed = 0
    total = 0
    samples: list[dict[str, str]] = []
    rewritten_lines: list[str] = []

    with STAGING_PATH.open("r", encoding="utf-8") as fh:
        for line in fh:
            total += 1
            item = json.loads(line)
            key = (
                str(item.get("source_record_id") or ""),
                str(item.get("product_id") or ""),
                str(item.get("company_id") or ""),
            )
            if (
                item.get("review_status") == "needs_review"
                and item.get("merge_target") == "registration_evidence"
                and key in closable_keys
            ):
                item["review_status"] = "auto_closed_duplicate_promoted_registration"
                item["merge_status"] = "closed_duplicate_promoted_registration"
                item["reviewed_by"] = RUN_ID
                item["reviewed_at"] = now
                item["review_note"] = (
                    "Closed from staging queue because the same FDA registration number "
                    "is already represented in registration_evidence with non-needs_review status."
                )
                closed += 1
                if len(samples) < 10:
                    samples.append(
                        {
                            "source_record_id": key[0],
                            "product_id": key[1],
                            "company_id": key[2],
                        }
                    )
            rewritten_lines.append(json.dumps(item, ensure_ascii=False, separators=(",", ":")))

    STAGING_PATH.write_text("\n".join(rewritten_lines) + "\n", encoding="utf-8")

    audit_path = AUDIT_DIR / "staging_duplicate_close_20260602_latest.json"
    audit = {
        "run_id": RUN_ID,
        "closed_at": now,
        "source": str(STAGING_PATH.relative_to(ROOT)),
        "backup": str(backup_path.relative_to(ROOT)),
        "total_lines": total,
        "closable_keys": len(closable_keys),
        "closed_rows": closed,
        "selection_rule": (
            "evidence_staging.review_status='needs_review' and merge_target='registration_evidence' "
            "and same registration_no/product_id exists in registration_evidence with non-needs_review status"
        ),
        "samples": samples,
    }
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
