#!/usr/bin/env python3
"""Run side-effect-free guardrail validation for the aesthetics database."""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
DB_PATH = DATA_DIR / "global_aesthetics.db"
JSON_PATH = AUDIT_DIR / "database_guardrail_validation_latest.json"
MD_PATH = AUDIT_DIR / "database_guardrail_validation_latest.md"

ROW_COUNT_MINIMUMS = {
    "company_master": 300,
    "product_master": 900,
    "product_family_master": 900,
    "product_sku_master": 1000,
    "registration_evidence": 1500,
    "product_specification_evidence": 50000,
    "company_official_source_evidence": 25000,
    "official_website_master": 19000,
}

CONSISTENCY_TABLES = [
    "product_specification_evidence",
    "manual_product_fact_evidence",
    "evidence_promotion_log",
]

FTS_SHADOW_TABLE_PREFIXES = ("evidence_fts_",)


def qident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def one(cur: sqlite3.Cursor, sql: str, params: tuple[Any, ...] = ()) -> Any:
    return cur.execute(sql, params).fetchone()[0]


def table_names(cur: sqlite3.Cursor) -> list[str]:
    return [
        row[0]
        for row in cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]


def is_internal_table(table: str) -> bool:
    return table.startswith("sqlite_") or any(table.startswith(prefix) for prefix in FTS_SHADOW_TABLE_PREFIXES)


def table_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    return [row[1] for row in cur.execute(f"PRAGMA table_info({qident(table)})").fetchall()]


def pk_columns(cur: sqlite3.Cursor, table: str) -> list[str]:
    rows = cur.execute(f"PRAGMA table_info({qident(table)})").fetchall()
    return [row[1] for row in sorted(rows, key=lambda item: item[5]) if row_has_pk(row)]


def row_has_pk(row: tuple[Any, ...]) -> bool:
    return bool(row[5])


def add_issue(
    report: dict[str, Any],
    severity: str,
    check_id: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    target = "failures" if severity.lower() in {"critical", "high"} else "warnings"
    report[target].append(
        {
            "severity": severity,
            "check_id": check_id,
            "message": message,
            "details": details or {},
        }
    )


def check_row_counts(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    counts = {}
    for table, minimum in ROW_COUNT_MINIMUMS.items():
        count = one(cur, f"SELECT COUNT(*) FROM {qident(table)}")
        counts[table] = count
        if count < minimum:
            add_issue(
                report,
                "High",
                "row_count_minimum",
                f"{table} has {count} rows, below minimum guardrail {minimum}.",
                {"table": table, "count": count, "minimum": minimum},
            )
    report["checks"]["row_counts"] = counts


def check_primary_keys(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    problems = []
    for table in table_names(cur):
        if is_internal_table(table):
            continue
        keys = pk_columns(cur, table)
        if not keys:
            continue
        null_conditions = " OR ".join(f"NULLIF(TRIM({qident(col)}), '') IS NULL" for col in keys)
        null_count = one(cur, f"SELECT COUNT(*) FROM {qident(table)} WHERE {null_conditions}")
        group_cols = ", ".join(qident(col) for col in keys)
        duplicate_count = one(
            cur,
            f"""
            SELECT COUNT(*) FROM (
              SELECT {group_cols}, COUNT(*) AS n
              FROM {qident(table)}
              GROUP BY {group_cols}
              HAVING n > 1
            )
            """,
        )
        if null_count or duplicate_count:
            problems.append(
                {
                    "table": table,
                    "pk_columns": keys,
                    "null_pk_rows": null_count,
                    "duplicate_pk_groups": duplicate_count,
                }
            )
    report["checks"]["primary_key_problems"] = problems
    if problems:
        add_issue(
            report,
            "High",
            "primary_key_integrity",
            "One or more primary-key columns have blanks or duplicate groups.",
            {"problems": problems[:20], "problem_count": len(problems)},
        )


def check_foreign_keys(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    refs = {
        "company_master": ("company_master", "company_id"),
        "product_master": ("product_master", "product_id"),
        "product_family_master": ("product_family_master", "product_family_id"),
    }
    orphan_rows = []
    for table in table_names(cur):
        columns = table_columns(cur, table)
        for col in columns:
            parent_table = ""
            parent_col = ""
            if col == "product_id":
                parent_table, parent_col = refs["product_master"]
            elif col == "product_family_id":
                parent_table, parent_col = refs["product_family_master"]
            elif col == "company_id" or col.endswith("_company_id"):
                parent_table, parent_col = refs["company_master"]
            if not parent_table:
                continue
            count = one(
                cur,
                f"""
                SELECT COUNT(*)
                FROM {qident(table)} AS child
                WHERE NULLIF(TRIM(child.{qident(col)}), '') IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM {qident(parent_table)} AS parent
                    WHERE parent.{qident(parent_col)} = child.{qident(col)}
                  )
                """,
            )
            if count:
                orphan_rows.append(
                    {
                        "table": table,
                        "column": col,
                        "parent_table": parent_table,
                        "orphan_rows": count,
                    }
                )
    report["checks"]["foreign_key_orphans"] = orphan_rows
    if orphan_rows:
        add_issue(
            report,
            "High",
            "foreign_key_orphans",
            "Orphan reference keys remain in generated database tables.",
            {"orphan_rows": orphan_rows},
        )


def check_owner_consistency(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    problems = {}

    problems["sku_family_company_mismatch"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM product_sku_master AS sku
        JOIN product_family_master AS fam
          ON fam.product_family_id = sku.product_family_id
        WHERE NULLIF(TRIM(sku.company_id), '') IS NOT NULL
          AND NULLIF(TRIM(fam.company_id), '') IS NOT NULL
          AND sku.company_id <> fam.company_id
          AND NULLIF(TRIM(sku.duplicate_of_record_id), '') IS NULL
          AND COALESCE(sku.review_status, '') <> 'duplicate_non_primary'
        """,
    )
    problems["duplicate_or_affiliate_sku_family_cross_company"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM product_sku_master AS sku
        JOIN product_family_master AS fam
          ON fam.product_family_id = sku.product_family_id
        WHERE NULLIF(TRIM(sku.company_id), '') IS NOT NULL
          AND NULLIF(TRIM(fam.company_id), '') IS NOT NULL
          AND sku.company_id <> fam.company_id
          AND (
            NULLIF(TRIM(sku.duplicate_of_record_id), '') IS NOT NULL
            OR COALESCE(sku.review_status, '') = 'duplicate_non_primary'
          )
        """,
    )
    problems["product_sku_company_mismatch"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM product_master AS prod
        JOIN product_sku_master AS sku
          ON sku.sku_id = prod.product_id
        WHERE NULLIF(TRIM(prod.company_id), '') IS NOT NULL
          AND NULLIF(TRIM(sku.company_id), '') IS NOT NULL
          AND prod.company_id <> sku.company_id
        """,
    )
    problems["products_without_sku_row"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM product_master AS prod
        WHERE NOT EXISTS (
          SELECT 1 FROM product_sku_master AS sku
          WHERE sku.sku_id = prod.product_id
        )
        """,
    )

    evidence_mismatches = {}
    for table in CONSISTENCY_TABLES:
        evidence_mismatches[f"{table}.product_family_vs_product"] = one(
            cur,
            f"""
            SELECT COUNT(*)
            FROM {qident(table)} AS ev
            JOIN product_sku_master AS sku
              ON sku.sku_id = ev.product_id
            WHERE NULLIF(TRIM(ev.product_family_id), '') IS NOT NULL
              AND NULLIF(TRIM(sku.product_family_id), '') IS NOT NULL
              AND ev.product_family_id <> sku.product_family_id
            """,
        )
        evidence_mismatches[f"{table}.company_vs_product"] = one(
            cur,
            f"""
            SELECT COUNT(*)
            FROM {qident(table)} AS ev
            JOIN product_sku_master AS sku
              ON sku.sku_id = ev.product_id
            WHERE NULLIF(TRIM(ev.company_id), '') IS NOT NULL
              AND NULLIF(TRIM(sku.company_id), '') IS NOT NULL
              AND ev.company_id <> sku.company_id
            """,
        )

    evidence_mismatches["registration_evidence.company_vs_product"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM registration_evidence AS reg
        JOIN product_master AS prod
          ON prod.product_id = reg.product_id
        WHERE NULLIF(TRIM(reg.company_id), '') IS NOT NULL
          AND NULLIF(TRIM(prod.company_id), '') IS NOT NULL
          AND reg.company_id <> prod.company_id
        """,
    )
    problems["evidence_mismatches"] = evidence_mismatches
    report["checks"]["owner_consistency"] = problems

    high_problem_items = {
        key: value
        for key, value in {**problems, **evidence_mismatches}.items()
        if isinstance(value, int)
        and value
        and key != "duplicate_or_affiliate_sku_family_cross_company"
    }
    if high_problem_items:
        add_issue(
            report,
            "High",
            "owner_consistency",
            "Some product/family/company references point to inconsistent owners.",
            {"problem_counts": high_problem_items},
        )


def check_usability(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    missing = one(cur, "SELECT COUNT(*) FROM data_usability_missing_owner")
    ledger_issues = one(
        cur,
        """
        SELECT COUNT(*)
        FROM data_usability_ledger
        WHERE missing_owner_rows > 0 OR missing_status_rows > 0
        """,
    )
    report["checks"]["data_usability"] = {
        "missing_owner_rows": missing,
        "ledger_tables_with_missing_owner_or_status": ledger_issues,
    }
    if missing or ledger_issues:
        add_issue(
            report,
            "High",
            "data_usability_coverage",
            "Data usability ledger has rows without an owner or operational status.",
            {
                "missing_owner_rows": missing,
                "ledger_tables_with_missing_owner_or_status": ledger_issues,
            },
        )


def check_traceability(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    missing_logs = one(
        cur,
        """
        SELECT COUNT(*)
        FROM manual_product_fact_evidence AS fact
        WHERE fact.review_status = 'promoted_to_product_master'
          AND NOT EXISTS (
            SELECT 1
            FROM evidence_promotion_log AS log
            WHERE log.product_id = fact.product_id
              AND log.source_key = fact.source_url
              AND log.field_name = fact.field_name
          )
        """,
    )
    report["checks"]["traceability"] = {"promoted_fact_missing_logs": missing_logs}
    if missing_logs:
        add_issue(
            report,
            "High",
            "promoted_fact_traceability",
            "Promoted product facts are missing matching evidence promotion log rows.",
            {"missing_logs": missing_logs},
        )


def check_business_caveats(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    caveats = {}
    caveats["listed_company_batch_blank_company_id"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM listed_company_batch
        WHERE NULLIF(TRIM(company_id), '') IS NULL
        """,
    )
    caveats["company_financial_metrics_blank_company_id"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM company_financial_metrics
        WHERE NULLIF(TRIM(company_id), '') IS NULL
        """,
    )
    caveats["registration_needs_review"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM registration_evidence
        WHERE review_status LIKE '%needs_review%'
           OR review_status = 'manual_new_product_candidate'
        """,
    )
    caveats["duplicate_or_affiliate_sku_family_cross_company"] = report["checks"].get("owner_consistency", {}).get(
        "duplicate_or_affiliate_sku_family_cross_company",
        0,
    )
    caveats["public_companies_without_aesthetics_revenue_pct"] = one(
        cur,
        """
        SELECT COUNT(*)
        FROM companies
        WHERE LOWER(ownership) = 'public'
          AND NULLIF(TRIM(aesthetics_revenue_pct), '') IS NULL
        """,
    )
    report["checks"]["business_caveats"] = caveats
    for key, value in caveats.items():
        if value:
            add_issue(
                report,
                "Medium",
                key,
                "This is not an integrity failure, but it is a stakeholder caveat for interpretation.",
                {"count": value},
            )


def check_nul_bytes(report: dict[str, Any]) -> None:
    problem_files = []
    for pattern in ("*.csv", "*.jsonl"):
        for path in sorted(DATA_DIR.glob(pattern)):
            name = path.name.lower()
            if "_backup_" in name or ".backup_" in name:
                continue
            data = path.read_bytes()
            nul_count = data.count(b"\x00")
            if nul_count:
                problem_files.append({"path": str(path), "nul_bytes": nul_count})
    report["checks"]["nul_bytes"] = problem_files
    if problem_files:
        add_issue(
            report,
            "High",
            "nul_bytes_in_active_sources",
            "Active CSV/JSONL source files contain NUL bytes and may break parsers.",
            {"files": problem_files},
        )


def check_database_nul_text(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    problems = []
    for table in table_names(cur):
        if is_internal_table(table):
            continue
        text_columns = [
            row[1]
            for row in cur.execute(f"PRAGMA table_info({qident(table)})").fetchall()
            if "TEXT" in (row[2] or "").upper()
        ]
        for col in text_columns:
            count = one(
                cur,
                f"""
                SELECT COUNT(*)
                FROM {qident(table)}
                WHERE {qident(col)} IS NOT NULL
                  AND instr({qident(col)}, char(0)) > 0
                """,
            )
            if count:
                problems.append({"table": table, "column": col, "rows": count})
    report["checks"]["database_nul_text"] = problems
    if problems:
        add_issue(
            report,
            "High",
            "database_nul_text",
            "SQLite text fields contain NUL bytes.",
            {"columns": problems},
        )


def check_sqlite_declared_fks(cur: sqlite3.Cursor, report: dict[str, Any]) -> None:
    fk_tables = []
    for table in table_names(cur):
        if is_internal_table(table):
            continue
        fks = cur.execute(f"PRAGMA foreign_key_list({qident(table)})").fetchall()
        if fks:
            fk_tables.append({"table": table, "declared_foreign_keys": len(fks)})
    report["checks"]["declared_foreign_keys"] = fk_tables
    if not fk_tables:
        add_issue(
            report,
            "Low",
            "sqlite_declared_foreign_keys",
            "SQLite tables do not declare foreign keys; referential integrity is enforced by guardrail scripts instead.",
            {},
        )


def check_source_file_parsing(report: dict[str, Any]) -> None:
    parse_errors = []
    for path in sorted(DATA_DIR.glob("*.csv")):
        name = path.name.lower()
        if "_backup_" in name or ".backup_" in name:
            continue
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for _ in csv.DictReader(handle):
                    pass
        except Exception as exc:  # pragma: no cover - defensive report path
            parse_errors.append({"path": str(path), "error": str(exc)})
    for path in sorted(DATA_DIR.glob("*.jsonl")):
        name = path.name.lower()
        if "_backup_" in name or ".backup_" in name:
            continue
        try:
            with path.open("r", encoding="utf-8-sig") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if line.strip():
                        json.loads(line)
        except Exception as exc:  # pragma: no cover - defensive report path
            parse_errors.append({"path": str(path), "error": str(exc), "line": line_number})
    report["checks"]["source_parse_errors"] = parse_errors
    if parse_errors:
        add_issue(
            report,
            "High",
            "source_parse_errors",
            "Active source CSV/JSONL files failed parser checks.",
            {"errors": parse_errors},
        )


def write_outputs(report: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    report["overall_assessment"] = "Ready to share" if not report["failures"] else "Needs revision"
    report["failure_count"] = len(report["failures"])
    report["warning_count"] = len(report["warnings"])
    JSON_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Database Guardrail Validation",
        "",
        f"- Generated at: {report['generated_at']}",
        f"- Database: `{report['database']}`",
        f"- Overall assessment: **{report['overall_assessment']}**",
        f"- Failures: {report['failure_count']}",
        f"- Warnings/caveats: {report['warning_count']}",
        "",
        "## Failures",
    ]
    if report["failures"]:
        for item in report["failures"]:
            lines.append(f"- [{item['severity']}] {item['check_id']}: {item['message']}")
    else:
        lines.append("- None")
    lines.extend(["", "## Warnings And Caveats"])
    if report["warnings"]:
        for item in report["warnings"]:
            detail = item.get("details") or {}
            suffix = f" Details: `{json.dumps(detail, ensure_ascii=False)}`" if detail else ""
            lines.append(f"- [{item['severity']}] {item['check_id']}: {item['message']}{suffix}")
    else:
        lines.append("- None")
    lines.extend(["", "## Key Check Results"])
    for key in [
        "row_counts",
        "foreign_key_orphans",
        "owner_consistency",
        "data_usability",
        "traceability",
        "nul_bytes",
        "database_nul_text",
        "source_parse_errors",
    ]:
        lines.append(f"- `{key}`: `{json.dumps(report['checks'].get(key), ensure_ascii=False)}`")
    MD_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(DB_PATH),
        "checks": {},
        "failures": [],
        "warnings": [],
    }
    if not DB_PATH.exists():
        add_issue(report, "High", "missing_database", "Database file does not exist.", {"path": str(DB_PATH)})
        write_outputs(report)
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        check_row_counts(cur, report)
        check_primary_keys(cur, report)
        check_foreign_keys(cur, report)
        check_owner_consistency(cur, report)
        check_usability(cur, report)
        check_traceability(cur, report)
        check_business_caveats(cur, report)
        check_nul_bytes(report)
        check_database_nul_text(cur, report)
        check_source_file_parsing(report)
        check_sqlite_declared_fks(cur, report)
    finally:
        conn.close()

    write_outputs(report)
    print(json.dumps(
        {
            "overall_assessment": report["overall_assessment"],
            "failure_count": report["failure_count"],
            "warning_count": report["warning_count"],
            "json_path": str(JSON_PATH),
            "markdown_path": str(MD_PATH),
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 1 if report["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
