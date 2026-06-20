#!/usr/bin/env python3
"""Validate the commercial evidence layer after build_data.py."""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "data" / "global_aesthetics.db"
SNAPSHOT_PATH = PROJECT_DIR / "web" / "v3" / "v3-market-intelligence.js"
REQUIRED_TABLES = [
    "commercial_source_documents",
    "commercial_claims",
    "commercial_conflict_groups",
    "commercial_data_source_registry",
    "commercial_data_collection_backlog",
]


def scalar(cur: sqlite3.Cursor, sql: str, params: tuple = ()) -> int:
    row = cur.execute(sql, params).fetchone()
    return int(row[0] if row else 0)


def load_snapshot() -> dict:
    if not SNAPSHOT_PATH.exists():
        return {}
    text = SNAPSHOT_PATH.read_text(encoding="utf-8")
    match = re.search(r"window\.V3_MARKET_INTELLIGENCE_DATA\s*=\s*(\{.*\});\s*$", text, re.S)
    if not match:
        return {}
    return json.loads(match.group(1))


def main() -> int:
    if not DB_PATH.exists():
        print(json.dumps({"status": "failed", "error": f"missing database: {DB_PATH}"}, ensure_ascii=False, indent=2))
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        tables = {row[0] for row in cur.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing_tables = [table for table in REQUIRED_TABLES if table not in tables]
        checks = {
            "missing_tables": len(missing_tables),
        }
        if missing_tables:
            result = {"status": "failed", "missing_tables": missing_tables, "checks": checks}
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1

        counts = {
            table: scalar(cur, f"SELECT COUNT(*) FROM {table}")
            for table in REQUIRED_TABLES
        }
        checks.update(
            {
                "claims_missing_source": scalar(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM commercial_claims c
                    LEFT JOIN commercial_source_documents s
                      ON c.source_document_id = s.source_document_id
                    WHERE c.source_document_id IS NULL
                       OR trim(c.source_document_id) = ''
                       OR s.source_document_id IS NULL
                    """,
                ),
                "claims_missing_confidence": scalar(
                    cur,
                    "SELECT COUNT(*) FROM commercial_claims WHERE confidence IS NULL OR trim(confidence) = ''",
                ),
                "claims_missing_review_status": scalar(
                    cur,
                    "SELECT COUNT(*) FROM commercial_claims WHERE review_status IS NULL OR trim(review_status) = ''",
                ),
                "numeric_claims_missing_unit_or_period": scalar(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM commercial_claims
                    WHERE value IS NOT NULL
                      AND (
                        unit IS NULL OR trim(unit) = ''
                        OR ((year IS NULL OR year = 0) AND (period IS NULL OR trim(period) = ''))
                      )
                    """,
                ),
                "conflict_groups_mixed_scope_guard": scalar(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM commercial_conflict_groups
                    WHERE unit IS NULL OR trim(unit) = ''
                       OR year IS NULL OR year = 0
                       OR geo IS NULL OR trim(geo) = ''
                    """,
                ),
                "trusted_daily_signals": scalar(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM commercial_claims
                    WHERE claim_type = 'briefing_signal'
                      AND confidence LIKE 'trusted_daily_signal%'
                    """,
                ),
                "commercial_data_source_registry_rows": scalar(
                    cur,
                    "SELECT COUNT(*) FROM commercial_data_source_registry",
                ),
                "commercial_data_collection_backlog_rows": scalar(
                    cur,
                    "SELECT COUNT(*) FROM commercial_data_collection_backlog",
                ),
                "commercial_backlog_unknown_source_ids": scalar(
                    cur,
                    """
                    SELECT COUNT(*)
                    FROM commercial_data_collection_backlog b
                    LEFT JOIN commercial_data_source_registry r
                      ON b.source_id = r.source_id
                    WHERE b.source_id IS NULL
                       OR trim(b.source_id) = ''
                       OR r.source_id IS NULL
                    """,
                ),
            }
        )
        source_roots = [
            {"source_root": row[0], "count": row[1]}
            for row in cur.execute(
                """
                SELECT source_root, COUNT(*)
                FROM commercial_source_documents
                GROUP BY source_root
                ORDER BY COUNT(*) DESC, source_root
                """
            )
        ]
    finally:
        conn.close()

    snapshot = load_snapshot()
    snapshot_keys = sorted(snapshot.keys())
    checks["snapshot_present"] = 1 if snapshot else 0
    checks["snapshot_interface_keys"] = int(
        all(
            key in snapshot
            for key in [
                "summary",
                "marketMetrics",
                "financialSnapshots",
                "briefingSignals",
                "conflictGroups",
                "sourceDocuments",
                "reviewQueues",
            ]
        )
    )

    blocking = [
        key
        for key in [
            "missing_tables",
            "claims_missing_source",
            "claims_missing_confidence",
            "claims_missing_review_status",
            "commercial_backlog_unknown_source_ids",
        ]
        if checks.get(key, 0)
    ]
    if checks.get("commercial_data_source_registry_rows", 0) <= 0:
        blocking.append("commercial_data_source_registry_rows")
    if checks.get("commercial_data_collection_backlog_rows", 0) <= 0:
        blocking.append("commercial_data_collection_backlog_rows")
    if checks.get("snapshot_present") != 1 or checks.get("snapshot_interface_keys") != 1:
        blocking.append("snapshot_interface")

    result = {
        "status": "passed" if not blocking else "failed",
        "counts": counts,
        "checks": checks,
        "blocking_checks": blocking,
        "source_roots": source_roots,
        "snapshot_keys": snapshot_keys,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blocking else 1


if __name__ == "__main__":
    sys.exit(main())
