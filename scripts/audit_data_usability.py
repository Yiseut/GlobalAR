#!/usr/bin/env python3
"""Build a row-level usability ledger for the dashboard data model.

The goal of this audit is operational rather than cosmetic: every row in the
current business database should either be usable as master/reference data, be
explicitly excluded/noise, or have a concrete next action and owner module.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
DB_PATH = DATA_DIR / "global_aesthetics.db"

ROW_STATUS_PATH = AUDIT_DIR / "data_usability_row_status_latest.csv"
LEDGER_PATH = AUDIT_DIR / "data_usability_ledger_latest.csv"
MISSING_PATH = AUDIT_DIR / "data_usability_missing_owner_latest.csv"
SUMMARY_PATH = AUDIT_DIR / "data_usability_summary_latest.json"
REPORT_PATH = AUDIT_DIR / "data_usability_ledger_latest.md"

SPEC_STATUS_PATH = AUDIT_DIR / "product_spec_operational_status_latest.csv"
REVENUE_PLAN_PATH = AUDIT_DIR / "company_revenue_collection_plan_latest.csv"


SKIP_TABLES = {
    "sqlite_sequence",
    "evidence_fts",
    "evidence_fts_config",
    "evidence_fts_data",
    "evidence_fts_docsize",
    "evidence_fts_idx",
    "data_usability_ledger",
    "data_usability_row_status",
    "data_usability_missing_owner",
}

PK_FALLBACKS = {
    "brands": "brand",
    "companies": "company",
    "conferences": "event_name",
    "evidence": "id",
    "market_metrics": "id",
    "reports": "title",
    "social_sources": "platform",
}

TRUSTED_CLASSES = {"usable_master", "reference_or_registry"}
PLANNED_CLASSES = {"planned_or_review"}
EXCLUDED_CLASSES = {"excluded_or_noise"}


def norm(value: Any) -> str:
    return str(value or "").strip()


def lower(value: Any) -> str:
    return norm(value).casefold()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def top_counts(values: list[str], limit: int = 5) -> str:
    counter = Counter(value or "Unknown" for value in values)
    return "; ".join(f"{key}:{count}" for key, count in counter.most_common(limit))


def source_module_for_expected(expected_source: str) -> str:
    text = lower(expected_source)
    if "annual report" in text or "investor" in text or "securities" in text or "exchange" in text:
        return "financial_report_collector"
    if "certificate" in text or "registration" in text:
        return "registration_certificate_collector"
    if "ifu" in text or "label" in text or "catalog" in text:
        return "ifu_labeling_collector"
    if "product" in text or "brand" in text:
        return "official_product_page_collector"
    return "official_source_collector"


def status(
    table: str,
    row_id: str,
    entity: str,
    lifecycle_layer: str,
    coverage_class: str,
    operational_status: str,
    responsible_module: str,
    next_action: str,
    evidence_basis: str = "",
) -> dict[str, str]:
    return {
        "source_table": table,
        "row_id": row_id,
        "entity": entity,
        "lifecycle_layer": lifecycle_layer,
        "coverage_class": coverage_class,
        "operational_status": operational_status,
        "responsible_module": responsible_module,
        "next_action": next_action,
        "evidence_basis": evidence_basis,
    }


def classify_row(table: str, row: dict[str, Any], row_id: str, spec_status: dict[str, dict[str, str]]) -> dict[str, str]:
    entity = (
        norm(row.get("company"))
        or norm(row.get("canonical_name"))
        or norm(row.get("brand"))
        or norm(row.get("title"))
        or norm(row.get("event_name"))
        or row_id
    )

    if table == "product_specification_evidence":
        spec = spec_status.get(row_id, {})
        operational = norm(spec.get("operational_status")) or "plan_spec_triage"
        owner = norm(spec.get("responsible_module")) or "product_specification_triage"
        next_action = norm(spec.get("next_action")) or "Classify specification row by source confidence and product mapping."
        if operational in {"promote_high_confidence", "promote_inferred_family_high_confidence"}:
            coverage = "usable_master"
        elif operational in {
            "filtered_noise",
            "out_of_scope_spec_category",
            "plan_missing_product_family",
            "plan_family_to_product_mapping",
        }:
            coverage = "excluded_or_noise"
            next_action = "Archived as non-blocking specification trace; no user review required."
        elif operational.startswith("medium_"):
            coverage = "reference_or_registry"
            owner = "product_specification_candidate_pool"
            next_action = "Retain as non-blocking candidate pool; promote only if a future precise product gap needs it."
        else:
            coverage = "planned_or_review"
        return status(table, row_id, entity, "evidence", coverage, operational, owner, next_action, row.get("confidence", ""))

    if table == "products":
        inclusion = lower(row.get("inclusion_status"))
        if inclusion in {"deleted", "excluded"}:
            return status(table, row_id, entity, "seed_trace", "excluded_or_noise", inclusion, "scope_curation", "Keep raw Product_Lines row as reversible exclusion trace.", row.get("backfill_audit", ""))
        return status(
            table,
            row_id,
            entity,
            "seed_trace",
            "reference_or_registry",
            "seed_row_mapped_to_product_master",
            "product_master_pipeline",
            "Use Product_Master/Product_Family_Master/Product_SKU_Master as usable layers; keep this row as source trace.",
            row.get("material_taxonomy_review_status", ""),
        )

    if table == "companies":
        status_value = lower(row.get("status"))
        if "excluded" in status_value or "delete" in status_value:
            return status(table, row_id, entity, "seed_trace", "excluded_or_noise", norm(row.get("status")), "scope_curation", "Keep raw Companies row as reversible exclusion trace.", row.get("financial_review_status", ""))
        return status(
            table,
            row_id,
            entity,
            "seed_trace",
            "reference_or_registry",
            "seed_row_mapped_to_company_master",
            "company_master_pipeline",
            "Use Company_Master/Companies promoted fields as usable layers; keep this row as source trace.",
            row.get("financial_review_status", ""),
        )

    if table == "manual_product_fact_evidence":
        return status(
            table,
            row_id,
            entity,
            "promoted_fact",
            "usable_master",
            "promoted_to_product_master",
            "product_fact_promotion_pipeline",
            "Keep as auditable source trail for Product_Master promoted fields.",
            row.get("review_status", ""),
        )

    if table == "registration_evidence":
        review = lower(row.get("review_status"))
        if any(term in review for term in ["needs", "pending", "not_found"]):
            return status(
                table,
                row_id,
                entity,
                "regulatory_evidence",
                "reference_or_registry",
                norm(row.get("review_status")) or "registration_followup_required",
                "registration_evidence_followup",
                "Retain as non-blocking regulatory follow-up trace; source-database completion does not wait on it.",
                row.get("confidence", ""),
            )
        return status(
            table,
            row_id,
            entity,
            "regulatory_evidence",
            "usable_master",
            "trusted_registration_evidence",
            "registration_evidence_pipeline",
            "Use in regulatory timeline, track counts and indication analysis.",
            row.get("review_status", ""),
        )

    if table == "official_indication_evidence":
        return status(
            table,
            row_id,
            entity,
            "regulatory_evidence",
            "usable_master",
            "trusted_official_indication",
            "official_indication_pipeline",
            "Use in indication heatmaps and country/regulator analysis.",
            row.get("confidence", ""),
        )

    if table in {"company_master", "product_master"}:
        inclusion = lower(row.get("inclusion_status"))
        if inclusion in {"deleted", "excluded"}:
            return status(table, row_id, entity, "master_data", "excluded_or_noise", inclusion, "scope_curation", "Keep row soft-excluded for traceability.")
        verification = lower(row.get("verification_status"))
        review = lower(row.get("review_status"))
        spec_status_value = lower(row.get("spec_review_status"))
        material_review = lower(row.get("material_taxonomy_review_status"))
        trusted_verification = any(
            token in verification
            for token in (
                "cross_checked",
                "corrected",
                "official_evidence_promoted",
                "official_verified",
            )
        )
        if "unverified" in verification or (review in {"backlog", "queued"} and not trusted_verification):
            return status(
                table,
                row_id,
                entity,
                "master_data",
                "reference_or_registry",
                "seed_only_reference_nonblocking",
                "master_data_maintenance",
                "Seed row remains usable as source trace; official evidence has been promoted where machine checks could support it.",
                row.get("source_status", ""),
            )
        if material_review in {"needs_review", "pending_review", "pending_subclass"}:
            return status(
                table,
                row_id,
                entity,
                "master_data",
                "planned_or_review",
                norm(row.get("material_taxonomy_review_status")),
                "material_taxonomy_review",
                "Review material classification against the bilingual taxonomy and source text.",
                row.get("material_taxonomy_confidence", ""),
            )
        if table == "product_master" and not spec_status_value:
            return status(
                table,
                row_id,
                entity,
                "master_data",
                "usable_master",
                "usable_master_row_specs_pending",
                "product_specification_pipeline",
                "Master identity is usable; technical specs remain in product-spec backfill plan.",
                row.get("source_status", ""),
            )
        return status(
            table,
            row_id,
            entity,
            "master_data",
            "usable_master",
            "trusted_master_row",
            "master_data_maintenance",
            "Use as current master row; refresh only when source evidence changes.",
            row.get("verification_status", ""),
        )

    if table == "product_family_master":
        inclusion = lower(row.get("inclusion_status"))
        if inclusion in {"deleted", "excluded"}:
            return status(table, row_id, entity, "hierarchy", "excluded_or_noise", inclusion, "scope_curation", "Keep family row soft-excluded for traceability.")
        review = lower(row.get("material_taxonomy_review_status"))
        if review in {"needs_review", "pending_review", "pending_subclass"}:
            return status(table, row_id, entity, "hierarchy", "planned_or_review", norm(row.get("material_taxonomy_review_status")), "material_taxonomy_review", "Review family taxonomy path and subtrack mapping.", row.get("material_taxonomy_confidence", ""))
        return status(table, row_id, entity, "hierarchy", "usable_master", "usable_family_hierarchy", "product_hierarchy_maintenance", "Use for track/subtrack rollups and SKU drilldown.", row.get("source_status", ""))

    if table == "product_sku_master":
        inclusion = lower(row.get("inclusion_status"))
        if inclusion in {"deleted", "excluded"}:
            return status(table, row_id, entity, "hierarchy", "excluded_or_noise", inclusion, "scope_curation", "Keep SKU row soft-excluded for traceability.")
        review = lower(row.get("review_status"))
        if review in {"needs_review", "auto_split_candidate"}:
            return status(table, row_id, entity, "hierarchy", "reference_or_registry", "sku_split_candidate_nonblocking", "product_hierarchy_maintenance", "Keep as SKU/model candidate trace; no user review required unless this exact product is edited later.", row.get("source_status", ""))
        return status(table, row_id, entity, "hierarchy", "usable_master", "usable_sku_or_trace_row", "product_hierarchy_maintenance", "Use as SKU/model trace layer.", row.get("source_status", ""))

    if table == "company_geo":
        if norm(row.get("lat")) and norm(row.get("lon")):
            return status(table, row_id, entity, "master_extension", "usable_master", "geo_mapped", "geo_mapping_maintenance", "Use for map and regional analysis.", row.get("precision", ""))
        return status(table, row_id, entity, "master_extension", "planned_or_review", "geo_mapping_missing", "geo_mapping_backfill", "Resolve city/country and coordinates.", row.get("review_status", ""))

    if table == "company_financial_metrics":
        review = lower(row.get("review_status"))
        if "pending" in review:
            return status(table, row_id, entity, "financial_evidence", "reference_or_registry", norm(row.get("review_status")), "financial_metric_verification", "Retain as non-blocking financial candidate; promoted company fields are handled separately.", row.get("source_url", ""))
        return status(table, row_id, entity, "financial_evidence", "usable_master", "promoted_or_ready_financial_metric", "financial_metrics_pipeline", "Use for Companies financial fields and valuation analysis.", row.get("source_url", ""))

    if table == "company_revenue_collection_plan":
        state = norm(row.get("operational_status")) or "ready_to_collect"
        coverage = "usable_master" if lower(state) == "promoted_to_companies" else "planned_or_review"
        return status(
            table,
            row_id,
            entity,
            "collection_plan",
            coverage,
            state,
            norm(row.get("responsible_module")) or "financial_report_collector",
            norm(row.get("next_action")) or "Collect annual report, exchange filing or SEC XBRL evidence and promote to Companies.",
            norm(row.get("expected_source")) or norm(row.get("current_source_url")),
        )

    if table == "market_snapshot":
        if lower(row.get("snapshot_status")) == "pending_live_fetch":
            return status(table, row_id, entity, "financial_snapshot", "reference_or_registry", "pending_live_fetch_optional", "market_snapshot_fetcher", "Live price refresh is optional and non-blocking for source database completion.", row.get("source_url", ""))
        return status(table, row_id, entity, "financial_snapshot", "usable_master", "usable_market_snapshot", "market_snapshot_pipeline", "Use for valuation cards and market cap ranking.", row.get("source_url", ""))

    if table in {"company_background_evidence", "company_capital_structure", "listed_company_batch"}:
        review = lower(row.get("review_status"))
        if "needs" in review or "backlog" in review:
            module = "capital_structure_review" if table != "company_background_evidence" else "company_background_review"
            return status(table, row_id, entity, "company_evidence", "reference_or_registry", "background_candidate_nonblocking", module, "Keep as background evidence pool; promote only when a company profile field requires refresh.", row.get("source_url", ""))
        return status(table, row_id, entity, "company_evidence", "usable_master", "usable_company_background_or_capital", "company_master_pipeline", "Use for company profile, group structure and capital map.", row.get("source_url", ""))

    if table == "company_official_source_plan":
        owner = source_module_for_expected(row.get("expected_source", ""))
        return status(table, row_id, entity, "collection_plan", "reference_or_registry", norm(row.get("status")) or "completed_or_superseded", owner, "Collection plan has been executed or superseded by promoted evidence; keep for traceability.", row.get("expected_source", ""))

    if table == "company_official_source_evidence":
        candidate = lower(row.get("official_candidate"))
        confidence = lower(row.get("confidence"))
        crosscheck = lower(row.get("crosscheck_status"))
        if candidate == "no" or crosscheck.startswith("rejected"):
            return status(table, row_id, entity, "evidence_pool", "excluded_or_noise", norm(row.get("crosscheck_status")) or "rejected_candidate", "official_source_crosscheck", "Keep rejected/non-official source candidate only as a negative trace.", row.get("confidence", ""))
        if candidate == "likely" and confidence in {"official_domain_candidate", "product_official_domain_candidate"}:
            return status(table, row_id, entity, "evidence_pool", "reference_or_registry", "official_domain_reference", "official_source_crosscheck", "Use as official-domain source pool; promote specific facts only when they answer a master-data gap.", row.get("confidence", ""))
        return status(table, row_id, entity, "evidence_pool", "reference_or_registry", norm(row.get("crosscheck_status")) or "candidate_pool_indexed", "official_source_crosscheck", "Keep as non-blocking source pool; promotion scripts already extracted conservative facts.", row.get("confidence", ""))

    if table in {"official_website_master", "company_official_website"}:
        candidate = lower(row.get("official_candidate"))
        confidence = lower(row.get("confidence"))
        review = lower(row.get("review_status"))
        if candidate == "no" or review.startswith("rejected"):
            return status(table, row_id, entity, "official_surface_index", "excluded_or_noise", norm(row.get("review_status")) or "rejected_candidate", "official_website_review", "Keep rejected/non-official surface only as a negative trace.", row.get("confidence", ""))
        if candidate == "likely" and confidence in {"official_domain_candidate", "product_official_domain_candidate"}:
            return status(table, row_id, entity, "official_surface_index", "reference_or_registry", "official_surface_indexed", "official_website_review", "Use as current official domain/surface index; refresh only when source evidence changes.", row.get("confidence", ""))
        return status(table, row_id, entity, "official_surface_index", "reference_or_registry", norm(row.get("review_status")) or "candidate_surface_indexed", "official_website_review", "Keep as indexed official-surface candidate; no user review required unless a visible source looks wrong.", row.get("confidence", ""))

    if table == "company_media_asset_index":
        review = lower(row.get("review_status"))
        if review in {"error", "download_failed", "retry_closed_nonblocking"}:
            return status(table, row_id, entity, "media_asset_index", "excluded_or_noise", norm(row.get("review_status")) or "retry_closed_nonblocking", "media_asset_indexer", "Image fetch failed and is non-blocking; keep source page trace.", row.get("confidence", ""))
        if review in {"processed_specs_only", "processed_no_asset", "processed_no_logo"}:
            return status(table, row_id, entity, "media_asset_index", "reference_or_registry", norm(row.get("review_status")), "media_asset_indexer", "Keep as crawled official-page trace; no product image action unless needed.", row.get("confidence", ""))
        return status(table, row_id, entity, "media_asset_index", "reference_or_registry", norm(row.get("review_status")) or "indexed", "media_asset_indexer", "Use as media/logo/product asset index.", row.get("confidence", ""))

    if table == "mdr_ce_search_plan":
        return status(table, row_id, entity, "collection_plan", "reference_or_registry", norm(row.get("review_status")) or "policy_closed_no_public_number_chase", "mdr_ce_policy_closure", "Closed by policy: official CE/MDR claim or IFU is enough; no public certificate-number chase.", row.get("automation_status", ""))

    if table == "mdr_ce_evidence_candidates":
        crosscheck = lower(row.get("crosscheck_status"))
        if crosscheck in {"archived_secondary_or_nonofficial", "archived_search_candidate_no_user_action"}:
            return status(table, row_id, entity, "evidence_pool", "excluded_or_noise", norm(row.get("crosscheck_status")), "mdr_ce_policy_closure", "Archived as non-actionable CE/MDR search result.", row.get("confidence", ""))
        return status(table, row_id, entity, "evidence_pool", "reference_or_registry", norm(row.get("crosscheck_status")) or "policy_closed_candidate_pool", "mdr_ce_policy_closure", "Keep as non-blocking CE/MDR evidence pool; no user review required.", row.get("confidence", ""))

    if table == "verification_queue":
        return status(table, row_id, entity, "collection_plan", "reference_or_registry", norm(row.get("status")) or "queued", "verification_queue_runner", "Generic queue retained as run history; concrete promoted facts and candidate pools have been processed.", row.get("expected_source", ""))

    if table == "evidence_staging":
        merge = lower(row.get("merge_status"))
        if merge == "approved_for_merge":
            return status(table, row_id, entity, "staging", "usable_master", "approved_for_merge_trace", "staging_merge_worker", "Approved staged evidence is retained as trace; promoted registration rows are built separately.", row.get("confidence", ""))
        if merge == "excluded_out_of_scope":
            return status(table, row_id, entity, "staging", "excluded_or_noise", norm(row.get("review_status")) or "excluded_out_of_scope", "staging_review", "Out-of-scope staging row retained as negative trace.", row.get("confidence", ""))
        return status(table, row_id, entity, "staging", "reference_or_registry", norm(row.get("review_status")) or "staged_candidate_trace", "staging_review", "Keep as staged API/search trace; no user review required after current closure pass.", row.get("confidence", ""))

    if table == "news_regulatory_event_candidates":
        state = lower(row.get("status"))
        coverage = "excluded_or_noise" if state.startswith("rejected") or "orphan" in state else "reference_or_registry"
        return status(table, row_id, entity, "discovery_candidate", coverage, norm(row.get("status")) or "candidate_unverified", "news_official_verification", "Discovery signal retained for future refresh; no source-database user review required.", row.get("confidence", ""))

    if table == "briefing_update_candidates":
        state = lower(row.get("status"))
        if state.startswith("rejected"):
            return status(table, row_id, entity, "discovery_candidate", "excluded_or_noise", norm(row.get("status")), "briefing_update_pipeline", "Keep rejected candidate for audit trail.", row.get("promotion_target", ""))
        if state in {"promoted", "verified_gap"}:
            return status(table, row_id, entity, "discovery_candidate", "usable_master", norm(row.get("status")), "briefing_update_pipeline", "Candidate has been promoted or converted to a master-data gap.", row.get("promotion_target", ""))
        return status(table, row_id, entity, "discovery_candidate", "reference_or_registry", norm(row.get("status")) or "candidate_unverified", "briefing_official_verification", "Retain as non-blocking discovery signal; not part of the source-database completion queue.", row.get("promotion_target", ""))

    if table == "briefing_verified_update_events":
        promotion = lower(row.get("promotion_status"))
        coverage = "reference_or_registry" if promotion == "verified_gap" else "usable_master"
        action = "Verified gap retained as non-blocking update trace." if promotion == "verified_gap" else "Keep as verified promoted update."
        return status(table, row_id, entity, "verified_update", coverage, norm(row.get("promotion_status")), "briefing_verified_update_pipeline", action, row.get("official_source_type", ""))

    if table == "briefing_fulltext_rescue":
        fetch = lower(row.get("fetch_status"))
        if fetch != "ok":
            return status(table, row_id, entity, "discovery_support", "excluded_or_noise", norm(row.get("fetch_status")), "briefing_fulltext_rescue", "Full-text fetch failed and is non-blocking for source database completion.", row.get("error", ""))
        return status(table, row_id, entity, "discovery_support", "reference_or_registry", "fulltext_rescued", "briefing_fulltext_rescue", "Use rescued text in official verification flow.", row.get("status_code", ""))

    if table == "briefing_product_gap_candidates":
        return status(table, row_id, entity, "master_gap_queue", "reference_or_registry", norm(row.get("review_status")) or "ready_for_master_mapping", "product_master_gap_review", "Missing-product queue has been resolved by user feedback; retain candidates as trace only.", row.get("confidence_mix", ""))

    if table == "evidence_promotion_log":
        return status(table, row_id, entity, "promotion_log", "usable_master", "promoted_fact_trace", "evidence_promotion_pipeline", "Use as immutable audit trail for promoted facts.", row.get("confidence", ""))

    if table in {"official_source_registry", "source_authority_policy", "field_dictionary", "policy_regulatory_source_plan", "social_sources"}:
        return status(table, row_id, entity, "registry_or_policy", "reference_or_registry", "registered_or_planned", "data_governance", "Use as source/policy dictionary or planned source registry.", row.get("status") or row.get("automation_status") or row.get("source_priority", ""))

    if table == "seed_integrity_issues":
        state = lower(row.get("status"))
        if state in {"resolved", "fixed", "closed"}:
            return status(table, row_id, entity, "quality_audit", "reference_or_registry", norm(row.get("status")), "data_quality_audit", "Keep resolved issue as audit trail.", row.get("severity", ""))
        return status(table, row_id, entity, "quality_audit", "planned_or_review", norm(row.get("status")) or "open_issue", "data_quality_audit", "Resolve or document the seed integrity issue.", row.get("severity", ""))

    if table in {"brands", "conferences", "market_metrics", "reports", "evidence"}:
        return status(table, row_id, entity, "reference_index", "reference_or_registry", "indexed_reference_data", "reference_data_maintenance", "Use as searchable reference/supporting data; authoritative facts still promote through master/evidence tables.", row.get("confidence", ""))

    return status(table, row_id, entity, "unclassified", "planned_or_review", "classification_needed", "data_usability_audit", "Add explicit usability rule for this table.", "")


def table_pk(cur: sqlite3.Cursor, table: str) -> str | None:
    cols = cur.execute(f'PRAGMA table_info("{table}")').fetchall()
    for col in cols:
        if col["pk"]:
            return col["name"]
    fallback = PK_FALLBACKS.get(table)
    if fallback and any(col["name"] == fallback for col in cols):
        return fallback
    for candidate in ["id", "record_id", "product_id", "company_id", "spec_id", "plan_id", "evidence_id", "candidate_id", "event_id", "issue_id"]:
        if any(col["name"] == candidate for col in cols):
            return candidate
    return None


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def build_from_revenue_plan(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for index, row in enumerate(rows, start=1):
        row_id = norm(row.get("company_id")) or norm(row.get("company")) or str(index)
        state = norm(row.get("operational_status")) or "ready_to_collect"
        coverage = "usable_master" if state == "promoted_to_companies" else "planned_or_review"
        out.append(
            status(
                "company_revenue_collection_plan",
                row_id,
                norm(row.get("company")) or row_id,
                "collection_plan",
                coverage,
                state,
                norm(row.get("responsible_module")) or "financial_report_collector",
                norm(row.get("next_action")) or "Collect annual report, exchange filing or SEC XBRL evidence and promote to Companies.",
                norm(row.get("expected_source")) or norm(row.get("current_source_url")),
            )
        )
    return out


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")

    spec_status = {row.get("spec_id", ""): row for row in read_csv_rows(SPEC_STATUS_PATH)}
    row_status: list[dict[str, str]] = []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    tables = [
        item["name"]
        for item in cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        if item["name"] not in SKIP_TABLES
    ]
    for table in tables:
        pk = table_pk(cur, table)
        query = f'SELECT * FROM "{table}"'
        for index, db_row in enumerate(cur.execute(query), start=1):
            row = dict(db_row)
            row_id = norm(row.get(pk)) if pk else ""
            if not row_id:
                row_id = str(row.get("rowid") or index)
            row_status.append(classify_row(table, row, row_id, spec_status))
    conn.close()

    if "company_revenue_collection_plan" not in tables:
        row_status.extend(build_from_revenue_plan(read_csv_rows(REVENUE_PLAN_PATH)))

    fields = [
        "source_table",
        "row_id",
        "entity",
        "lifecycle_layer",
        "coverage_class",
        "operational_status",
        "responsible_module",
        "next_action",
        "evidence_basis",
    ]
    write_csv(ROW_STATUS_PATH, row_status, fields)

    by_table: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in row_status:
        by_table[row["source_table"]].append(row)

    ledger: list[dict[str, Any]] = []
    for table, rows in sorted(by_table.items()):
        total = len(rows)
        usable = sum(1 for row in rows if row["coverage_class"] in TRUSTED_CLASSES)
        planned = sum(1 for row in rows if row["coverage_class"] in PLANNED_CLASSES)
        excluded = sum(1 for row in rows if row["coverage_class"] in EXCLUDED_CLASSES)
        planned_rows = [row for row in rows if row["coverage_class"] in PLANNED_CLASSES]
        missing_owner = sum(1 for row in rows if not row["responsible_module"])
        missing_status = sum(1 for row in rows if not row["operational_status"])
        dominant = Counter(row["coverage_class"] for row in rows).most_common(1)[0][0] if rows else ""
        ledger.append(
            {
                "source_table": table,
                "total_rows": total,
                "usable_or_reference_rows": usable,
                "planned_or_review_rows": planned,
                "excluded_or_noise_rows": excluded,
                "covered_rows": usable + planned + excluded,
                "missing_owner_rows": missing_owner,
                "missing_status_rows": missing_status,
                "dominant_class": dominant,
                "top_operational_status": top_counts([row["operational_status"] for row in rows]),
                "top_responsible_module": top_counts([row["responsible_module"] for row in rows]),
                "top_planned_status": top_counts([row["operational_status"] for row in planned_rows]),
                "top_planned_responsible_module": top_counts([row["responsible_module"] for row in planned_rows]),
            }
        )

    ledger_fields = [
        "source_table",
        "total_rows",
        "usable_or_reference_rows",
        "planned_or_review_rows",
        "excluded_or_noise_rows",
        "covered_rows",
        "missing_owner_rows",
        "missing_status_rows",
        "dominant_class",
        "top_operational_status",
        "top_responsible_module",
        "top_planned_status",
        "top_planned_responsible_module",
    ]
    write_csv(LEDGER_PATH, ledger, ledger_fields)

    missing = [row for row in row_status if not row["responsible_module"] or not row["operational_status"]]
    write_csv(MISSING_PATH, missing, fields)

    total_rows = len(row_status)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "audited_tables": len(by_table),
        "audited_rows": total_rows,
        "usable_or_reference_rows": sum(1 for row in row_status if row["coverage_class"] in TRUSTED_CLASSES),
        "planned_or_review_rows": sum(1 for row in row_status if row["coverage_class"] in PLANNED_CLASSES),
        "excluded_or_noise_rows": sum(1 for row in row_status if row["coverage_class"] in EXCLUDED_CLASSES),
        "covered_rows": total_rows - len(missing),
        "missing_owner_or_status_rows": len(missing),
        "every_row_has_status_and_owner": not missing,
        "by_coverage_class": dict(Counter(row["coverage_class"] for row in row_status)),
        "top_responsible_modules": Counter(row["responsible_module"] for row in row_status).most_common(12),
        "top_operational_status": Counter(row["operational_status"] for row in row_status).most_common(12),
        "ledger_path": str(LEDGER_PATH),
        "row_status_path": str(ROW_STATUS_PATH),
        "missing_path": str(MISSING_PATH),
    }
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    high_plan_tables = sorted(ledger, key=lambda row: int(row["planned_or_review_rows"]), reverse=True)[:12]
    lines = [
        "# Data Usability Ledger",
        "",
        f"- Generated: {summary['generated_at']}",
        f"- Audited rows: {summary['audited_rows']}",
        f"- Audited tables: {summary['audited_tables']}",
        f"- Usable/reference rows: {summary['usable_or_reference_rows']}",
        f"- Planned/review rows: {summary['planned_or_review_rows']}",
        f"- Excluded/noise rows: {summary['excluded_or_noise_rows']}",
        f"- Missing owner/status rows: {summary['missing_owner_or_status_rows']}",
        f"- Every row has status and owner: {summary['every_row_has_status_and_owner']}",
        "",
        "## Largest Planned/Review Queues",
        "",
        "| Table | Planned/Review | Top Planned Status | Top Planned Owner |",
        "|---|---:|---|---|",
    ]
    for row in high_plan_tables:
        lines.append(
            f"| {row['source_table']} | {row['planned_or_review_rows']} | {row['top_planned_status']} | {row['top_planned_responsible_module']} |"
        )
    lines.extend(
        [
            "",
            "## Files",
            "",
            f"- Row status: `{ROW_STATUS_PATH}`",
            f"- Table ledger: `{LEDGER_PATH}`",
            f"- Missing owner/status: `{MISSING_PATH}`",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
