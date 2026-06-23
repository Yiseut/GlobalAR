#!/usr/bin/env python3
"""Extract ISAPS 2020-2024 survey PDFs into raw and normalized datasets.

The extractor deliberately writes two layers:
- raw page text and raw table cells, so every PDF table remains auditable
- normalized long rows for the recurring ISAPS table families
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Iterable


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = Path("E:/shared") / "\u884c\u4e1a\u62a5\u544a"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "isaps_full_survey_2020_2024"


@dataclass(frozen=True)
class ReportConfig:
    year: int
    path: Path
    official_url: str
    country_pages: tuple[int, int]
    surgical_location_pages: tuple[int, int]
    nonsurgical_location_pages: tuple[int, int]
    worldwide_surgical_page: int
    worldwide_nonsurgical_page: int
    worldwide_surgical_region_page: int
    worldwide_nonsurgical_type_page: int
    popular_surgical_pages: tuple[int, int]
    popular_nonsurgical_pages: tuple[int, int]
    surgical_category_rank_pages: tuple[int, int]
    nonsurgical_category_rank_pages: tuple[int, int]
    total_rank_pages: tuple[int, int]
    surgeon_rank_pages: tuple[int, int]
    surgical_group_rank_pages: tuple[int, int]
    nonsurgical_group_rank_pages: tuple[int, int]
    adoption_surgical_pages: tuple[int, int]
    adoption_nonsurgical_pages: tuple[int, int]
    gender_surgical_page: int
    gender_nonsurgical_page: int
    age_page: int
    facility_pages: tuple[int, int]
    medical_tourism_pages: tuple[int, int]
    covid_pages: tuple[int, int] | None
    additional_pages: tuple[int, int]
    resident_pages: tuple[int, int] | None
    other_stats_pages: tuple[int, int] | None = None


REPORTS: dict[int, ReportConfig] = {
    2020: ReportConfig(
        year=2020,
        path=REPORT_DIR / "2020isaps-global-survey.pdf",
        official_url="https://www.isaps.org/media/dzjfg50s/isaps-global-survey_2020.pdf",
        country_pages=(15, 28),
        surgical_location_pages=(29, 29),
        nonsurgical_location_pages=(30, 30),
        worldwide_surgical_page=9,
        worldwide_nonsurgical_page=10,
        worldwide_surgical_region_page=11,
        worldwide_nonsurgical_type_page=12,
        popular_surgical_pages=(31, 31),
        popular_nonsurgical_pages=(32, 32),
        surgical_category_rank_pages=(33, 33),
        nonsurgical_category_rank_pages=(34, 34),
        total_rank_pages=(35, 35),
        surgeon_rank_pages=(36, 36),
        surgical_group_rank_pages=(37, 37),
        nonsurgical_group_rank_pages=(38, 38),
        adoption_surgical_pages=(42, 43),
        adoption_nonsurgical_pages=(44, 45),
        gender_surgical_page=46,
        gender_nonsurgical_page=47,
        age_page=48,
        facility_pages=(49, 49),
        medical_tourism_pages=(50, 50),
        covid_pages=(55, 55),
        additional_pages=(58, 58),
        resident_pages=(59, 59),
    ),
    2021: ReportConfig(
        year=2021,
        path=REPORT_DIR / "2021isaps-global-survey.pdf",
        official_url="https://www.isaps.org/media/vdpdanke/isaps-global-survey_2021.pdf",
        country_pages=(15, 28),
        surgical_location_pages=(29, 29),
        nonsurgical_location_pages=(30, 30),
        worldwide_surgical_page=9,
        worldwide_nonsurgical_page=10,
        worldwide_surgical_region_page=11,
        worldwide_nonsurgical_type_page=12,
        popular_surgical_pages=(31, 31),
        popular_nonsurgical_pages=(32, 32),
        surgical_category_rank_pages=(33, 33),
        nonsurgical_category_rank_pages=(34, 34),
        total_rank_pages=(35, 35),
        surgeon_rank_pages=(36, 36),
        surgical_group_rank_pages=(37, 37),
        nonsurgical_group_rank_pages=(38, 38),
        adoption_surgical_pages=(42, 43),
        adoption_nonsurgical_pages=(44, 45),
        gender_surgical_page=46,
        gender_nonsurgical_page=47,
        age_page=48,
        facility_pages=(49, 49),
        medical_tourism_pages=(50, 50),
        covid_pages=(52, 53),
        additional_pages=(55, 55),
        resident_pages=(56, 56),
    ),
    2022: ReportConfig(
        year=2022,
        path=REPORT_DIR / "2022isaps-global-survey.pdf",
        official_url="https://www.isaps.org/media/a0qfm4h3/isaps-global-survey_2022.pdf",
        country_pages=(15, 30),
        surgical_location_pages=(31, 31),
        nonsurgical_location_pages=(32, 32),
        worldwide_surgical_page=9,
        worldwide_nonsurgical_page=10,
        worldwide_surgical_region_page=11,
        worldwide_nonsurgical_type_page=12,
        popular_surgical_pages=(33, 33),
        popular_nonsurgical_pages=(34, 34),
        surgical_category_rank_pages=(35, 35),
        nonsurgical_category_rank_pages=(36, 36),
        total_rank_pages=(37, 37),
        surgeon_rank_pages=(38, 38),
        surgical_group_rank_pages=(39, 39),
        nonsurgical_group_rank_pages=(40, 40),
        adoption_surgical_pages=(44, 45),
        adoption_nonsurgical_pages=(46, 47),
        gender_surgical_page=48,
        gender_nonsurgical_page=49,
        age_page=50,
        facility_pages=(51, 51),
        medical_tourism_pages=(52, 52),
        covid_pages=None,
        additional_pages=(54, 54),
        resident_pages=(55, 55),
    ),
    2023: ReportConfig(
        year=2023,
        path=REPORT_DIR / "2023isaps-global-survey.pdf",
        official_url="https://www.isaps.org/media/rxnfqibn/isaps-global-survey_2023.pdf",
        country_pages=(15, 37),
        surgical_location_pages=(38, 39),
        nonsurgical_location_pages=(40, 41),
        worldwide_surgical_page=9,
        worldwide_nonsurgical_page=10,
        worldwide_surgical_region_page=11,
        worldwide_nonsurgical_type_page=12,
        popular_surgical_pages=(42, 42),
        popular_nonsurgical_pages=(43, 43),
        surgical_category_rank_pages=(44, 44),
        nonsurgical_category_rank_pages=(45, 45),
        total_rank_pages=(46, 46),
        surgeon_rank_pages=(47, 47),
        surgical_group_rank_pages=(48, 48),
        nonsurgical_group_rank_pages=(49, 49),
        adoption_surgical_pages=(53, 56),
        adoption_nonsurgical_pages=(57, 58),
        gender_surgical_page=60,
        gender_nonsurgical_page=61,
        age_page=62,
        facility_pages=(63, 63),
        medical_tourism_pages=(64, 64),
        covid_pages=None,
        additional_pages=(68, 69),
        resident_pages=(66, 67),
    ),
    2024: ReportConfig(
        year=2024,
        path=REPORT_DIR / "2024 isaps-global-survey.pdf",
        official_url="https://www.isaps.org/media/30xldsyf/isaps-global-survey-2024.pdf",
        country_pages=(15, 46),
        surgical_location_pages=(47, 50),
        nonsurgical_location_pages=(51, 54),
        worldwide_surgical_page=9,
        worldwide_nonsurgical_page=10,
        worldwide_surgical_region_page=11,
        worldwide_nonsurgical_type_page=12,
        popular_surgical_pages=(55, 55),
        popular_nonsurgical_pages=(56, 56),
        surgical_category_rank_pages=(57, 57),
        nonsurgical_category_rank_pages=(58, 58),
        total_rank_pages=(59, 59),
        surgeon_rank_pages=(60, 60),
        surgical_group_rank_pages=(61, 61),
        nonsurgical_group_rank_pages=(62, 62),
        adoption_surgical_pages=(66, 69),
        adoption_nonsurgical_pages=(70, 73),
        gender_surgical_page=75,
        gender_nonsurgical_page=76,
        age_page=77,
        facility_pages=(78, 78),
        medical_tourism_pages=(79, 80),
        covid_pages=None,
        additional_pages=(83, 84),
        resident_pages=None,
        other_stats_pages=(81, 81),
    ),
}


RAW_TABLE_CELL_FIELDS = [
    "source_year",
    "source_file",
    "source_url",
    "page",
    "table_index",
    "table_title",
    "row_index",
    "column_index",
    "cell_text",
    "row_text",
]

RAW_PAGE_FIELDS = [
    "source_year",
    "source_file",
    "source_url",
    "page",
    "text",
]

NORMALIZED_FIELDS = [
    "source_year",
    "data_year",
    "source_file",
    "source_url",
    "page",
    "table_index",
    "table_name",
    "metric_family",
    "record_role",
    "procedure_type",
    "procedure_group",
    "procedure",
    "geo",
    "dimension_type",
    "dimension",
    "metric_name",
    "rank",
    "value",
    "value_text",
    "unit",
    "percent",
    "percent_of_total",
    "compare_to_year",
    "note",
    "series_key",
    "row_hash",
]

COMPARABILITY_FIELDS = [
    "series_key",
    "metric_family",
    "procedure_type",
    "procedure_group",
    "procedure",
    "geo",
    "dimension_type",
    "dimension",
    "metric_name",
    "unit",
    "year_count",
    "years",
    "missing_2020_2024",
    "comparability_class",
    "note",
]


COUNTRY_MAP = {
    "WORLD-WIDE": "Global",
    "WORLDWIDE": "Global",
    "WORLDWIDE TOTALS": "Global",
    "WORLD WIDE TOTALS": "Global",
    "WORLD WIDE": "Global",
    "US": "United States",
    "USA": "United States",
    "USA**": "United States",
    "UNITED STATES": "United States",
    "TURKEY": "Turkiye",
    "TURKIYE": "Turkiye",
    "IRAN (ISLAMIC REPUBLIC OF)": "Iran",
    "IRAN ISLAMIC REPUBLIC OF": "Iran",
    "KOREA REPUBLIC OF SOUTH KOREA": "South Korea",
    "KOREA, REPUBLIC OF (SOUTH KOREA)": "South Korea",
    "UNITED KINGDOM": "UK",
    "U.K.": "UK",
    "UK": "UK",
    "CHINESE TAIPEI": "Chinese Taipei",
    "UAE": "UAE",
}

GROUP_LABELS = {
    "FACE & HEAD",
    "BODY & EXTREMITIES",
    "BREAST",
    "INJECTABLES",
    "INJECTABLES - FACE",
    "INJECTABLES - BODY",
    "FACIAL REJUVENATION",
    "OTHER",
    "TOTAL",
}


def now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def clean_text(value: Any) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u6bcf": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\ufeff": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    return text


def clean_header(value: Any) -> str:
    return clean_text(value).replace("PERCENTAGE", "Percentage").replace("PROCEDURES", "Procedures")


def norm_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", clean_text(value).upper()).strip()


def canonical_geo(value: Any) -> str:
    text = clean_text(value)
    text = re.sub(r"\*+", "", text)
    key = norm_key(text)
    if key in COUNTRY_MAP:
        return COUNTRY_MAP[key]
    # Fix common table-wrap variants.
    if key.startswith("IRAN "):
        return "Iran"
    if "SOUTH KOREA" in key:
        return "South Korea"
    if key == "":
        return ""
    return text.title() if text.isupper() else text


def canonical_procedure(value: Any) -> str:
    text = clean_text(value)
    mapping = {
        "Facelift": "Face Lift",
        "Fat Grafting (face)": "Fat Grafting - Face",
        "Fat Grafting - Face": "Fat Grafting - Face",
        "Face Lift (All Types)": "Face Lift",
        "Face Lift (all types)": "Face Lift",
        "Total Injectables Procedures": "Total Injectables Procedures",
        "Total Non-Surgical Procedures": "Total Non-Surgical Procedures",
        "Total Nonsurgical Procedures": "Total Non-Surgical Procedures",
        "Calcium Hydroxyapatite": "Calcium Hydroxylapatite",
    }
    return mapping.get(text, text)


def is_na(value: Any) -> bool:
    text = clean_text(value).upper()
    return text in {"", "N/A", "NA", "NONE", "-"}


def parse_number(value: Any) -> float | None:
    text = clean_text(value)
    if is_na(text):
        return None
    text = text.replace("%", "")
    # Some 2021 table cells render millions as 12,882.055.
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d{3}", text):
        text = text.replace(".", ",")
    text = text.replace(",", "")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    return float(match.group(0))


def parse_int(value: Any) -> int | None:
    number = parse_number(value)
    if number is None:
        return None
    return int(round(number))


def parse_percent(value: Any) -> float | None:
    text = clean_text(value)
    if "%" not in text and not re.search(r"-?\d", text):
        return None
    number = parse_number(text)
    return number


def value_has_percent(value: Any) -> bool:
    return "%" in clean_text(value)


def row_hash(*parts: Any) -> str:
    payload = "|".join(clean_text(part) for part in parts)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def page_range(bounds: tuple[int, int] | None) -> list[int]:
    if not bounds:
        return []
    start, stop = bounds
    return list(range(start, stop + 1))


def table_title(table: list[list[Any]]) -> str:
    if not table:
        return ""
    first = " ".join(clean_text(cell) for cell in table[0] if clean_text(cell))
    second = ""
    if len(table) > 1:
        second = " ".join(clean_text(cell) for cell in table[1] if clean_text(cell))
    if first:
        return first
    return second


def is_title_table(table: list[list[Any]]) -> bool:
    if len(table) <= 2 and max((len(row) for row in table), default=0) <= 3:
        return True
    return False


def significant_tables(tables: list[list[list[Any]]]) -> list[tuple[int, list[list[Any]]]]:
    return [(idx, table) for idx, table in enumerate(tables) if not is_title_table(table)]


def find_header_index(table: list[list[Any]], required_terms: list[str], scan_rows: int = 4) -> int | None:
    terms = [norm_key(term) for term in required_terms]
    for idx, row in enumerate(table[:scan_rows]):
        row_key = norm_key(" ".join(clean_text(cell) for cell in row))
        if all(term in row_key for term in terms):
            return idx
    return None


def add_row(rows: list[dict[str, Any]], config: ReportConfig, **kwargs: Any) -> None:
    row = {field: "" for field in NORMALIZED_FIELDS}
    row.update(
        {
            "source_year": config.year,
            "source_file": str(config.path),
            "source_url": config.official_url,
            "data_year": kwargs.get("data_year", config.year),
            "record_role": kwargs.get("record_role", "current"),
        }
    )
    row.update(kwargs)
    series_parts = [
        row.get("metric_family"),
        row.get("procedure_type"),
        row.get("procedure_group"),
        row.get("procedure"),
        row.get("geo"),
        row.get("dimension_type"),
        row.get("dimension"),
        row.get("metric_name"),
        row.get("unit"),
    ]
    row["series_key"] = "|".join(clean_text(part) for part in series_parts)
    row["row_hash"] = row_hash(
        row.get("source_year"),
        row.get("data_year"),
        row.get("page"),
        row.get("table_index"),
        row.get("metric_family"),
        row.get("procedure"),
        row.get("geo"),
        row.get("dimension_type"),
        row.get("dimension"),
        row.get("metric_name"),
        row.get("record_role"),
        row.get("compare_to_year"),
        row.get("value_text"),
    )
    rows.append(row)


def extract_raw(config: ReportConfig, pdf: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw_pages: list[dict[str, Any]] = []
    raw_cells: list[dict[str, Any]] = []
    for page_idx, page in enumerate(pdf.pages, start=1):
        text = page.extract_text() or ""
        raw_pages.append(
            {
                "source_year": config.year,
                "source_file": str(config.path),
                "source_url": config.official_url,
                "page": page_idx,
                "text": text,
            }
        )
        for table_idx, table in enumerate(page.extract_tables() or []):
            title = table_title(table)
            for row_idx, row in enumerate(table):
                cleaned = [clean_text(cell) for cell in row]
                row_text = " | ".join(cell for cell in cleaned if cell)
                for col_idx, cell in enumerate(cleaned):
                    raw_cells.append(
                        {
                            "source_year": config.year,
                            "source_file": str(config.path),
                            "source_url": config.official_url,
                            "page": page_idx,
                            "table_index": table_idx,
                            "table_title": title,
                            "row_index": row_idx,
                            "column_index": col_idx,
                            "cell_text": cell,
                            "row_text": row_text,
                        }
                    )
    return raw_pages, raw_cells


def extract_years_from_headers(headers: list[str]) -> tuple[dict[int, int], dict[int, tuple[int, int]]]:
    year_cols: dict[int, int] = {}
    change_cols: dict[int, tuple[int, int]] = {}
    for idx, header in enumerate(headers):
        h = clean_text(header)
        in_match = re.search(r"in\s+(20\d{2})", h, re.I)
        if in_match:
            year_cols[idx] = int(in_match.group(1))
        elif re.fullmatch(r"20\d{2}", h):
            year_cols[idx] = int(h)
        change_match = re.search(r"(20\d{2})\s+vs\.?\s+(20\d{2})", h, re.I)
        if change_match:
            change_cols[idx] = (int(change_match.group(1)), int(change_match.group(2)))
    return year_cols, change_cols


def parse_worldwide_ranked_table(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if not table or len(table[0]) < 4:
            continue
        header = [clean_text(cell) for cell in table[0]]
        if "RANK" not in norm_key(header[0]) or "PROCEDURES" not in norm_key(header[1]):
            continue
        year_cols, change_cols = extract_years_from_headers(header)
        for source_row in table[1:]:
            if len(source_row) < 4 or is_na(source_row[1]):
                continue
            rank = clean_text(source_row[0])
            procedure = canonical_procedure(source_row[1])
            current_value = parse_int(source_row[2])
            pct_total = parse_percent(source_row[3])
            if current_value is not None:
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="worldwide_ranked_procedures",
                    metric_family="procedure_volume",
                    record_role="current",
                    procedure_type=procedure_type,
                    procedure=procedure,
                    geo="Global",
                    metric_name="procedure volume",
                    rank=rank,
                    value=current_value,
                    value_text=clean_text(source_row[2]),
                    unit="procedures",
                    percent_of_total=pct_total if pct_total is not None else "",
                )
            for col_idx, year in year_cols.items():
                if col_idx >= len(source_row):
                    continue
                value = parse_int(source_row[col_idx])
                if value is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="worldwide_ranked_procedures",
                    metric_family="procedure_volume",
                    record_role="comparator",
                    data_year=year,
                    procedure_type=procedure_type,
                    procedure=procedure,
                    geo="Global",
                    metric_name="procedure volume",
                    rank=rank,
                    value=value,
                    value_text=clean_text(source_row[col_idx]),
                    unit="procedures",
                    note=f"Comparator column in {config.year} report.",
                )
            for col_idx, (current_year, compare_to_year) in change_cols.items():
                if col_idx >= len(source_row):
                    continue
                pct = parse_percent(source_row[col_idx])
                if pct is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="worldwide_ranked_procedures",
                    metric_family="procedure_percent_change",
                    record_role="percent_change",
                    data_year=current_year,
                    procedure_type=procedure_type,
                    procedure=procedure,
                    geo="Global",
                    metric_name="percent change",
                    rank=rank,
                    value=pct,
                    value_text=clean_text(source_row[col_idx]),
                    unit="percent_change",
                    compare_to_year=compare_to_year,
                )


def parse_worldwide_grouped_table(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if not table or len(table[0]) < 3:
            continue
        header = [clean_text(cell) for cell in table[0]]
        if not any(re.fullmatch(r"20\d{2}", h) for h in header):
            continue
        year_cols, change_cols = extract_years_from_headers(header)
        for source_row in table[1:]:
            if len(source_row) < 2:
                continue
            procedure = canonical_procedure(source_row[0])
            if is_na(procedure) or "PERCENTAGE CHANGE" in norm_key(procedure):
                continue
            for col_idx, year in year_cols.items():
                if col_idx >= len(source_row):
                    continue
                value = parse_int(source_row[col_idx])
                if value is None:
                    continue
                role = "current" if year == config.year else "comparator"
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="worldwide_grouped_procedure_table",
                    metric_family="procedure_volume",
                    record_role=role,
                    data_year=year,
                    procedure_type=procedure_type,
                    procedure=procedure,
                    geo="Global",
                    metric_name="procedure volume",
                    value=value,
                    value_text=clean_text(source_row[col_idx]),
                    unit="procedures",
                )
            for col_idx, (current_year, compare_to_year) in change_cols.items():
                if col_idx >= len(source_row):
                    continue
                pct = parse_percent(source_row[col_idx])
                if pct is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="worldwide_grouped_procedure_table",
                    metric_family="procedure_percent_change",
                    record_role="percent_change",
                    data_year=current_year,
                    procedure_type=procedure_type,
                    procedure=procedure,
                    geo="Global",
                    metric_name="percent change",
                    value=pct,
                    value_text=clean_text(source_row[col_idx]),
                    unit="percent_change",
                    compare_to_year=compare_to_year,
                )


def parse_location_matrix(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
    metric_family: str,
    unit: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 2:
            continue
        header_idx = find_header_index(table, ["procedures"], scan_rows=4)
        if header_idx is None:
            header_idx = find_header_index(table, ["surgeons"], scan_rows=4)
        if header_idx is None:
            continue
        header = [clean_text(cell) for cell in table[header_idx]]
        if len(header) < 3:
            continue
        if "PROCEDURES" not in norm_key(header[0]) and "SURGEONS" not in norm_key(header[0]):
            continue
        geos = [canonical_geo(h) for h in header[1:]]
        current_group = ""
        for source_row in table[header_idx + 1 :]:
            label = canonical_procedure(source_row[0] if source_row else "")
            if is_na(label):
                continue
            key = norm_key(label)
            nonempty_values = [clean_text(cell) for cell in source_row[1:] if clean_text(cell)]
            if key in GROUP_LABELS or (label.isupper() and not nonempty_values):
                current_group = label.title() if label.isupper() else label
                continue
            row_metric_family = metric_family
            row_unit = unit
            row_proc_type = procedure_type
            row_group = current_group
            metric_name = "procedure volume"
            if "ESTIMATED NUMBER OF PLASTIC SURGEONS" in key:
                row_metric_family = "estimated_plastic_surgeons"
                row_unit = "surgeons"
                row_proc_type = ""
                row_group = "Workforce"
                metric_name = "estimated plastic surgeons"
            elif "TOTAL SURGICAL PROCEDURES" in key:
                row_group = ""
                row_proc_type = "surgical"
                label = "Total Surgical Procedures"
            elif "TOTAL NON SURGICAL PROCEDURES" in key or "TOTAL NONSURGICAL PROCEDURES" in key:
                row_group = ""
                row_proc_type = "non_surgical"
                label = "Total Non-Surgical Procedures"
            for col_idx, geo in enumerate(geos, start=1):
                if col_idx >= len(source_row) or not geo:
                    continue
                cell = clean_text(source_row[col_idx])
                value = parse_percent(cell) if row_unit == "percent" else parse_int(cell)
                if value is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="location_matrix",
                    metric_family=row_metric_family,
                    record_role="current",
                    procedure_type=row_proc_type,
                    procedure_group=row_group,
                    procedure="" if row_metric_family == "estimated_plastic_surgeons" else label,
                    geo=geo,
                    metric_name=metric_name,
                    value=value,
                    value_text=cell,
                    unit=row_unit,
                    percent=value if row_unit == "percent" else "",
                )


def parse_country_page_totals(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    text: str,
) -> None:
    country = ""
    if tables and tables[0]:
        country = canonical_geo(table_title(tables[0]))
    if not country:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        country = canonical_geo(lines[0]) if lines else ""
    if not country:
        return
    flat = clean_text(text)

    def match_int(pattern: str) -> int | None:
        match = re.search(pattern, flat, re.I)
        return parse_int(match.group(1)) if match else None

    total = None
    total_match = re.search(r"TOTAL NUMBER OF\s+PROCEDURES(?:\s+IN\s+THE\s+[A-Z ]+)?\s+([0-9,]+)", flat, re.I)
    if total_match:
        total = parse_int(total_match.group(1))
    else:
        lines = [clean_text(line) for line in text.splitlines() if clean_text(line)]
        for idx, line in enumerate(lines):
            if "TOTAL NUMBER OF" in norm_key(line):
                for next_line in lines[idx + 1 : idx + 8]:
                    value = parse_int(next_line)
                    if value is not None:
                        total = value
                        break
                break

    patterns = [
        ("all", "Total Procedures", total),
        (
            "surgical",
            "Total Surgical Procedures",
            match_int(r"TOTAL SURGICAL PROCEDURES\s+([0-9,]+)"),
        ),
        (
            "non_surgical",
            "Total Non-Surgical Procedures",
            match_int(r"TOTAL NON[- ]?SURGICAL(?:\s+POCEDURES)?\s+PROCEDURES\s+([0-9,]+)"),
        ),
    ]
    for procedure_type, label, value in patterns:
        if value is None:
            continue
        add_row(
            rows,
            config,
            page=page_no,
            table_index="text",
            table_name="country_page_totals",
            metric_family="procedure_volume",
            record_role="current",
            procedure_type=procedure_type,
            procedure=label,
            geo=country,
            metric_name="procedure volume",
            value=value,
            value_text=str(value),
            unit="procedures",
            note="Extracted from country/location page header text.",
        )


def parse_country_page_most_common(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    country = ""
    if tables and tables[0]:
        title = table_title(tables[0])
        country = canonical_geo(title)
    if not country:
        return
    for table_idx, table in significant_tables(tables):
        if not table:
            continue
        first = norm_key(table[0][0] if table[0] else "")
        if "MOST COMMON PROCEDURES" not in first:
            continue
        rank = 0
        for source_row in table[2:]:
            if len(source_row) < 3:
                continue
            procedure = canonical_procedure(source_row[0])
            value = parse_int(source_row[1])
            pct = parse_percent(source_row[2])
            if is_na(procedure) or value is None:
                continue
            rank += 1
            proc_type = "non_surgical" if procedure in NONSURGICAL_PROCEDURES else "surgical"
            add_row(
                rows,
                config,
                page=page_no,
                table_index=table_idx,
                table_name="country_page_most_common_procedures",
                metric_family="procedure_rank",
                record_role="current",
                procedure_type=proc_type,
                procedure=procedure,
                geo=country,
                metric_name="country most common procedure rank",
                rank=rank,
                value=value,
                value_text=clean_text(source_row[1]),
                unit="procedures",
                percent_of_total=pct if pct is not None else "",
            )


NONSURGICAL_PROCEDURES = {
    "Botulinum Toxin",
    "Hyaluronic Acid",
    "Hair Removal",
    "Non-Surgical Skin Tightening",
    "Chemical Peel",
    "Full Field Ablative",
    "Non-Surgical Fat Reduction",
    "Poly-L-Lactic Acid",
    "Calcium Hydroxylapatite",
    "Tattoo Removal",
    "Micro-Ablative Resurfacing",
    "Photo Rejuvenation",
    "Cellulite Treatment",
}


def parse_popular_by_location(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 3:
            continue
        procedure = canonical_procedure(table[0][0])
        if is_na(procedure) or "RANK" in norm_key(procedure):
            continue
        for source_row in table[2:]:
            if len(source_row) < 4:
                continue
            rank = clean_text(source_row[0])
            geo = canonical_geo(source_row[1])
            value = parse_int(source_row[2])
            pct = parse_percent(source_row[3])
            if not rank or not geo or value is None:
                continue
            add_row(
                rows,
                config,
                page=page_no,
                table_index=table_idx,
                table_name="most_popular_procedures_by_location",
                metric_family="procedure_location_rank",
                record_role="current",
                procedure_type=procedure_type,
                procedure=procedure.title() if procedure.isupper() else procedure,
                geo=geo,
                metric_name="location rank for procedure",
                rank=rank,
                value=value,
                value_text=clean_text(source_row[2]),
                unit="procedures",
                percent_of_total=pct if pct is not None else "",
            )


def parse_category_rank(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 2:
            continue
        header = [clean_text(cell) for cell in table[0]]
        if not header or "RANK" not in norm_key(header[0]):
            continue
        category = clean_text(header[-1])
        for source_row in table[1:]:
            if len(source_row) < 4:
                continue
            rank = clean_text(source_row[0])
            geo = canonical_geo(source_row[1])
            value = parse_int(source_row[2])
            pct = parse_percent(source_row[3])
            if not rank or not geo or value is None:
                continue
            add_row(
                rows,
                config,
                page=page_no,
                table_index=table_idx,
                table_name="category_totals_ranked",
                metric_family="procedure_category_rank",
                record_role="current",
                procedure_type=procedure_type,
                procedure_group=category.title() if category.isupper() else category,
                geo=geo,
                metric_name="category rank by location",
                rank=rank,
                value=value,
                value_text=clean_text(source_row[2]),
                unit="procedures",
                percent_of_total=pct if pct is not None else "",
            )


def parse_total_rank(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 3:
            continue
        # Usually row 1 is the real header after a TOP 10 banner.
        header_idx = 1 if len(table[0]) >= 2 and "TOP" in norm_key(table[0][0]) else 0
        for source_row in table[header_idx + 1 :]:
            if len(source_row) < 6:
                continue
            rank = clean_text(source_row[0])
            geo = canonical_geo(source_row[1])
            if not rank or not geo:
                continue
            metrics = [
                ("surgical procedure volume", "surgical", 2, 3),
                ("non-surgical procedure volume", "non_surgical", 4, 5),
                ("total procedure volume", "all", 6, 7),
            ]
            for metric_name, proc_type, value_col, pct_col in metrics:
                if value_col >= len(source_row):
                    continue
                value = parse_int(source_row[value_col])
                if value is None:
                    continue
                pct = parse_percent(source_row[pct_col]) if pct_col < len(source_row) else None
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="total_number_of_procedures_rank",
                    metric_family="procedure_total_rank",
                    record_role="current",
                    procedure_type=proc_type,
                    geo=geo,
                    metric_name=metric_name,
                    rank=rank,
                    value=value,
                    value_text=clean_text(source_row[value_col]),
                    unit="procedures",
                    percent_of_total=pct if pct is not None else "",
                )


def parse_group_rank(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 3:
            continue
        current_geo = ""
        for source_row in table[1:]:
            first = clean_text(source_row[0] if source_row else "")
            second = clean_text(source_row[1] if len(source_row) > 1 else "")
            if first and not parse_int(first) and not second:
                current_geo = canonical_geo(first)
                continue
            rank = first
            if not rank or not current_geo or len(source_row) < 4:
                continue
            value = parse_int(source_row[2])
            pct = parse_percent(source_row[3])
            if value is None:
                continue
            group = clean_text(source_row[1])
            add_row(
                rows,
                config,
                page=page_no,
                table_index=table_idx,
                table_name="procedure_group_rank",
                metric_family="procedure_group_rank",
                record_role="current",
                procedure_type=procedure_type,
                procedure_group=group,
                geo=current_geo,
                metric_name="procedure group rank within location",
                rank=rank,
                value=value,
                value_text=clean_text(source_row[2]),
                unit="procedures",
                percent_of_total=pct if pct is not None else "",
            )


def parse_surgeon_rank(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    for table_idx, table in significant_tables(tables):
        for source_row in table:
            # Some ranking tables are split into two rank/location/value/% blocks.
            for offset in (0, 4):
                if len(source_row) <= offset + 3:
                    continue
                rank = clean_text(source_row[offset])
                geo = canonical_geo(source_row[offset + 1])
                value = parse_int(source_row[offset + 2])
                pct = parse_percent(source_row[offset + 3])
                if not rank or not rank.isdigit() or not geo or value is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="estimated_plastic_surgeons_rank",
                    metric_family="estimated_plastic_surgeons_rank",
                    record_role="current",
                    procedure_group="Workforce",
                    geo=geo,
                    metric_name="estimated plastic surgeons",
                    rank=rank,
                    value=value,
                    value_text=clean_text(source_row[offset + 2]),
                    unit="surgeons",
                    percent_of_total=pct if pct is not None else "",
                )


def parse_gender_distribution(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    procedure_type: str,
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 2:
            continue
        header_idx = find_header_index(table, ["rank", "female"], scan_rows=3)
        if header_idx is None:
            header_idx = find_header_index(table, ["rank", "male"], scan_rows=3)
        if header_idx is None:
            continue
        header = [norm_key(cell) for cell in table[header_idx]]
        blocks: list[tuple[str, int]] = []
        if len(header) > 1 and "FEMALE" in header[1]:
            blocks.append(("Female", 0))
        if len(header) > 5 and "MALE" in header[5]:
            blocks.append(("Male", 4))
        if not blocks and len(header) > 1 and "MALE" in header[1]:
            blocks.append(("Male", 0))
        for source_row in table[header_idx + 1 :]:
            for gender, offset in blocks:
                if len(source_row) < offset + 4:
                    continue
                rank = clean_text(source_row[offset])
                procedure = canonical_procedure(source_row[offset + 1])
                value = parse_int(source_row[offset + 2])
                pct = parse_percent(source_row[offset + 3])
                if is_na(procedure) or value is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="gender_distribution",
                    metric_family="gender_distribution",
                    record_role="current",
                    procedure_type=procedure_type,
                    procedure=procedure,
                    geo="Global",
                    dimension_type="gender",
                    dimension=gender,
                    metric_name="procedure volume by gender",
                    rank=rank,
                    value=value,
                    value_text=clean_text(source_row[offset + 2]),
                    unit="procedures",
                    percent=pct if pct is not None else "",
                )


def parse_age_distribution(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    age_groups = [
        "17 years or younger",
        "18-34 years old",
        "35-50 years old",
        "51-64 years old",
        "65 years or older",
    ]
    for table_idx, table in significant_tables(tables):
        if len(table) < 4:
            continue
        for source_row in table[2:]:
            if len(source_row) < 11:
                continue
            procedure = canonical_procedure(source_row[0])
            if is_na(procedure):
                continue
            for group_idx, age_group in enumerate(age_groups):
                value_col = 1 + group_idx * 2
                pct_col = value_col + 1
                value = parse_int(source_row[value_col])
                pct = parse_percent(source_row[pct_col])
                if value is None:
                    continue
                proc_type = "non_surgical" if procedure in NONSURGICAL_PROCEDURES else "surgical"
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="age_distribution",
                    metric_family="age_distribution",
                    record_role="current",
                    procedure_type=proc_type,
                    procedure=procedure,
                    geo="Global",
                    dimension_type="age_group",
                    dimension=age_group,
                    metric_name="procedure volume by age group",
                    value=value,
                    value_text=clean_text(source_row[value_col]),
                    unit="procedures",
                    percent=pct if pct is not None else "",
                )


def parse_facility_distribution(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 2:
            continue
        header_idx = find_header_index(table, ["office", "hospital"], scan_rows=5)
        if header_idx is None:
            continue
        header = [clean_text(cell) for cell in table[header_idx]]
        if len(header) < 3:
            continue
        if "OFFICE" not in norm_key(" ".join(header)) and "HOSPITAL" not in norm_key(" ".join(header)):
            continue
        facility_types = [clean_text(h).title() for h in header[1:]]
        for source_row in table[header_idx + 1 :]:
            if len(source_row) < 2:
                continue
            geo = canonical_geo(source_row[0])
            if not geo:
                continue
            for col_idx, facility in enumerate(facility_types, start=1):
                if col_idx >= len(source_row):
                    continue
                pct = parse_percent(source_row[col_idx])
                if pct is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="cosmetic_procedures_by_facility_location",
                    metric_family="facility_distribution",
                    record_role="current",
                    geo=geo,
                    dimension_type="facility_type",
                    dimension=facility,
                    metric_name="procedure location share",
                    value=pct,
                    value_text=clean_text(source_row[col_idx]),
                    unit="percent",
                    percent=pct,
                )


def parse_medical_tourism(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    for table_idx, table in significant_tables(tables):
        for source_row in table[2:]:
            if len(source_row) < 3:
                continue
            geo = canonical_geo(source_row[0])
            median = parse_percent(source_row[1])
            average = parse_percent(source_row[2])
            if not geo or median is None:
                continue
            add_row(
                rows,
                config,
                page=page_no,
                table_index=table_idx,
                table_name="medical_tourism",
                metric_family="medical_tourism",
                record_role="current",
                geo=geo,
                metric_name="median foreign patient share",
                value=median,
                value_text=clean_text(source_row[1]),
                unit="percent",
                percent=median,
            )
            if average is not None:
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="medical_tourism",
                    metric_family="medical_tourism",
                    record_role="current",
                    geo=geo,
                    metric_name="average foreign patient share",
                    value=average,
                    value_text=clean_text(source_row[2]),
                    unit="percent",
                    percent=average,
                )
            for origin_idx in range(3):
                col = 3 + origin_idx
                if col >= len(source_row):
                    continue
                origin = canonical_geo(source_row[col])
                if not origin:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="medical_tourism",
                    metric_family="medical_tourism_origin_rank",
                    record_role="current",
                    geo=geo,
                    dimension_type="origin_country_rank",
                    dimension=str(origin_idx + 1),
                    metric_name="frequently cited origin country",
                    rank=origin_idx + 1,
                    value_text=origin,
                    unit="rank",
                )


def parse_additional_stats(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
    family: str = "additional_statistics",
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 2:
            continue
        header_idx = None
        for idx, row in enumerate(table[:4]):
            cells = [canonical_geo(cell) for cell in row]
            if len([cell for cell in cells[1:] if cell]) >= 3 and any(cell in {"Global", "Worldwide", "United States"} for cell in cells):
                header_idx = idx
                break
        if header_idx is None:
            continue
        header = [canonical_geo(cell) for cell in table[header_idx]]
        if len(header) < 3:
            continue
        geos = header[1:]
        current_section = ""
        for source_row in table[header_idx + 1 :]:
            label = clean_text(source_row[0] if source_row else "")
            if not label:
                continue
            values = [clean_text(cell) for cell in source_row[1:]]
            has_values = any(v and v.upper() != "N/A" for v in values)
            if not has_values:
                current_section = label
                continue
            for col_idx, geo in enumerate(geos, start=1):
                if col_idx >= len(source_row) or not geo:
                    continue
                cell = clean_text(source_row[col_idx])
                if is_na(cell):
                    continue
                unit = "percent" if value_has_percent(cell) else "value"
                value = parse_percent(cell) if unit == "percent" else parse_number(cell)
                if value is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name=family,
                    metric_family=family,
                    record_role="current",
                    geo=geo,
                    dimension_type=current_section,
                    dimension=label,
                    metric_name=f"{current_section} - {label}" if current_section else label,
                    value=value,
                    value_text=cell,
                    unit=unit,
                    percent=value if unit == "percent" else "",
                )


def parse_covid_impact(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 4:
            continue
        header_row = None
        for candidate in table[:4]:
            if any("WORLD" in norm_key(cell) for cell in candidate):
                header_row = candidate
                break
        if not header_row:
            continue
        geos = [canonical_geo(cell) for cell in header_row]
        for source_row in table:
            label = clean_text(source_row[0] if source_row else "")
            if not label or "WHICH OF THE FOLLOWING" in norm_key(label):
                continue
            for col_idx, geo in enumerate(geos):
                if col_idx >= len(source_row) or not geo:
                    continue
                pct = parse_percent(source_row[col_idx])
                if pct is None:
                    continue
                add_row(
                    rows,
                    config,
                    page=page_no,
                    table_index=table_idx,
                    table_name="covid_impact",
                    metric_family="covid_impact",
                    record_role="current",
                    geo=geo,
                    dimension_type="covid_impact_item",
                    dimension=label,
                    metric_name="COVID impact share",
                    value=pct,
                    value_text=clean_text(source_row[col_idx]),
                    unit="percent",
                    percent=pct,
                )


def parse_other_procedure_stats(
    rows: list[dict[str, Any]],
    config: ReportConfig,
    page_no: int,
    tables: list[list[list[Any]]],
) -> None:
    for table_idx, table in significant_tables(tables):
        if len(table) < 2:
            continue
        title = clean_text(table[0][0])
        if not title or "MEDIAN" not in norm_key(" ".join(clean_text(c) for r in table for c in r)):
            continue
        metric_title = title
        for source_row in table[1:]:
            if len(source_row) < 2:
                continue
            stat = clean_text(source_row[0])
            value = parse_number(source_row[1])
            if not stat or value is None:
                continue
            unit = "percent" if value_has_percent(source_row[1]) else "value"
            add_row(
                rows,
                config,
                page=page_no,
                table_index=table_idx,
                table_name="other_procedure_statistics",
                metric_family="other_procedure_statistics",
                record_role="current",
                geo="Global",
                dimension_type="statistic",
                dimension=stat.title(),
                metric_name=metric_title,
                value=value,
                value_text=clean_text(source_row[1]),
                unit=unit,
                percent=value if unit == "percent" else "",
            )


def normalize_report(config: ReportConfig, pdf: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    page_tables: dict[int, list[list[list[Any]]]] = {}
    needed_pages = set(range(1, len(pdf.pages) + 1))
    for page_no in needed_pages:
        page_tables[page_no] = pdf.pages[page_no - 1].extract_tables() or []

    parse_worldwide_ranked_table(
        rows,
        config,
        config.worldwide_surgical_page,
        page_tables[config.worldwide_surgical_page],
        "surgical",
    )
    parse_worldwide_ranked_table(
        rows,
        config,
        config.worldwide_nonsurgical_page,
        page_tables[config.worldwide_nonsurgical_page],
        "non_surgical",
    )
    parse_worldwide_grouped_table(
        rows,
        config,
        config.worldwide_surgical_region_page,
        page_tables[config.worldwide_surgical_region_page],
        "surgical",
    )
    parse_worldwide_grouped_table(
        rows,
        config,
        config.worldwide_nonsurgical_type_page,
        page_tables[config.worldwide_nonsurgical_type_page],
        "non_surgical",
    )

    for page_no in page_range(config.surgical_location_pages):
        parse_location_matrix(
            rows,
            config,
            page_no,
            page_tables[page_no],
            "surgical",
            "procedure_volume",
            "procedures",
        )
    for page_no in page_range(config.nonsurgical_location_pages):
        parse_location_matrix(
            rows,
            config,
            page_no,
            page_tables[page_no],
            "non_surgical",
            "procedure_volume",
            "procedures",
        )
    for page_no in page_range(config.country_pages):
        page_text = pdf.pages[page_no - 1].extract_text() or ""
        parse_country_page_totals(rows, config, page_no, page_tables[page_no], page_text)
        parse_country_page_most_common(rows, config, page_no, page_tables[page_no])

    for page_no in page_range(config.popular_surgical_pages):
        parse_popular_by_location(rows, config, page_no, page_tables[page_no], "surgical")
    for page_no in page_range(config.popular_nonsurgical_pages):
        parse_popular_by_location(rows, config, page_no, page_tables[page_no], "non_surgical")
    for page_no in page_range(config.surgical_category_rank_pages):
        parse_category_rank(rows, config, page_no, page_tables[page_no], "surgical")
    for page_no in page_range(config.nonsurgical_category_rank_pages):
        parse_category_rank(rows, config, page_no, page_tables[page_no], "non_surgical")
    for page_no in page_range(config.total_rank_pages):
        parse_total_rank(rows, config, page_no, page_tables[page_no])
    for page_no in page_range(config.surgeon_rank_pages):
        parse_surgeon_rank(rows, config, page_no, page_tables[page_no])
    for page_no in page_range(config.surgical_group_rank_pages):
        parse_group_rank(rows, config, page_no, page_tables[page_no], "surgical")
    for page_no in page_range(config.nonsurgical_group_rank_pages):
        parse_group_rank(rows, config, page_no, page_tables[page_no], "non_surgical")

    for page_no in page_range(config.adoption_surgical_pages):
        parse_location_matrix(
            rows,
            config,
            page_no,
            page_tables[page_no],
            "surgical",
            "surgeon_adoption_rate",
            "percent",
        )
    for page_no in page_range(config.adoption_nonsurgical_pages):
        parse_location_matrix(
            rows,
            config,
            page_no,
            page_tables[page_no],
            "non_surgical",
            "surgeon_adoption_rate",
            "percent",
        )

    parse_gender_distribution(rows, config, config.gender_surgical_page, page_tables[config.gender_surgical_page], "surgical")
    parse_gender_distribution(
        rows,
        config,
        config.gender_nonsurgical_page,
        page_tables[config.gender_nonsurgical_page],
        "non_surgical",
    )
    parse_age_distribution(rows, config, config.age_page, page_tables[config.age_page])

    for page_no in page_range(config.facility_pages):
        parse_facility_distribution(rows, config, page_no, page_tables[page_no])
    for page_no in page_range(config.medical_tourism_pages):
        parse_medical_tourism(rows, config, page_no, page_tables[page_no])
    for page_no in page_range(config.covid_pages):
        parse_covid_impact(rows, config, page_no, page_tables[page_no])
    for page_no in page_range(config.additional_pages):
        parse_additional_stats(rows, config, page_no, page_tables[page_no], "additional_statistics")
    for page_no in page_range(config.resident_pages):
        parse_additional_stats(rows, config, page_no, page_tables[page_no], "resident_statistics")
    for page_no in page_range(config.other_stats_pages):
        parse_other_procedure_stats(rows, config, page_no, page_tables[page_no])

    return rows


def write_csv(path: Path, fields: list[str], rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
            count += 1
    return count


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


def build_comparability(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    series: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("record_role")) != "current":
            continue
        data_year = int(row.get("data_year") or row.get("source_year") or 0)
        if data_year not in {2020, 2021, 2022, 2023, 2024}:
            continue
        key = str(row.get("series_key") or "")
        if not key:
            continue
        item = series.setdefault(
            key,
            {
                "series_key": key,
                "metric_family": row.get("metric_family", ""),
                "procedure_type": row.get("procedure_type", ""),
                "procedure_group": row.get("procedure_group", ""),
                "procedure": row.get("procedure", ""),
                "geo": row.get("geo", ""),
                "dimension_type": row.get("dimension_type", ""),
                "dimension": row.get("dimension", ""),
                "metric_name": row.get("metric_name", ""),
                "unit": row.get("unit", ""),
                "years_set": set(),
            },
        )
        item["years_set"].add(data_year)

    output: list[dict[str, Any]] = []
    full_years = {2020, 2021, 2022, 2023, 2024}
    for item in series.values():
        years_set = item.pop("years_set")
        missing = sorted(full_years - years_set)
        year_count = len(years_set)
        if year_count == 5:
            klass = "trend_5yr"
            note = "Comparable across every report year from 2020 through 2024."
        elif year_count >= 3:
            klass = "trend_partial"
            note = "Comparable as a partial multi-year trend; inspect missing years before charting."
        elif year_count == 2:
            klass = "stage_2yr"
            note = "Only two report-year observations; useful for stage comparison, not a stable trend."
        else:
            klass = "stage_single_year"
            note = "Single report-year observation; usually a new, retired, or one-off metric."
        output.append(
            {
                **item,
                "year_count": year_count,
                "years": ",".join(str(year) for year in sorted(years_set)),
                "missing_2020_2024": ",".join(str(year) for year in missing),
                "comparability_class": klass,
                "note": note,
            }
        )
    output.sort(key=lambda row: (row["comparability_class"], row["metric_family"], row["series_key"]))
    return output


def add_computed_global_all_totals(rows: list[dict[str, Any]], years: list[int]) -> None:
    for year in years:
        config = REPORTS[year]
        exists = any(
            str(row.get("source_year")) == str(year)
            and str(row.get("record_role")) == "current"
            and row.get("metric_family") == "procedure_volume"
            and row.get("geo") == "Global"
            and row.get("procedure_type") == "all"
            and row.get("procedure") == "Total Procedures"
            for row in rows
        )
        if exists:
            continue

        def first_total(procedure_names: set[str]) -> int | None:
            for row in rows:
                if str(row.get("source_year")) != str(year):
                    continue
                if str(row.get("record_role")) != "current":
                    continue
                if row.get("metric_family") != "procedure_volume" or row.get("geo") != "Global":
                    continue
                if canonical_procedure(row.get("procedure")) not in procedure_names:
                    continue
                value = parse_int(row.get("value"))
                if value is not None:
                    return value
            return None

        surgical = first_total({"TOTAL SURGICAL PROCEDURES", "Total Surgical Procedures"})
        nonsurgical = first_total({"TOTAL NON-SURGICAL PROCEDURES", "Total Non-Surgical Procedures"})
        if surgical is None or nonsurgical is None:
            continue
        total = surgical + nonsurgical
        add_row(
            rows,
            config,
            page="computed",
            table_index="computed",
            table_name="computed_global_total",
            metric_family="procedure_volume",
            record_role="current",
            procedure_type="all",
            procedure="Total Procedures",
            geo="Global",
            metric_name="procedure volume",
            value=total,
            value_text=str(total),
            unit="procedures",
            note="Computed as global surgical procedures plus global non-surgical procedures from same ISAPS report.",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract full ISAPS survey PDF data for 2020-2024.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--years", nargs="*", type=int, default=sorted(REPORTS))
    args = parser.parse_args()

    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:
        raise SystemExit("pdfplumber is required. Use the bundled Codex Python runtime or install pdfplumber.") from exc

    ensure_dir(args.output_dir)

    all_raw_pages: list[dict[str, Any]] = []
    all_raw_cells: list[dict[str, Any]] = []
    all_normalized: list[dict[str, Any]] = []
    report_stats: list[dict[str, Any]] = []

    for year in args.years:
        if year not in REPORTS:
            raise SystemExit(f"Unsupported year: {year}")
        config = REPORTS[year]
        if not config.path.exists():
            raise SystemExit(f"Missing PDF for {year}: {config.path}")
        with pdfplumber.open(config.path) as pdf:
            raw_pages, raw_cells = extract_raw(config, pdf)
            normalized = normalize_report(config, pdf)
            all_raw_pages.extend(raw_pages)
            all_raw_cells.extend(raw_cells)
            all_normalized.extend(normalized)
            report_stats.append(
                {
                    "year": year,
                    "source_file": str(config.path),
                    "pages": len(pdf.pages),
                    "raw_page_rows": len(raw_pages),
                    "raw_table_cell_rows": len(raw_cells),
                    "normalized_rows": len(normalized),
                }
            )

    add_computed_global_all_totals(all_normalized, args.years)
    comparability = build_comparability(all_normalized)

    counts = {
        "raw_pages_jsonl": write_jsonl(args.output_dir / "isaps_raw_page_text_2020_2024.jsonl", all_raw_pages),
        "raw_pages_csv": write_csv(args.output_dir / "isaps_raw_page_text_2020_2024.csv", RAW_PAGE_FIELDS, all_raw_pages),
        "raw_table_cells": write_csv(args.output_dir / "isaps_raw_table_cells_2020_2024.csv", RAW_TABLE_CELL_FIELDS, all_raw_cells),
        "normalized_long": write_csv(args.output_dir / "isaps_normalized_long_2020_2024.csv", NORMALIZED_FIELDS, all_normalized),
        "comparability": write_csv(args.output_dir / "isaps_series_comparability_2020_2024.csv", COMPARABILITY_FIELDS, comparability),
    }

    summary: dict[str, Any] = {
        "status": "ok",
        "captured_at": now_iso(),
        "output_dir": str(args.output_dir),
        "years": args.years,
        "report_stats": report_stats,
        "counts": counts,
        "metric_family_counts": {},
        "comparability_counts": {},
    }
    for row in all_normalized:
        family = str(row.get("metric_family") or "")
        summary["metric_family_counts"][family] = summary["metric_family_counts"].get(family, 0) + 1
    for row in comparability:
        klass = str(row.get("comparability_class") or "")
        summary["comparability_counts"][klass] = summary["comparability_counts"].get(klass, 0) + 1

    (args.output_dir / "isaps_extraction_manifest_2020_2024.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
