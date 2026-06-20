#!/usr/bin/env python3
"""Validate the commercial data-source expansion registry and backlog."""

from __future__ import annotations

import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
REGISTRY_PATH = PROJECT_DIR / "data" / "commercial_data_source_registry.csv"
BACKLOG_PATH = PROJECT_DIR / "data" / "audits" / "commercial_data_collection_backlog_latest.csv"
ISAPS_MARKET_METRICS_PATH = PROJECT_DIR / "data" / "isaps_market_metrics.csv"
ASPS_MARKET_METRICS_PATH = PROJECT_DIR / "data" / "asps_market_metrics.csv"
SNAPSHOT_PATH = PROJECT_DIR / "web" / "v3" / "v3-market-intelligence.js"

REQUIRED_PHASES = {"1", "2", "3", "4"}
REQUIRED_REGISTRY_COLUMNS = {
    "source_id",
    "phase",
    "source_name",
    "source_family",
    "source_url",
    "authority_tier",
    "kpi_families",
    "geo_grain",
    "time_grain",
    "segment_grain",
    "target_dataset",
    "implementation_status",
    "priority",
}
REQUIRED_BACKLOG_COLUMNS = {
    "task_id",
    "phase",
    "priority",
    "workstream",
    "source_id",
    "target_dataset",
    "target_table",
    "scope",
    "years",
    "segments",
    "metrics",
    "method",
    "status",
    "next_action",
    "acceptance_check",
}
CORE_SOURCE_IDS = {
    "isaps_global_survey",
    "asps_plastic_surgery_statistics",
    "aesthetic_society_statistics",
    "sec_edgar_companyfacts",
    "open_dart_korea",
    "edinet_japan",
    "company_ir_reports",
    "provider_locator_pages",
    "enrichment_provider_panel",
    "cms_open_payments",
    "world_bank_wdi",
    "market_report_archive",
}
REQUIRED_ISAPS_YEARS = {"2020", "2021", "2022", "2023", "2024"}
REQUIRED_ASPS_YEARS = {"2024"}


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def load_snapshot_metrics() -> list[dict]:
    if not SNAPSHOT_PATH.exists():
        return []
    text = SNAPSHOT_PATH.read_text(encoding="utf-8")
    match = re.search(r"window\.V3_MARKET_INTELLIGENCE_DATA\s*=\s*(\{.*\});?\s*$", text, re.S)
    if not match:
        return []
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []
    return payload.get("marketMetrics") if isinstance(payload.get("marketMetrics"), list) else []


def norm_geo(value: str) -> str:
    aliases = {
        "全球": "Global",
        "美国": "USA",
        "United States": "USA",
        "欧洲": "Europe",
        "北美": "North America",
        "亚太": "Asia-Pacific",
        "澳大利亚": "Australia",
        "韩国": "South Korea",
    }
    text = (value or "").strip()
    return aliases.get(text, text or "Unknown")


def main() -> int:
    registry, registry_columns = read_csv(REGISTRY_PATH)
    backlog, backlog_columns = read_csv(BACKLOG_PATH)
    isaps_rows, _ = read_csv(ISAPS_MARKET_METRICS_PATH)
    asps_rows, _ = read_csv(ASPS_MARKET_METRICS_PATH)
    metrics = load_snapshot_metrics()

    registry_ids = {row.get("source_id", "").strip() for row in registry if row.get("source_id")}
    backlog_source_ids = {row.get("source_id", "").strip() for row in backlog if row.get("source_id")}
    phases = {row.get("phase", "").strip() for row in registry if row.get("phase")}
    backlog_phases = {row.get("phase", "").strip() for row in backlog if row.get("phase")}

    metric_type_counts = Counter(row.get("type") for row in metrics)
    metric_year_counts = Counter(str(row.get("period") or row.get("year") or "") for row in metrics)
    snapshot_years = {str(row.get("period") or row.get("year") or "") for row in metrics if row.get("period") or row.get("year")}
    isaps_years = {row.get("year") for row in isaps_rows if row.get("year")}
    isaps_year_counts = Counter(row.get("year") for row in isaps_rows if row.get("year"))
    asps_years = {row.get("year") for row in asps_rows if row.get("year")}
    asps_year_counts = Counter(row.get("year") for row in asps_rows if row.get("year"))
    isaps_country_year_pairs = {
        (row.get("geo"), row.get("year"))
        for row in isaps_rows
        if row.get("geo") and row.get("geo") != "Global" and row.get("year")
    }
    country_kpis: dict[str, set[str]] = defaultdict(set)
    for row in metrics:
        geo = norm_geo(row.get("geo") or row.get("entity") or "")
        if geo in {"Global", "Europe", "North America", "Asia-Pacific", "Middle East", "Latin America"}:
            continue
        if row.get("type"):
            country_kpis[geo].add(row["type"])

    checks = {
        "registry_present": int(bool(registry)),
        "backlog_present": int(bool(backlog)),
        "registry_missing_required_columns": sorted(REQUIRED_REGISTRY_COLUMNS.difference(registry_columns)),
        "backlog_missing_required_columns": sorted(REQUIRED_BACKLOG_COLUMNS.difference(backlog_columns)),
        "registry_missing_required_phases": sorted(REQUIRED_PHASES.difference(phases)),
        "backlog_missing_required_phases": sorted(REQUIRED_PHASES.difference(backlog_phases)),
        "registry_missing_core_sources": sorted(CORE_SOURCE_IDS.difference(registry_ids)),
        "backlog_unknown_source_ids": sorted(backlog_source_ids.difference(registry_ids)),
        "phase1_sources": sum(1 for row in registry if row.get("phase") == "1"),
        "phase2_sources": sum(1 for row in registry if row.get("phase") == "2"),
        "phase3_sources": sum(1 for row in registry if row.get("phase") == "3"),
        "phase4_sources": sum(1 for row in registry if row.get("phase") == "4"),
        "isaps_seed_rows": len(isaps_rows),
        "isaps_seed_years": sorted(isaps_years),
        "isaps_seed_year_counts": dict(isaps_year_counts),
        "isaps_missing_required_years": sorted(REQUIRED_ISAPS_YEARS.difference(isaps_years)),
        "isaps_country_year_pairs": len(isaps_country_year_pairs),
        "isaps_us_abbrev_rows": sum(1 for row in isaps_rows if row.get("geo") == "US"),
        "asps_seed_rows": len(asps_rows),
        "asps_seed_years": sorted(asps_years),
        "asps_seed_year_counts": dict(asps_year_counts),
        "asps_missing_required_years": sorted(REQUIRED_ASPS_YEARS.difference(asps_years)),
        "snapshot_market_metric_rows": len(metrics),
        "snapshot_metric_type_counts": dict(metric_type_counts),
        "snapshot_metric_year_counts": dict(metric_year_counts),
        "snapshot_missing_required_years": sorted(REQUIRED_ISAPS_YEARS.difference(snapshot_years)),
        "country_count_with_metrics": len(country_kpis),
        "countries_with_only_one_kpi": sum(1 for values in country_kpis.values() if len(values) == 1),
    }

    blocking = []
    if not checks["registry_present"]:
        blocking.append("registry_present")
    if not checks["backlog_present"]:
        blocking.append("backlog_present")
    for key in [
        "registry_missing_required_columns",
        "backlog_missing_required_columns",
        "registry_missing_required_phases",
        "backlog_missing_required_phases",
        "registry_missing_core_sources",
        "backlog_unknown_source_ids",
    ]:
        if checks[key]:
            blocking.append(key)
    if checks["phase1_sources"] < 3:
        blocking.append("phase1_source_coverage")
    if checks["isaps_seed_rows"] <= 0:
        blocking.append("isaps_seed_rows")
    if checks["isaps_missing_required_years"]:
        blocking.append("isaps_missing_required_years")
    if checks["isaps_us_abbrev_rows"]:
        blocking.append("isaps_country_normalization")
    if checks["asps_seed_rows"] <= 0:
        blocking.append("asps_seed_rows")
    if checks["asps_missing_required_years"]:
        blocking.append("asps_missing_required_years")
    if checks["snapshot_missing_required_years"]:
        blocking.append("snapshot_missing_required_years")

    result = {
        "status": "passed" if not blocking else "failed",
        "registry_rows": len(registry),
        "backlog_rows": len(backlog),
        "checks": checks,
        "blocking_checks": blocking,
        "next_backlog_items": [
            {
                "task_id": row.get("task_id"),
                "phase": row.get("phase"),
                "priority": row.get("priority"),
                "source_id": row.get("source_id"),
                "next_action": row.get("next_action"),
            }
            for row in sorted(backlog, key=lambda item: (int(item.get("phase") or 99), int(item.get("priority") or 99)))[:8]
        ],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not blocking else 1


if __name__ == "__main__":
    sys.exit(main())
