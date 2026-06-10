#!/usr/bin/env python3
"""Self-check the v4 data-completeness convergence goal.

The checks in this file are intentionally acceptance-oriented. They do not
replace the broader usability ledger; they answer whether the current database
snapshot satisfies the hard gates requested for the v4 convergence goal.
"""

from __future__ import annotations

import csv
import json
import sqlite3
import sys
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
DB_PATH = DATA_DIR / "global_aesthetics.db"

SPEC_OPERATIONAL_STATUS_PATH = AUDIT_DIR / "product_spec_operational_status_latest.csv"
SPEC_PROMOTION_PATH = AUDIT_DIR / "product_spec_promotion_latest.csv"
NMPA_MATCH_PATH = AUDIT_DIR / "nmpa_registration_project_match_latest.csv"
NMPA_SUPPLEMENT_APPLY_PATH = AUDIT_DIR / "nmpa_supplement_product_line_apply_latest.csv"
NMPA_SUPPLEMENT_ARCHIVE_GLOB = PROJECT_DIR / "_archive" / "audits_verified_intermediate_*" / "nmpa_supplement_product_line_apply_latest.csv"

MANUAL_PRODUCT_FACT_PATH = DATA_DIR / "manual_product_fact_evidence.csv"
EVIDENCE_PROMOTION_LOG_PATHS = [
    DATA_DIR / "evidence_promotion_log.csv",
    DATA_DIR / "manual_evidence_promotion_log.csv",
]
MANUAL_NMPA_PATH = DATA_DIR / "manual_nmpa_registration_evidence.csv"

SUMMARY_JSON_PATH = AUDIT_DIR / "v4_acceptance_self_check_latest.json"
SUMMARY_MD_PATH = AUDIT_DIR / "v4_acceptance_self_check_latest.md"


BAD_MATERIAL_REVIEW_STATUSES = {"needs_review", "pending_review", "pending_subclass"}
SKU_CANDIDATE_STATUSES = {
    "variant_split_candidate",
    "family_multi_sku_candidate",
    "sku_split_from_family_candidate",
}
REGISTRATION_FOLLOWUP_STATUSES = {"needs_source_followup", "pdf_indication_not_found"}
RESOLVED_STATUSES = {"resolved", "closed", "fixed", "accepted", "done"}


@dataclass
class Metric:
    section: str
    metric_id: str
    label: str
    current_value: str
    threshold: str
    passed: bool
    details: dict[str, Any]
    next_action: str


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def lower(value: Any) -> str:
    return norm(value).casefold()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_nmpa_supplement_rows() -> tuple[list[dict[str, str]], str]:
    rows = read_csv_rows(NMPA_SUPPLEMENT_APPLY_PATH)
    if rows:
        return rows, str(NMPA_SUPPLEMENT_APPLY_PATH)
    archive_paths = sorted(PROJECT_DIR.glob(str(NMPA_SUPPLEMENT_ARCHIVE_GLOB.relative_to(PROJECT_DIR))))
    for path in reversed(archive_paths):
        rows = read_csv_rows(path)
        if rows:
            return rows, str(path)
    return [], str(NMPA_SUPPLEMENT_APPLY_PATH)


def write_csv(path: Path, fieldnames: Iterable[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def pct(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator * 100.0 / denominator


def pct_text(numerator: int, denominator: int) -> str:
    return f"{pct(numerator, denominator):.1f}% ({numerator}/{denominator})"


def add_metric(
    metrics: list[Metric],
    section: str,
    metric_id: str,
    label: str,
    current_value: str,
    threshold: str,
    passed: bool,
    details: dict[str, Any] | None = None,
    next_action: str = "",
) -> None:
    metrics.append(
        Metric(
            section=section,
            metric_id=metric_id,
            label=label,
            current_value=current_value,
            threshold=threshold,
            passed=bool(passed),
            details=details or {},
            next_action=next_action,
        )
    )


def scalar(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> Any:
    return con.execute(sql, params).fetchone()[0]


def rows(con: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    return [dict(row) for row in con.execute(sql, params).fetchall()]


def table_columns(con: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()]


def all_tables(con: sqlite3.Connection) -> list[str]:
    return [
        row[0]
        for row in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
    ]


def active_product_where(alias: str = "pm") -> str:
    return f"lower(coalesce({alias}.inclusion_status, '')) = 'active'"


def nonempty_sql(column: str) -> str:
    return f"trim(coalesce({column}, '')) <> ''"


def top_statuses(con: sqlite3.Connection, table: str, status_col: str, where: str = "1=1") -> list[dict[str, Any]]:
    return rows(
        con,
        f"""
        SELECT coalesce({status_col}, '') AS status, count(*) AS count
        FROM {table}
        WHERE {where}
        GROUP BY coalesce({status_col}, '')
        ORDER BY count DESC, status
        LIMIT 12
        """,
    )


def check_data_consistency(con: sqlite3.Connection, metrics: list[Metric]) -> None:
    duplicate_groups = rows(
        con,
        f"""
        WITH active AS (
            SELECT
                lower(trim(coalesce(brand, ''))) AS brand_norm,
                lower(trim(coalesce(standard_product_name, ''))) AS product_norm,
                group_concat(DISTINCT company) AS companies,
                group_concat(DISTINCT product_id) AS product_ids,
                count(DISTINCT lower(trim(coalesce(company, '')))) AS company_count,
                count(*) AS row_count
            FROM product_master
            WHERE {active_product_where('product_master')}
              AND {nonempty_sql('brand')}
              AND {nonempty_sql('standard_product_name')}
            GROUP BY brand_norm, product_norm
            HAVING count(DISTINCT lower(trim(coalesce(company, '')))) > 1
        )
        SELECT * FROM active
        ORDER BY company_count DESC, row_count DESC, brand_norm, product_norm
        """,
    )
    add_metric(
        metrics,
        "A",
        "A1_duplicate_active_product_groups",
        "No duplicate active products across companies by normalized brand + standard_product_name",
        str(len(duplicate_groups)),
        "= 0 duplicate groups",
        len(duplicate_groups) == 0,
        {"sample_groups": duplicate_groups[:20]},
        "Merge or soft-delete duplicate Product_Master rows and retarget references.",
    )

    active_total = scalar(con, f"SELECT count(*) FROM product_master pm WHERE {active_product_where()}")
    missing_company = scalar(
        con,
        f"SELECT count(*) FROM product_master pm WHERE {active_product_where()} AND NOT ({nonempty_sql('pm.company')})",
    )
    missing_legal = scalar(
        con,
        f"SELECT count(*) FROM product_master pm WHERE {active_product_where()} AND NOT ({nonempty_sql('pm.legal_manufacturer')})",
    )
    missing_marketing = scalar(
        con,
        f"SELECT count(*) FROM product_master pm WHERE {active_product_where()} AND NOT ({nonempty_sql('pm.marketing_holder')})",
    )
    complete_rows = scalar(
        con,
        f"""
        SELECT count(*)
        FROM product_master pm
        WHERE {active_product_where()}
          AND {nonempty_sql('pm.company')}
          AND {nonempty_sql('pm.legal_manufacturer')}
          AND {nonempty_sql('pm.marketing_holder')}
        """,
    )
    add_metric(
        metrics,
        "A",
        "A2_active_product_ownership_completeness",
        "Active products have company, legal_manufacturer, and marketing_holder",
        pct_text(complete_rows, active_total),
        "100%",
        active_total > 0 and complete_rows == active_total,
        {
            "active_products": active_total,
            "missing_company": missing_company,
            "missing_legal_manufacturer": missing_legal,
            "missing_marketing_holder": missing_marketing,
        },
        "Backfill legal manufacturer and marketing holder from registration/official sources.",
    )

    orphan_details: list[dict[str, Any]] = []
    total_orphans = 0
    deleted_refs = 0
    for table in all_tables(con):
        if table == "product_master":
            continue
        if "product_id" not in table_columns(con, table):
            continue
        orphan_count = scalar(
            con,
            f"""
            SELECT count(*)
            FROM {table} t
            LEFT JOIN product_master pm ON pm.product_id = t.product_id
            WHERE {nonempty_sql('t.product_id')} AND pm.product_id IS NULL
            """,
        )
        deleted_count = scalar(
            con,
            f"""
            SELECT count(*)
            FROM {table} t
            JOIN product_master pm ON pm.product_id = t.product_id
            WHERE {nonempty_sql('t.product_id')}
              AND lower(coalesce(pm.inclusion_status, '')) IN ('deleted', 'excluded')
            """,
        )
        if orphan_count or deleted_count:
            orphan_details.append(
                {"table": table, "orphan_product_id_refs": orphan_count, "deleted_product_refs": deleted_count}
            )
        total_orphans += orphan_count
        deleted_refs += deleted_count
    add_metric(
        metrics,
        "A",
        "A3_evidence_product_id_integrity",
        "Evidence/reference tables have no orphan product_id and no active references to deleted products",
        f"{total_orphans + deleted_refs} issues ({total_orphans} orphan, {deleted_refs} deleted refs)",
        "= 0 issues",
        total_orphans == 0 and deleted_refs == 0,
        {"affected_tables": orphan_details},
        "Retarget evidence rows to active product_id values or mark the evidence inactive/noise.",
    )


def check_master_fill_rates(con: sqlite3.Connection, metrics: list[Metric]) -> None:
    product_total = scalar(con, "SELECT count(*) FROM product_master")
    inclusion_filled = scalar(con, f"SELECT count(*) FROM product_master WHERE {nonempty_sql('inclusion_status')}")
    active_total = scalar(con, f"SELECT count(*) FROM product_master pm WHERE {active_product_where()}")
    material_path_filled = scalar(
        con,
        f"""
        SELECT count(*)
        FROM product_master pm
        WHERE {active_product_where()}
          AND {nonempty_sql('pm.material_taxonomy_path_cn')}
        """,
    )
    add_metric(
        metrics,
        "B",
        "B1_inclusion_and_material_path_coverage",
        "inclusion_status is filled for all Product_Master rows and material_taxonomy_path_cn is filled for active products",
        f"inclusion {pct_text(inclusion_filled, product_total)}; material path {pct_text(material_path_filled, active_total)}",
        "100% / 100%",
        product_total > 0 and inclusion_filled == product_total and material_path_filled == active_total,
        {"product_master_rows": product_total, "active_products": active_total},
        "Preserve existing classification fields when rebuilding Product_Master.",
    )

    bad_status_rows = rows(
        con,
        f"""
        SELECT product_id, company, brand, standard_product_name, material_taxonomy_review_status,
               material_taxonomy_path_cn, search_blob
        FROM product_master pm
        WHERE {active_product_where()}
          AND lower(coalesce(material_taxonomy_review_status, '')) IN ({','.join('?' for _ in BAD_MATERIAL_REVIEW_STATUSES)})
        ORDER BY material_taxonomy_review_status, company, brand
        """,
        tuple(sorted(BAD_MATERIAL_REVIEW_STATUSES)),
    )
    hold_terms = ("微波", "冷冻", "微电流", "microwave", "cryo", "cooling", "microcurrent")
    hold_candidates = [
        row
        for row in bad_status_rows
        if any(term in lower(" ".join(norm(row.get(k)) for k in row)) for term in hold_terms)
    ]
    add_metric(
        metrics,
        "B",
        "B2_material_taxonomy_review_backlog",
        "material_taxonomy_review_status has no needs_review, pending_review, or pending_subclass rows",
        str(len(bad_status_rows)),
        "= 0 backlog rows",
        len(bad_status_rows) == 0,
        {
            "status_counts": top_statuses(con, "product_master", "material_taxonomy_review_status", active_product_where("product_master")),
            "hold_candidate_count": len(hold_candidates),
            "sample_rows": bad_status_rows[:25],
        },
        "Resolve taxonomy backlog; pause only for explicit hold taxonomy decisions.",
    )

    family_filled = scalar(
        con,
        f"""
        SELECT count(*)
        FROM product_master pm
        WHERE {active_product_where()}
          AND {nonempty_sql('pm.material_family')}
        """,
    )
    add_metric(
        metrics,
        "B",
        "B3_material_family_coverage",
        "material_family coverage among active products",
        pct_text(family_filled, active_total),
        ">= 95%",
        pct(family_filled, active_total) >= 95.0,
        {"active_products": active_total, "filled": family_filled},
        "Backfill material_family from confirmed taxonomy/SKU family assignments.",
    )

    regulated_total = scalar(
        con,
        f"""
        SELECT count(DISTINCT pm.product_id)
        FROM product_master pm
        JOIN registration_evidence re ON re.product_id = pm.product_id
        WHERE {active_product_where()}
          AND {nonempty_sql('re.product_id')}
        """,
    )
    regulated_registered = scalar(
        con,
        f"""
        SELECT count(DISTINCT pm.product_id)
        FROM product_master pm
        JOIN registration_evidence re ON re.product_id = pm.product_id
        WHERE {active_product_where()}
          AND {nonempty_sql('re.product_id')}
          AND {nonempty_sql('pm.registered_name')}
        """,
    )
    add_metric(
        metrics,
        "B",
        "B4_registered_name_regulated_subset",
        "registered_name coverage among products with regulatory evidence",
        pct_text(regulated_registered, regulated_total),
        ">= 90%",
        regulated_total > 0 and pct(regulated_registered, regulated_total) >= 90.0,
        {"regulated_products": regulated_total, "registered_name_filled": regulated_registered},
        "Promote registered names from Registration_Evidence into Product_Master.",
    )

    sku_candidate_count = scalar(
        con,
        f"""
        SELECT count(*)
        FROM product_sku_master
        WHERE lower(coalesce(inclusion_status, '')) = 'active'
          AND lower(coalesce(split_status, '')) IN ({','.join('?' for _ in SKU_CANDIDATE_STATUSES)})
        """,
        tuple(sorted(SKU_CANDIDATE_STATUSES)),
    )
    add_metric(
        metrics,
        "B",
        "B5_sku_split_candidate_backlog",
        "Product_SKU_Master split candidates have all been resolved",
        str(sku_candidate_count),
        "= 0 candidate rows",
        sku_candidate_count == 0,
        {"status_counts": top_statuses(con, "product_sku_master", "split_status", "lower(coalesce(inclusion_status, '')) = 'active'")},
        "Execute SKU/family split candidates and mark terminal split_status values.",
    )

    spec_products = scalar(
        con,
        f"""
        SELECT count(DISTINCT pse.product_id)
        FROM product_specification_evidence pse
        JOIN product_master pm ON pm.product_id = pse.product_id
        WHERE {nonempty_sql('pse.product_id')}
          AND {active_product_where()}
        """,
    )
    add_metric(
        metrics,
        "B",
        "B6a_spec_evidence_product_id_mapping",
        "Product_Spec_Evidence product_id-level mapping has expanded beyond the initial 11-product baseline",
        str(spec_products),
        "> 11 products",
        spec_products > 11,
        {"distinct_products_with_product_id_spec_evidence": spec_products},
        "Map family-level spec evidence to product_id before judging technical_specs_json coverage.",
    )

    spec_subset_total = scalar(
        con,
        f"""
        SELECT count(DISTINCT pm.product_id)
        FROM product_master pm
        JOIN product_specification_evidence pse ON pse.product_id = pm.product_id
        WHERE {active_product_where()}
          AND {nonempty_sql('pse.product_id')}
        """,
    )
    spec_subset_filled = scalar(
        con,
        f"""
        SELECT count(DISTINCT pm.product_id)
        FROM product_master pm
        JOIN product_specification_evidence pse ON pse.product_id = pm.product_id
        WHERE {active_product_where()}
          AND {nonempty_sql('pse.product_id')}
          AND {nonempty_sql('pm.technical_specs_json')}
        """,
    )
    add_metric(
        metrics,
        "B",
        "B6b_technical_specs_json_spec_subset",
        "technical_specs_json coverage among products with product_id-level specification evidence",
        pct_text(spec_subset_filled, spec_subset_total),
        ">= 85%",
        spec_subset_total > 0 and pct(spec_subset_filled, spec_subset_total) >= 85.0,
        {"spec_evidence_products": spec_subset_total, "technical_specs_json_filled": spec_subset_filled},
        "Promote verified specification evidence into Product_Master.technical_specs_json.",
    )

    spec_rows = rows(con, "SELECT spec_id, review_status FROM product_specification_evidence")
    promoted_spec_ids = {row.get("spec_id") for row in read_csv_rows(SPEC_PROMOTION_PATH) if row.get("spec_id")}
    converted_spec_ids = {
        row["spec_id"]
        for row in spec_rows
        if row.get("spec_id") and ("cross_checked" in lower(row.get("review_status")) or row.get("spec_id") in promoted_spec_ids)
    }
    conversion_rate = pct(len(converted_spec_ids), len(spec_rows))
    operational_rows = read_csv_rows(SPEC_OPERATIONAL_STATUS_PATH)
    operational_converted = [
        row
        for row in operational_rows
        if "promote" in lower(row.get("operational_status")) or "crosscheck" in lower(row.get("operational_status"))
    ]
    add_metric(
        metrics,
        "B",
        "B6c_spec_candidate_conversion",
        "Product_Spec_Evidence candidate conversion rate (promoted or cross_checked)",
        f"{conversion_rate:.1f}% ({len(converted_spec_ids)}/{len(spec_rows)})",
        ">= 60%",
        conversion_rate >= 60.0,
        {
            "promoted_spec_ids": len(promoted_spec_ids),
            "converted_spec_ids": len(converted_spec_ids),
            "operational_triaged_promote_or_crosscheck_rows": len(operational_converted),
            "operational_status_file_rows": len(operational_rows),
        },
        "Convert raw candidate rows into promoted or cross_checked terminal states.",
    )


def check_regulatory(con: sqlite3.Connection, metrics: list[Metric]) -> None:
    followup_count = scalar(
        con,
        f"""
        SELECT count(*)
        FROM registration_evidence
        WHERE lower(coalesce(review_status, '')) IN ({','.join('?' for _ in REGISTRATION_FOLLOWUP_STATUSES)})
        """,
        tuple(sorted(REGISTRATION_FOLLOWUP_STATUSES)),
    )
    add_metric(
        metrics,
        "C",
        "C1_registration_followup_backlog",
        "Registration_Evidence has no needs_source_followup or pdf_indication_not_found rows",
        str(followup_count),
        "= 0 rows",
        followup_count == 0,
        {"status_counts": top_statuses(con, "registration_evidence", "review_status")},
        "补源；若确实无公开适应症，显式标记为 unavailable_verified/no_public_indication.",
    )

    registration_total = scalar(con, "SELECT count(*) FROM registration_evidence")
    approved_filled = scalar(con, f"SELECT count(*) FROM registration_evidence WHERE {nonempty_sql('approved_indication')}")
    intended_filled = scalar(con, f"SELECT count(*) FROM registration_evidence WHERE {nonempty_sql('intended_use')}")
    approved_pass = pct(approved_filled, registration_total) >= 60.0
    intended_pass = pct(intended_filled, registration_total) >= 60.0
    add_metric(
        metrics,
        "C",
        "C2_registration_indication_coverage",
        "approved_indication and intended_use coverage in Registration_Evidence",
        f"approved_indication {pct_text(approved_filled, registration_total)}; intended_use {pct_text(intended_filled, registration_total)}",
        ">= 60% / >= 60%",
        approved_pass and intended_pass,
        {"registration_rows": registration_total, "approved_indication_filled": approved_filled, "intended_use_filled": intended_filled},
        "Promote official indications from regulator/IFU evidence or mark unavailable after source follow-up.",
    )

    match_rows = read_csv_rows(NMPA_MATCH_PATH)
    supplement_rows, supplement_source = read_nmpa_supplement_rows()
    pending_link_rows = [
        row
        for row in match_rows
        if "review" in lower(row.get("decision")) or "pending" in lower(row.get("decision"))
    ]
    prod_new_count = 0
    for table in ["product_master", "registration_evidence"]:
        if table in all_tables(con):
            prod_new_count += scalar(con, f"SELECT count(*) FROM {table} WHERE product_id LIKE 'prod_NEW%'")
    for row in read_csv_rows(MANUAL_NMPA_PATH):
        if norm(row.get("product_id")).startswith("prod_NEW"):
            prod_new_count += 1
    add_metric(
        metrics,
        "C",
        "C3_nmpa_link_and_supplement_closure",
        "NMPA pending links/supplements are landed with no prod_NEW placeholders",
        f"pending links {len(pending_link_rows)}; supplement rows {len(supplement_rows)}; prod_NEW placeholders {prod_new_count}",
        "pending links = 0; supplement rows >= 18; prod_NEW = 0",
        len(pending_link_rows) == 0 and len(supplement_rows) >= 18 and prod_new_count == 0,
        {
            "supplement_source": supplement_source,
            "match_decision_counts": count_values(match_rows, "decision"),
            "supplement_action_counts": count_values(supplement_rows, "action"),
        },
        "Apply remaining NMPA manual link decisions and replace all prod_NEW placeholders.",
    )


def count_values(items: list[dict[str, str]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        key = norm(item.get(field)) or "(blank)"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def check_company_layer(con: sqlite3.Connection, metrics: list[Metric]) -> None:
    public_where = "lower(coalesce(ownership, '')) = 'public' AND lower(coalesce(status, '')) NOT IN ('deleted', 'excluded')"
    public_total = scalar(con, f"SELECT count(*) FROM companies WHERE {public_where}")
    market_cap_filled = scalar(con, f"SELECT count(*) FROM companies WHERE {public_where} AND {nonempty_sql('market_cap_usd_m')}")
    revenue_filled = scalar(
        con,
        f"""
        SELECT count(*)
        FROM companies
        WHERE {public_where}
          AND {nonempty_sql('revenue_usd_m')}
          AND {nonempty_sql('revenue_year')}
        """,
    )
    stock_filled = scalar(con, f"SELECT count(*) FROM companies WHERE {public_where} AND {nonempty_sql('stock_code')}")
    aesthetics_revenue_filled = scalar(
        con,
        f"SELECT count(*) FROM companies WHERE {public_where} AND {nonempty_sql('aesthetics_revenue_pct')}",
    )
    add_metric(
        metrics,
        "D",
        "D1_public_market_cap_coverage",
        "Market_Cap_USD_M coverage among public companies",
        pct_text(market_cap_filled, public_total),
        "100%",
        public_total > 0 and market_cap_filled == public_total,
        {"public_companies": public_total, "filled": market_cap_filled},
        "Refresh public-company market-cap snapshots for blank rows.",
    )
    add_metric(
        metrics,
        "D",
        "D2_public_revenue_coverage",
        "Revenue_USD_M + Revenue_Year coverage among public companies",
        pct_text(revenue_filled, public_total),
        ">= 90%",
        pct(revenue_filled, public_total) >= 90.0,
        {"public_companies": public_total, "filled": revenue_filled},
        "Collect annual report/XBRL revenue and fiscal year for public companies.",
    )
    add_metric(
        metrics,
        "D",
        "D3_public_stock_code_coverage",
        "Stock_Code coverage among public companies",
        pct_text(stock_filled, public_total),
        "100%",
        public_total > 0 and stock_filled == public_total,
        {"public_companies": public_total, "filled": stock_filled},
        "Backfill exchange/ticker identifiers from listed-company batch evidence.",
    )
    add_metric(
        metrics,
        "D",
        "D4_public_aesthetics_revenue_pct_coverage",
        "Aesthetics_Revenue_Pct coverage among public companies",
        pct_text(aesthetics_revenue_filled, public_total),
        ">= 50%",
        pct(aesthetics_revenue_filled, public_total) >= 50.0,
        {"public_companies": public_total, "filled": aesthetics_revenue_filled},
        "Extract aesthetics segment revenue share from annual report segment notes.",
    )

    known_group_rows = rows(
        con,
        """
        SELECT DISTINCT l.company_id, l.company, l.relation_to_listed_entity,
               l.parent_company_seed, l.ultimate_parent_seed,
               cm.parent_company AS cm_parent, cm.ultimate_parent AS cm_ultimate,
               c.parent_company AS companies_parent
        FROM listed_company_batch l
        LEFT JOIN company_master cm ON cm.company_id = l.company_id
        LEFT JOIN companies c ON lower(c.company) = lower(l.company)
        WHERE trim(coalesce(l.parent_company_seed, '')) <> ''
           OR trim(coalesce(l.ultimate_parent_seed, '')) <> ''
           OR lower(coalesce(l.relation_to_listed_entity, '')) LIKE '%subsidiary%'
           OR lower(coalesce(l.relation_to_listed_entity, '')) LIKE '%affiliate%'
           OR lower(coalesce(l.relation_to_listed_entity, '')) LIKE '%owned%'
           OR lower(coalesce(l.relation_to_listed_entity, '')) LIKE '%group%'
        """,
    )
    known_filled = [
        row
        for row in known_group_rows
        if norm(row.get("cm_parent"))
        or norm(row.get("cm_ultimate"))
        or norm(row.get("companies_parent"))
    ]
    add_metric(
        metrics,
        "D",
        "D5_parent_company_known_group_subset",
        "Parent_Company coverage among known group/subsidiary relationships",
        pct_text(len(known_filled), len(known_group_rows)),
        ">= 90%",
        len(known_group_rows) > 0 and pct(len(known_filled), len(known_group_rows)) >= 90.0,
        {"known_group_rows": len(known_group_rows), "filled": len(known_filled), "sample_missing": [row for row in known_group_rows if row not in known_filled][:20]},
        "Promote parent/ultimate parent from Listed_Company_Batch evidence into company tables.",
    )


def check_process_closure(con: sqlite3.Connection, metrics: list[Metric]) -> None:
    fact_rows = read_csv_rows(MANUAL_PRODUCT_FACT_PATH)
    log_rows: list[dict[str, str]] = []
    for path in EVIDENCE_PROMOTION_LOG_PATHS:
        log_rows.extend(read_csv_rows(path))

    log_keys = {
        (
            norm(row.get("product_id")),
            lower(row.get("field_name")),
            lower(row.get("promoted_value")),
        )
        for row in log_rows
        if norm(row.get("product_id")) and norm(row.get("field_name")) and norm(row.get("promoted_value"))
    }
    missing_log_rows = []
    for row in fact_rows:
        if not norm(row.get("product_id")):
            continue
        if "orphan" in lower(row.get("review_status")) or "unlinked" in lower(row.get("review_status")):
            continue
        key = (
            norm(row.get("product_id")),
            lower(row.get("field_name")),
            lower(row.get("field_value")),
        )
        if key not in log_keys:
            missing_log_rows.append(
                {
                    "fact_id": row.get("fact_id"),
                    "product_id": row.get("product_id"),
                    "field_name": row.get("field_name"),
                    "field_value": row.get("field_value"),
                    "source_url": row.get("source_url"),
                }
            )
    add_metric(
        metrics,
        "E",
        "E1_promoted_field_traceability",
        "Every promoted product fact has a matching Evidence_Promotion_Log source record",
        str(len(missing_log_rows)),
        "= 0 missing log rows",
        len(missing_log_rows) == 0,
        {
            "manual_product_fact_rows": len(fact_rows),
            "promotion_log_rows": len(log_rows),
            "sample_missing": missing_log_rows[:25],
        },
        "Write or repair Evidence_Promotion_Log rows for promoted facts before field promotion is accepted.",
    )

    high_open = scalar(
        con,
        f"""
        SELECT count(*)
        FROM seed_integrity_issues
        WHERE lower(coalesce(severity, '')) = 'high'
          AND lower(coalesce(status, '')) NOT IN ({','.join('?' for _ in RESOLVED_STATUSES)})
        """,
        tuple(sorted(RESOLVED_STATUSES)),
    )
    add_metric(
        metrics,
        "E",
        "E2_seed_integrity_high_open",
        "Seed_Integrity_Issues high severity unresolved rows",
        str(high_open),
        "= 0 high open rows",
        high_open == 0,
        {"severity_counts": top_statuses(con, "seed_integrity_issues", "severity")},
        "Resolve high-severity seed integrity issues before final acceptance.",
    )


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# v4 Acceptance Self-Check",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Database: `{payload['database']}`",
        f"- Overall passed: `{payload['overall_passed']}`",
        "",
        "| Section | Metric | Current | Threshold | Passed | Next action |",
        "|---|---|---:|---:|---:|---|",
    ]
    for item in payload["metrics"]:
        passed = "True" if item["passed"] else "False"
        lines.append(
            "| {section} | `{metric_id}` {label} | {current_value} | {threshold} | {passed} | {next_action} |".format(
                **{k: str(v).replace("|", "\\|") for k, v in item.items() if k != "details"}
            )
        )
    lines.extend(["", "## Failing Metrics", ""])
    failing = [item for item in payload["metrics"] if not item["passed"]]
    if not failing:
        lines.append("- None.")
    else:
        for item in failing:
            lines.append(f"- `{item['metric_id']}`: {item['current_value']} vs {item['threshold']}. {item['next_action']}")
    lines.append("")
    return "\n".join(lines)


def run() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if not DB_PATH.exists():
        raise FileNotFoundError(DB_PATH)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        metrics: list[Metric] = []
        check_data_consistency(con, metrics)
        check_master_fill_rates(con, metrics)
        check_regulatory(con, metrics)
        check_company_layer(con, metrics)
        check_process_closure(con, metrics)
    finally:
        con.close()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database": str(DB_PATH),
        "overall_passed": all(metric.passed for metric in metrics),
        "metrics": [asdict(metric) for metric in metrics],
    }

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    SUMMARY_MD_PATH.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(run())
