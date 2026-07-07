#!/usr/bin/env python3
"""Build the completed next-step data layers for the commercial dashboard."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
AUDIT_DIR = DATA_DIR / "audits"
WEB_DATA_PATH = PROJECT_DIR / "web" / "v3" / "v3-market-intelligence.js"

GEO_DISCOVERY_PATH = AUDIT_DIR / "commercial_geo_market_source_discovery_latest.csv"
SOURCE_REGISTRY_PATH = DATA_DIR / "commercial_data_source_registry.csv"
BACKLOG_PATH = AUDIT_DIR / "commercial_data_collection_backlog_latest.csv"
ASPS_STATUS_PATH = AUDIT_DIR / "asps_official_stats_extraction_status_latest.csv"
BAAPS_MARKET_METRICS_PATH = DATA_DIR / "baaps_market_metrics.csv"
COMPANY_FINANCIAL_PATH = DATA_DIR / "company_financial_metrics.csv"
COMPANY_REVENUE_PLAN_PATH = AUDIT_DIR / "company_revenue_collection_plan_latest.csv"
AESTHETICS_REVENUE_QUEUE_PATH = AUDIT_DIR / "aesthetics_revenue_pct_collection_queue_latest.csv"
EUROPE_ASSOCIATION_MARKET_METRICS_PATH = DATA_DIR / "europe_association_market_metrics.csv"

EUROPE_QA_PATH = AUDIT_DIR / "europe_metric_qa_latest.csv"
CHANNEL_DENSITY_PATH = DATA_DIR / "commercial_channel_density_proxy.csv"
CHANNEL_DENSITY_DETAIL_PATH = DATA_DIR / "commercial_channel_density_detail.csv"
REVENUE_PROGRESS_PATH = AUDIT_DIR / "company_revenue_layer_progress_latest.csv"
COMPLETION_PATH = AUDIT_DIR / "commercial_next_step_completion_latest.csv"


def norm(value: Any) -> str:
    return " ".join(str(value or "").split())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def safe_int(value: Any) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except Exception:
        return 0


def parse_v3_market_data() -> dict[str, Any]:
    if not WEB_DATA_PATH.exists():
        return {}
    text = WEB_DATA_PATH.read_text(encoding="utf-8")
    prefix = "window.V3_MARKET_INTELLIGENCE_DATA = "
    if not text.startswith(prefix):
        return {}
    payload = text[len(prefix) :].strip()
    if payload.endswith(";"):
        payload = payload[:-1]
    return json.loads(payload)


def inspect_pdf(path: Path, max_pages_for_tables: int = 12) -> dict[str, Any]:
    out = {
        "pages": 0,
        "tables": 0,
        "percent_mentions": 0,
        "count_terms": 0,
        "procedure_terms": 0,
    }
    if not path.exists() or path.suffix.lower() != ".pdf":
        return out
    try:
        with pdfplumber.open(path) as pdf:
            out["pages"] = len(pdf.pages)
            for index, page in enumerate(pdf.pages):
                text = (page.extract_text(x_tolerance=1, y_tolerance=3) or "").lower()
                out["percent_mentions"] += text.count("%")
                out["count_terms"] += len(re.findall(r"\b(count|total|number|anzahl|zahl|n=|intervenciones|totale)\b", text))
                out["procedure_terms"] += len(re.findall(r"\b(procedure|procedures|operationen|behandlungen|cirug[ií]a|intervenciones)\b", text))
                if index < max_pages_for_tables:
                    out["tables"] += len(page.extract_tables() or [])
    except Exception:
        out["error"] = "pdf_inspection_failed"
    return out


def build_europe_qa(captured_at: str) -> list[dict[str, Any]]:
    geo_rows = read_csv(GEO_DISCOVERY_PATH)
    registry = {row.get("source_id"): row for row in read_csv(SOURCE_REGISTRY_PATH)}
    backlog = {row.get("source_id"): row for row in read_csv(BACKLOG_PATH)}
    promoted_europe_rows = read_csv(EUROPE_ASSOCIATION_MARKET_METRICS_PATH)
    promoted_by_source = Counter(norm(row.get("source_org")).lower() for row in promoted_europe_rows)
    target_ids = [
        "germany_dgaepc_statistics",
        "spain_secpre_aesthetic_surgery_report",
        "italy_aicpe_observatory_statistics",
        "italy_sicpre_isaps_statistics",
    ]
    rows: list[dict[str, Any]] = []
    for source_id in target_ids:
        source_rows = [row for row in geo_rows if row.get("source_id") == source_id]
        meta = registry.get(source_id, {})
        task = backlog.get(source_id, {})
        local_paths = []
        pdf_inspection = Counter()
        for row in source_rows:
            local_path = norm(row.get("local_path"))
            if not local_path:
                continue
            local_paths.append(local_path)
            inspected = inspect_pdf(PROJECT_DIR / local_path)
            pdf_inspection.update(
                {
                    "pages": inspected.get("pages", 0),
                    "tables": inspected.get("tables", 0),
                    "percent_mentions": inspected.get("percent_mentions", 0),
                    "count_terms": inspected.get("count_terms", 0),
                    "procedure_terms": inspected.get("procedure_terms", 0),
                }
            )

        years = sorted({norm(row.get("year")) for row in source_rows if norm(row.get("year"))})
        status_counts = Counter(norm(row.get("status")) or "unknown" for row in source_rows)
        artifact_counts = Counter(norm(row.get("artifact_type")) or "unknown" for row in source_rows)
        country = norm(source_rows[0].get("country_or_region")) if source_rows else ""
        source_name = norm(meta.get("source_name") or (source_rows[0].get("source_name") if source_rows else source_id))

        if source_id == "germany_dgaepc_statistics":
            count_status = "patient survey preference shares; no national procedure count denominator found"
            share_status = "usable as treatment preference proxy only"
            table_status = "2020-2025 PDFs inspected; methodology is a standardized patient questionnaire and percentages can exceed 100%"
            decision = "proxy_only_do_not_promote_as_treatment_volume"
            next_action = "Keep DGÄPC out of procedure_volume mainline; optionally extract top treatment preference shares as source-labeled demand proxy."
        elif source_id == "spain_secpre_aesthetic_surgery_report":
            if promoted_by_source.get("secpre"):
                count_status = f"surgical intervention count table promoted ({promoted_by_source['secpre']} rows)"
                share_status = "patient/demographic shares remain unpromoted"
                table_status = "SECPRE Table 1 manually QA'd and loaded as Spain surgical-only procedure volume"
                decision = "promoted_surgical_only"
                next_action = "Keep SECPRE as Spain surgical-only association lane; do not merge silently with ISAPS total procedures."
            else:
                count_status = "candidate count-like narrative metrics"
                share_status = "patient/demographic shares likely"
                table_status = "official PDF acquired; first-pass table extraction did not expose stable tables"
                decision = "hold_for_manual_text_qa"
                next_action = "Manually mark SECPRE tables/text blocks as count, share or context before promotion."
        elif source_id == "italy_aicpe_observatory_statistics":
            count_status = "2020 total cross-checks ISAPS Italy; no independent count table found"
            share_status = "association commentary only"
            table_status = "legacy AICPE page is unavailable; readable copies cite ISAPS 2020 as the source"
            decision = "crosscheck_only_do_not_promote_duplicate_isaps"
            next_action = "Keep AICPE as Italy association context; do not load duplicate 2020 rows. Reopen 2019 only if official ISAPS 2019 backfill becomes a priority."
        else:
            count_status = "secondary ISAPS commentary"
            share_status = "not an independent denominator"
            table_status = "downloaded ISAPS PDF is already covered by primary ISAPS lane"
            decision = "do_not_promote_as_new_source"
            next_action = "Use SICPRE only as cross-check/context; do not overwrite primary ISAPS Italy rows."

        rows.append(
            {
                "source_id": source_id,
                "country": country,
                "source_name": source_name,
                "source_family": norm(meta.get("source_family") or (source_rows[0].get("source_family") if source_rows else "")),
                "authority_tier": norm(meta.get("authority_tier") or (source_rows[0].get("authority_tier") if source_rows else "")),
                "records": len(source_rows),
                "downloaded_files": status_counts.get("downloaded", 0),
                "artifact_mix": "; ".join(f"{key}:{value}" for key, value in sorted(artifact_counts.items())),
                "years_found": ";".join(years),
                "pdf_pages_inspected": pdf_inspection.get("pages", 0),
                "pdf_tables_detected": pdf_inspection.get("tables", 0),
                "count_status": count_status,
                "share_status": share_status,
                "table_status": table_status,
                "mainline_decision": decision,
                "promotion_allowed": "yes_surgical_only" if decision == "promoted_surgical_only" else "no",
                "source_files": "; ".join(local_paths[:5]),
                "next_action": next_action or norm(task.get("next_action")),
                "acceptance_check": norm(task.get("acceptance_check")),
                "captured_at": captured_at,
            }
        )
    return rows


def role_has(row: dict[str, Any], tokens: list[str]) -> bool:
    text = " ".join(
        norm(row.get(key))
        for key in ["sourceId", "sourceName", "sourceFamily", "dataRole", "metricPotential", "authorityTier"]
    ).lower()
    return any(token in text for token in tokens)


def build_channel_density(captured_at: str) -> list[dict[str, Any]]:
    data = parse_v3_market_data()
    top_rows = data.get("topCompanyCountries") or []
    geo_rows = data.get("geoSourceDiscovery") or []
    by_source = defaultdict(list)
    for row in geo_rows:
        source_id = norm(row.get("sourceId"))
        if source_id:
            by_source[source_id].append(row)

    output: list[dict[str, Any]] = []
    for row in top_rows:
        source_ids = [norm(source_id) for source_id in row.get("sourceIds", []) if norm(source_id)]
        source_rows = [item for source_id in source_ids for item in by_source.get(source_id, [])]
        source_samples = []
        for source_id in source_ids:
            sample = (by_source.get(source_id) or [{}])[0]
            source_samples.append(
                {
                    "sourceId": source_id,
                    "sourceName": norm(sample.get("sourceName")) or source_id,
                    "sourceFamily": norm(sample.get("sourceFamily")),
                    "dataRole": norm(sample.get("dataRole")),
                    "authorityTier": norm(sample.get("authorityTier")),
                    "metricPotential": norm(sample.get("metricPotential")),
                }
            )
        provider_sources = [sample for sample in source_samples if role_has(sample, ["provider", "locator", "clinic", "touchpoint", "distributor"])]
        denominator_sources = [sample for sample in source_samples if role_has(sample, ["surgeon_denominator", "physician", "medical_demography", "doctor", "specialty"])]
        association_sources = [sample for sample in source_samples if role_has(sample, ["association", "society", "statistics"])]
        distributor_sources = [sample for sample in source_samples if role_has(sample, ["distributor", "dealer", "partner"])]
        if provider_sources:
            proxy_status = "provider_locator_available"
        elif denominator_sources:
            proxy_status = "doctor_denominator_available"
        elif association_sources:
            proxy_status = "association_entry_only"
        elif source_ids:
            proxy_status = "source_discovered_needs_enrichment"
        else:
            proxy_status = "gap"
        output.append(
            {
                "rank": row.get("rank"),
                "country": row.get("country"),
                "source_country": row.get("sourceCountry") or row.get("country"),
                "company_count": row.get("companyCount"),
                "coverage_tier": row.get("coverageTier"),
                "proxy_status": proxy_status,
                "source_count": len(source_ids),
                "discovery_record_count": len(source_rows) or row.get("recordCount") or 0,
                "downloaded_artifacts": row.get("downloadedArtifacts") or sum(1 for item in source_rows if item.get("status") == "downloaded"),
                "provider_locator_sources": len({sample["sourceId"] for sample in provider_sources}),
                "doctor_denominator_sources": len({sample["sourceId"] for sample in denominator_sources}),
                "association_entry_sources": len({sample["sourceId"] for sample in association_sources}),
                "distributor_or_channel_sources": len({sample["sourceId"] for sample in distributor_sources}),
                "data_roles": "; ".join(row.get("dataRoles") or []),
                "source_ids": "; ".join(source_ids),
                "source_names": "; ".join(row.get("sourceNames") or []),
                "next_action": (
                    "Run provider-locator/enrichment scrape to city/provider grain."
                    if proxy_status == "provider_locator_available"
                    else (
                        "Use physician/surgeon denominator as national density proxy, then add locator coverage."
                        if proxy_status == "doctor_denominator_available"
                        else "Keep as association/source entry until provider or denominator data is captured."
                    )
                ),
                "captured_at": captured_at,
            }
        )
    return output


def build_revenue_progress(captured_at: str) -> list[dict[str, Any]]:
    financial_rows = read_csv(COMPANY_FINANCIAL_PATH)
    plan_rows = read_csv(COMPANY_REVENUE_PLAN_PATH)
    queue_rows = read_csv(AESTHETICS_REVENUE_QUEUE_PATH)
    financial_by_company = {
        company_id: row
        for row in financial_rows
        if (company_id := norm(row.get("company_id")))
    }
    queue_by_company = {
        company_id: row
        for row in queue_rows
        if (company_id := norm(row.get("company_id")))
    }

    output: list[dict[str, Any]] = []
    for plan in plan_rows:
        company_id = norm(plan.get("company_id"))
        financial = financial_by_company.get(company_id, {})
        queue = queue_by_company.get(company_id, {})
        revenue_status = "total_revenue_promoted" if financial else norm(plan.get("operational_status")) or "ready_to_collect"
        aesthetics_status = "needs_aesthetics_segment_or_not_disclosed_review" if queue else "no_current_segment_gap"
        output.append(
            {
                "company_id": company_id,
                "company": norm(plan.get("company")),
                "stock_code": norm(plan.get("stock_code")),
                "listing_country": norm(plan.get("listing_country")),
                "responsible_module": norm(plan.get("responsible_module")),
                "revenue_status": revenue_status,
                "aesthetics_segment_status": aesthetics_status,
                "revenue_year": norm(financial.get("fiscal_year") or plan.get("current_revenue_year")),
                "revenue_usd_m": norm(financial.get("revenue_usd_m") or plan.get("current_revenue_usd_m")),
                "gross_margin_pct": norm(financial.get("gross_margin_pct") or plan.get("current_gross_margin_pct")),
                "financial_review_status": norm(financial.get("review_status") or queue.get("financial_review_status")),
                "segment_queue_priority": norm(queue.get("priority")),
                "expected_source": norm(queue.get("expected_source") or plan.get("expected_source")),
                "source_url": norm(financial.get("source_url") or plan.get("current_source_url") or queue.get("financial_source_url")),
                "next_action": norm(queue.get("suggested_action") or plan.get("next_action")),
                "captured_at": captured_at,
            }
        )

    for queue in queue_rows:
        company_id = norm(queue.get("company_id"))
        if any(row["company_id"] == company_id for row in output):
            continue
        output.append(
            {
                "company_id": company_id,
                "company": norm(queue.get("company")),
                "stock_code": norm(queue.get("stock_code")),
                "listing_country": "",
                "responsible_module": "segment_ir_or_annual_report_review",
                "revenue_status": "not_in_revenue_plan",
                "aesthetics_segment_status": "needs_aesthetics_segment_or_not_disclosed_review",
                "revenue_year": norm(queue.get("revenue_year")),
                "revenue_usd_m": norm(queue.get("revenue_usd_m")),
                "gross_margin_pct": norm(queue.get("gross_margin_pct")),
                "financial_review_status": norm(queue.get("financial_review_status")),
                "segment_queue_priority": norm(queue.get("priority")),
                "expected_source": norm(queue.get("expected_source")),
                "source_url": norm(queue.get("financial_source_url")),
                "next_action": norm(queue.get("suggested_action")),
                "captured_at": captured_at,
            }
        )
    output.sort(key=lambda row: (row["aesthetics_segment_status"] != "needs_aesthetics_segment_or_not_disclosed_review", row["company"].lower()))
    return output


def build_completion_rows(
    captured_at: str,
    europe_rows: list[dict[str, Any]],
    channel_rows: list[dict[str, Any]],
    revenue_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    asps_rows = read_csv(ASPS_STATUS_PATH)
    asps_row_count = sum(safe_int(row.get("rows_extracted")) for row in asps_rows)
    asps_years = sorted({part for row in asps_rows for part in norm(row.get("years_extracted")).split(";") if part})
    baaps_rows = read_csv(BAAPS_MARKET_METRICS_PATH)
    baaps_years = sorted({norm(row.get("year")) for row in baaps_rows if norm(row.get("year"))})
    baaps_surgical_years = sorted(
        {norm(row.get("year")) for row in baaps_rows if norm(row.get("category_l1")) == "Surgical procedures"}
    )
    channel_detail_rows = read_csv(CHANNEL_DENSITY_DETAIL_PATH)
    brazil_state_denominator_rows = [
        row
        for row in channel_detail_rows
        if norm(row.get("source_id")) == "brazil_sbcp_pesquisas_censo"
        and norm(row.get("metric")) == "plastic_surgeon_count"
    ]
    hong_kong_facility_rows = [
        row
        for row in channel_detail_rows
        if norm(row.get("source_id")) == "hong_kong_dh_day_procedure_centres"
    ]
    taiwan_aesthetic_institution_rows = [
        row
        for row in channel_detail_rows
        if norm(row.get("source_id")) == "taiwan_mohw_aesthetic_medicine_institutions"
    ]
    taiwan_medical_facility_rows = [
        row
        for row in channel_detail_rows
        if norm(row.get("source_id")) == "taiwan_mohw_medical_facility_open_data"
    ]
    japan_survey_frame_rows = [
        row
        for row in channel_detail_rows
        if norm(row.get("source_id")) == "japan_mhlw_aesthetic_medicine_status"
    ]
    segment_gaps = sum(1 for row in revenue_rows if row.get("aesthetics_segment_status") == "needs_aesthetics_segment_or_not_disclosed_review")
    europe_promoted = [row for row in europe_rows if norm(row.get("promotion_allowed")).startswith("yes")]
    europe_status = "completed_partial_promotion" if europe_promoted else "completed_hold_unpromoted"
    europe_note = (
        f"{len(europe_promoted)} Europe candidate source(s) have source-labeled count rows promoted; remaining candidates stay QA-held."
        if europe_promoted
        else "Candidates are classified before promotion; no Europe candidate overwrites ISAPS mainline rows."
    )
    return [
        {
            "workstream": "ASPS official US deep dive",
            "status": "completed",
            "output": str(DATA_DIR / "asps_market_metrics.csv"),
            "rows": asps_row_count,
            "frontstage_label": "ASPS 2020/2022/2023/2024 + 2024 fee/regional",
            "note": f"Extracted ASPS years {', '.join(asps_years)} into the market_metrics lane.",
            "captured_at": captured_at,
        },
        {
            "workstream": "BAAPS UK annual audit",
            "status": "completed_source_labeled",
            "output": str(BAAPS_MARKET_METRICS_PATH),
            "rows": len(baaps_rows),
            "frontstage_label": "BAAPS UK 2020-2025 audit lane",
            "note": (
                f"Extracted BAAPS years {', '.join(baaps_years)} into market_metrics; "
                f"surgical current-year rows cover {', '.join(baaps_surgical_years)} and 2022 remains non-surgical-only."
            ),
            "captured_at": captured_at,
        },
        {
            "workstream": "Europe candidate QA",
            "status": europe_status,
            "output": str(EUROPE_QA_PATH),
            "rows": len(europe_rows),
            "frontstage_label": "DGAEPC / SECPRE / AICPE / SICPRE QA",
            "note": europe_note,
            "captured_at": captured_at,
        },
        {
            "workstream": "Channel density proxy",
            "status": "completed",
            "output": str(CHANNEL_DENSITY_PATH),
            "rows": len(channel_rows),
            "frontstage_label": "Top 15 country channel-density proxy",
            "note": "Top 15 country provider locator, doctor denominator and association entries are normalized to one proxy table.",
            "captured_at": captured_at,
        },
        {
            "workstream": "Brazil SBCP surgeon-density detail",
            "status": "completed_state_denominator",
            "output": str(CHANNEL_DENSITY_DETAIL_PATH),
            "rows": len(brazil_state_denominator_rows),
            "frontstage_label": "Brazil state plastic-surgeon denominator",
            "note": "SBCP Censo 2025 page 4 is loaded as state-level plastic surgeon counts for channel-density analysis, not treatment volume.",
            "captured_at": captured_at,
        },
        {
            "workstream": "Hong Kong DH facility-density detail",
            "status": "completed_csv_denominator",
            "output": str(CHANNEL_DENSITY_DETAIL_PATH),
            "rows": len(hong_kong_facility_rows),
            "frontstage_label": "Hong Kong licensed facility denominator",
            "note": "Hong Kong DH Cap. 633 CSV is aggregated into country/district day-procedure-centre and private-hospital counts; contact fields are excluded.",
            "captured_at": captured_at,
        },
        {
            "workstream": "Taiwan MOHW aesthetic-institution detail",
            "status": "completed_pdf_denominator",
            "output": str(CHANNEL_DENSITY_DETAIL_PATH),
            "rows": len(taiwan_aesthetic_institution_rows),
            "frontstage_label": "Taiwan approved aesthetic institution denominator",
            "note": "Taiwan MOHW PDF page 1 is loaded as country/city-county approved aesthetic-medicine institution counts, updated to 2025-06-30.",
            "captured_at": captured_at,
        },
        {
            "workstream": "Taiwan MOHW medical-supply denominator",
            "status": "completed_ods_denominator",
            "output": str(CHANNEL_DENSITY_DETAIL_PATH),
            "rows": len(taiwan_medical_facility_rows),
            "frontstage_label": "Taiwan medical facility and physician denominator",
            "note": "Taiwan MOHW 2024-12-31 ODS is aggregated into city/county medical-facility and western-physician counts; contact/address fields are excluded.",
            "captured_at": captured_at,
        },
        {
            "workstream": "Japan MHLW survey-frame detail",
            "status": "completed_survey_frame_proxy",
            "output": str(CHANNEL_DENSITY_DETAIL_PATH),
            "rows": len(japan_survey_frame_rows),
            "frontstage_label": "Japan aesthetic survey coverage frame",
            "note": "MHLW material page 5 is loaded as 2019-2022 JSAPS survey target/responding institution counts; physician specialty counts remain pending.",
            "captured_at": captured_at,
        },
        {
            "workstream": "Company revenue layer",
            "status": "completed_progress_layer",
            "output": str(REVENUE_PROGRESS_PATH),
            "rows": len(revenue_rows),
            "frontstage_label": "Company-year revenue and segment gap layer",
            "note": f"Total revenue plan and aesthetics-segment gap queue are unified; {segment_gaps} companies still need segment/not-disclosed review.",
            "captured_at": captured_at,
        },
    ]


def run() -> int:
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    europe_rows = build_europe_qa(captured_at)
    channel_rows = build_channel_density(captured_at)
    revenue_rows = build_revenue_progress(captured_at)
    completion_rows = build_completion_rows(captured_at, europe_rows, channel_rows, revenue_rows)

    write_csv(
        EUROPE_QA_PATH,
        [
            "source_id",
            "country",
            "source_name",
            "source_family",
            "authority_tier",
            "records",
            "downloaded_files",
            "artifact_mix",
            "years_found",
            "pdf_pages_inspected",
            "pdf_tables_detected",
            "count_status",
            "share_status",
            "table_status",
            "mainline_decision",
            "promotion_allowed",
            "source_files",
            "next_action",
            "acceptance_check",
            "captured_at",
        ],
        europe_rows,
    )
    write_csv(
        CHANNEL_DENSITY_PATH,
        [
            "rank",
            "country",
            "source_country",
            "company_count",
            "coverage_tier",
            "proxy_status",
            "source_count",
            "discovery_record_count",
            "downloaded_artifacts",
            "provider_locator_sources",
            "doctor_denominator_sources",
            "association_entry_sources",
            "distributor_or_channel_sources",
            "data_roles",
            "source_ids",
            "source_names",
            "next_action",
            "captured_at",
        ],
        channel_rows,
    )
    write_csv(
        REVENUE_PROGRESS_PATH,
        [
            "company_id",
            "company",
            "stock_code",
            "listing_country",
            "responsible_module",
            "revenue_status",
            "aesthetics_segment_status",
            "revenue_year",
            "revenue_usd_m",
            "gross_margin_pct",
            "financial_review_status",
            "segment_queue_priority",
            "expected_source",
            "source_url",
            "next_action",
            "captured_at",
        ],
        revenue_rows,
    )
    write_csv(
        COMPLETION_PATH,
        ["workstream", "status", "output", "rows", "frontstage_label", "note", "captured_at"],
        completion_rows,
    )

    print(
        json.dumps(
            {
                "status": "ok",
                "europe_qa_rows": len(europe_rows),
                "channel_density_rows": len(channel_rows),
                "revenue_progress_rows": len(revenue_rows),
                "completion_rows": len(completion_rows),
                "outputs": {
                    "europe_qa": str(EUROPE_QA_PATH),
                    "channel_density": str(CHANNEL_DENSITY_PATH),
                    "revenue_progress": str(REVENUE_PROGRESS_PATH),
                    "completion": str(COMPLETION_PATH),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
