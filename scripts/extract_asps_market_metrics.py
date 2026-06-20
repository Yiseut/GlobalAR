#!/usr/bin/env python3
"""Extract ASPS official statistics PDFs into market metrics CSV.

The extractor keeps ASPS as a source-labeled US lane beside ISAPS. It covers:
- national procedure volume for 2020, 2022, 2023, 2024
- 2024 regional procedure volume and regional share
- 2024 average surgeon/physician fee ranges as midpoint rows
"""

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
RAW_DIR = PROJECT_DIR / "data" / "commercial_sources" / "phase1_official_stats" / "asps_plastic_surgery_statistics"
INVENTORY_PATH = PROJECT_DIR / "data" / "audits" / "commercial_phase1_official_source_inventory_latest.csv"
OUTPUT_PATH = PROJECT_DIR / "data" / "asps_market_metrics.csv"
STATUS_PATH = PROJECT_DIR / "data" / "audits" / "asps_official_stats_extraction_status_latest.csv"

FIELDS = [
    "source_file",
    "data_type",
    "category_l1",
    "category_l2",
    "category_l3",
    "geo",
    "value",
    "unit",
    "year",
    "source_org",
    "report_title",
    "url",
    "note",
    "confidence",
]

STATUS_FIELDS = [
    "source_file",
    "source_url",
    "extraction_scope",
    "years_extracted",
    "rows_extracted",
    "data_types",
    "status",
    "note",
    "captured_at",
]

TOPIC_CATEGORY = {
    "cosmetic_procedure": "Cosmetic surgery procedures",
    "minimally_invasive": "Cosmetic minimally invasive procedures",
    "reconstructive_procedure": "Reconstructive procedures",
}

DEFAULT_SECTION = {
    "cosmetic_procedure": "Cosmetic surgical procedures",
    "minimally_invasive": "Cosmetic minimally invasive procedures",
    "reconstructive_procedure": "Reconstructive procedures",
}

REGION_DEFINITIONS = {
    "Region 1": "New England; Middle Atlantic",
    "Region 2": "East North Central; West North Central",
    "Region 3": "South Atlantic",
    "Region 4": "East South Central; West South Central",
    "Region 5": "Mountain; Pacific",
}

NATIONAL_SPECS = [
    {
        "file": "2024__cosmetic_procedure__2024-cosmetic-surgery-procedure-trends.pdf",
        "topic": "cosmetic_procedure",
        "years": ["2024"],
        "pages": None,
        "title": "2024 ASPS cosmetic surgery procedure trends",
    },
    {
        "file": "2024__minimally_invasive__2024-minimally-invasive-procedure-trends.pdf",
        "topic": "minimally_invasive",
        "years": ["2024"],
        "pages": None,
        "title": "2024 ASPS minimally invasive procedure trends",
    },
    {
        "file": "2024__reconstructive_procedure__2024-reconstructive-procedure-trends.pdf",
        "topic": "reconstructive_procedure",
        "years": ["2024"],
        "pages": None,
        "title": "2024 ASPS reconstructive procedure trends",
    },
    {
        "file": "2022-2023__cosmetic_procedure__2022-2023-national-cosmetic-procedures.pdf",
        "topic": "cosmetic_procedure",
        "years": ["2023", "2022"],
        "pages": None,
        "title": "2023 ASPS cosmetic surgery procedures with 2022 comparator",
    },
    {
        "file": "2022-2023__minimally_invasive__2022-2023-national-minimally-invasive-procedures.pdf",
        "topic": "minimally_invasive",
        "years": ["2023", "2022"],
        "pages": None,
        "title": "2023 ASPS minimally invasive procedures with 2022 comparator",
    },
    {
        "file": "2022-2023__reconstructive_procedure__2022-2023-national-reconstructive-procedures.pdf",
        "topic": "reconstructive_procedure",
        "years": ["2023", "2022"],
        "pages": None,
        "title": "2023 ASPS reconstructive procedures with 2022 comparator",
    },
]

LEGACY_2020_SPECS = [
    {
        "file": "2020__procedure_statistics__2020-plastic-surgery-statistics-report.pdf",
        "topic": "cosmetic_procedure",
        "years": ["2020"],
        "pages": [6],
        "title": "2020 ASPS cosmetic procedure trends",
    },
    {
        "file": "2020__procedure_statistics__2020-plastic-surgery-statistics-report.pdf",
        "topic": "minimally_invasive",
        "years": ["2020"],
        "pages": [7],
        "title": "2020 ASPS minimally invasive procedure trends",
    },
    {
        "file": "2020__procedure_statistics__2020-plastic-surgery-statistics-report.pdf",
        "topic": "reconstructive_procedure",
        "years": ["2020"],
        "pages": [9],
        "title": "2020 ASPS reconstructive procedure trends",
    },
]


def norm(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def normalize_key(value: Any) -> str:
    return norm(value).replace("\\", "/").lower()


def clean_num(value: Any) -> int | None:
    text = norm(value).replace("$", "").replace(",", "")
    if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", text):
        return None
    return int(float(text))


def clean_float(value: Any) -> float | None:
    text = norm(value).replace("$", "").replace(",", "").replace("%", "")
    if not re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?", text):
        return None
    return float(text)


def clean_percent(value: Any) -> float | None:
    text = norm(value)
    if not text.endswith("%"):
        return None
    return clean_float(text)


def clean_procedure(value: Any) -> str:
    text = norm(value).replace("\n", " ")
    text = re.sub(r"[\*\u2020\u2021\u25ca\u25e6\u00b0\^]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip(" ;")


def section_from_header(value: Any, fallback: str) -> str:
    text = clean_procedure(value)
    if " - " in text:
        return norm(text.rsplit(" - ", 1)[-1]).title()
    if " - " not in text and "-" in text:
        return norm(text.rsplit("-", 1)[-1]).title()
    return fallback


def is_section_row(cells: list[str]) -> bool:
    first = norm(cells[0]).upper()
    if not first:
        return False
    if first.startswith("TOTAL"):
        return False
    has_numeric = any(clean_num(cell) is not None or clean_percent(cell) is not None for cell in cells[1:])
    return not has_numeric and ("PROCEDURES" in first or "COSMETIC" in first or "RECONSTRUCTIVE" in first)


def parse_fee_range(value: Any) -> tuple[float | None, str]:
    text = norm(value)
    numbers = [float(part.replace(",", "")) for part in re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?", text)]
    if not numbers:
        return None, text
    if len(numbers) == 1:
        return numbers[0], text
    return round((numbers[0] + numbers[1]) / 2, 2), text


def local_path_key(path: Path | str) -> str:
    return normalize_key(str(path))


def load_inventory_urls() -> dict[str, str]:
    if not INVENTORY_PATH.exists():
        return {}
    lookup: dict[str, str] = {}
    with INVENTORY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            local_path = norm(row.get("local_path"))
            url = norm(row.get("canonical_url") or row.get("url"))
            if local_path and url:
                lookup[local_path_key(local_path)] = url
    return lookup


def source_url_for(path: Path, url_lookup: dict[str, str]) -> str:
    rel_path = path.relative_to(PROJECT_DIR)
    return url_lookup.get(local_path_key(rel_path), "")


def row_template(
    path: Path,
    url_lookup: dict[str, str],
    data_type: str,
    category_l1: str,
    category_l2: str,
    category_l3: str,
    geo: str,
    value: Any,
    unit: str,
    year: str,
    report_title: str,
    note: str,
) -> dict[str, str]:
    return {
        "source_file": str(path.relative_to(PROJECT_DIR)),
        "data_type": data_type,
        "category_l1": category_l1,
        "category_l2": category_l2,
        "category_l3": category_l3,
        "geo": geo,
        "value": str(value),
        "unit": unit,
        "year": year,
        "source_org": "ASPS",
        "report_title": report_title,
        "url": source_url_for(path, url_lookup),
        "note": note,
        "confidence": "official_association_report_auto_extracted",
    }


def iter_tables(path: Path, pages: list[int] | None = None) -> list[list[list[Any]]]:
    tables: list[list[list[Any]]] = []
    with pdfplumber.open(path) as pdf:
        selected_pages = [pdf.pages[index] for index in pages] if pages is not None else pdf.pages
        for page in selected_pages:
            tables.extend(page.extract_tables() or [])
    return tables


def extract_national_spec(spec: dict[str, Any], years_filter: set[str], url_lookup: dict[str, str]) -> list[dict[str, str]]:
    path = RAW_DIR / spec["file"]
    if not path.exists():
        return []
    years = [year for year in spec["years"] if year in years_filter]
    if not years:
        return []
    topic = spec["topic"]
    category_l1 = TOPIC_CATEGORY[topic]
    section = DEFAULT_SECTION[topic]
    rows: list[dict[str, str]] = []

    for table in iter_tables(path, spec.get("pages")):
        section = DEFAULT_SECTION[topic]
        for raw_row in table:
            cells = [norm(cell) for cell in raw_row]
            if not cells or not cells[0]:
                continue
            if is_section_row(cells):
                section = section_from_header(cells[0], DEFAULT_SECTION[topic])
                continue
            procedure = clean_procedure(cells[0])
            if not procedure or procedure.lower().startswith(("all procedures include", "counts of procedures")):
                continue
            is_total = procedure.upper().startswith("TOTAL")
            for offset, year in enumerate(spec["years"], start=1):
                if year not in years:
                    continue
                if offset >= len(cells):
                    continue
                value = clean_num(cells[offset])
                if value is None:
                    continue
                rows.append(
                    row_template(
                        path=path,
                        url_lookup=url_lookup,
                        data_type="procedure_volume",
                        category_l1=category_l1,
                        category_l2="Total" if is_total else section,
                        category_l3="" if is_total else procedure,
                        geo="United States",
                        value=value,
                        unit="procedures",
                        year=year,
                        report_title=spec["title"],
                        note=f"ASPS official national table extracted from {path.name}; comparator columns remain source-labeled and are not merged with ISAPS.",
                    )
                )
    return rows


def extract_2024_fees(years_filter: set[str], url_lookup: dict[str, str]) -> list[dict[str, str]]:
    if "2024" not in years_filter:
        return []
    path = RAW_DIR / "2024__complete_report__2024-complete-plastic-surgery-statistics-report.pdf"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    section = "Cosmetic surgical procedures"
    for table in iter_tables(path, [27]):
        for raw_row in table:
            cells = [norm(cell) for cell in raw_row]
            if not cells or not cells[0]:
                continue
            if is_section_row(cells):
                section = section_from_header(cells[0], "Cosmetic surgical procedures")
                continue
            procedure = clean_procedure(cells[0])
            midpoint, range_text = parse_fee_range(cells[1] if len(cells) > 1 else "")
            if midpoint is None:
                continue
            rows.append(
                row_template(
                    path=path,
                    url_lookup=url_lookup,
                    data_type="average_fee_range_midpoint",
                    category_l1="Average surgeon/physician fees",
                    category_l2=section,
                    category_l3=procedure,
                    geo="United States",
                    value=midpoint,
                    unit="USD midpoint of reported range",
                    year="2024",
                    report_title="2024 ASPS average surgeon/physician fees",
                    note=f"ASPS reports a 2024 fee range of {range_text}; value is the midpoint for numeric dashboard use.",
                )
            )
    return rows


def extract_2024_regional_distribution(years_filter: set[str], url_lookup: dict[str, str]) -> list[dict[str, str]]:
    if "2024" not in years_filter:
        return []
    path = RAW_DIR / "2024__regional_distribution__procedures-by-region.pdf"
    if not path.exists():
        return []
    rows: list[dict[str, str]] = []
    section = "Cosmetic surgical procedures"
    report_title = "2024 ASPS cosmetic surgery regional distribution"

    for table in iter_tables(path, [1, 2]):
        region_columns: list[tuple[str, int, int | None]] = []
        for raw_row in table:
            cells = [norm(cell) for cell in raw_row]
            if not cells or not cells[0]:
                continue
            if is_section_row(cells):
                section = section_from_header(cells[0], "Cosmetic surgical procedures")
                for index, cell in enumerate(cells[1:], start=1):
                    match = re.search(r"Region\s+([1-5])", cell, re.I)
                    if match:
                        region = f"Region {match.group(1)}"
                        share_index = index + 1 if index + 1 < len(cells) else None
                        region_columns.append((region, index, share_index))
                continue
            procedure = clean_procedure(cells[0])
            if not procedure:
                continue
            is_total = procedure.upper().startswith("TOTAL")
            for region, count_index, share_index in region_columns:
                if count_index >= len(cells):
                    continue
                count = clean_num(cells[count_index])
                if count is None:
                    continue
                region_note = REGION_DEFINITIONS.get(region, "")
                category_l2 = "Total" if is_total else section
                category_l3 = "" if is_total else procedure
                rows.append(
                    row_template(
                        path=path,
                        url_lookup=url_lookup,
                        data_type="regional_procedure_volume",
                        category_l1="Cosmetic regional distribution",
                        category_l2=category_l2,
                        category_l3=category_l3,
                        geo=f"United States - ASPS {region}",
                        value=count,
                        unit="procedures",
                        year="2024",
                        report_title=report_title,
                        note=f"{region}: {region_note}. ASPS regional distribution count.",
                    )
                )
                share = clean_percent(cells[share_index]) if share_index is not None and share_index < len(cells) else None
                if share is not None:
                    rows.append(
                        row_template(
                            path=path,
                            url_lookup=url_lookup,
                            data_type="regional_procedure_share",
                            category_l1="Cosmetic regional distribution",
                            category_l2=category_l2,
                            category_l3=category_l3,
                            geo=f"United States - ASPS {region}",
                            value=share,
                            unit="%",
                            year="2024",
                            report_title=report_title,
                            note=f"{region}: {region_note}. Share of ASPS total for this procedure.",
                        )
                    )
    return rows


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def write_status(rows: list[dict[str, str]], status_path: Path) -> None:
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    by_file: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        by_file[row["source_file"]].append(row)
    status_rows = []
    expected_files = {spec["file"] for spec in NATIONAL_SPECS + LEGACY_2020_SPECS}
    expected_files.update(
        {
            "2024__complete_report__2024-complete-plastic-surgery-statistics-report.pdf",
            "2024__regional_distribution__procedures-by-region.pdf",
        }
    )
    for file_name in sorted(expected_files):
        path = RAW_DIR / file_name
        rel_path = str(path.relative_to(PROJECT_DIR))
        file_rows = by_file.get(rel_path, [])
        status_rows.append(
            {
                "source_file": rel_path,
                "source_url": file_rows[0].get("url", "") if file_rows else "",
                "extraction_scope": "ASPS official procedure/fee/regional extraction",
                "years_extracted": ";".join(sorted({row["year"] for row in file_rows})),
                "rows_extracted": len(file_rows),
                "data_types": ";".join(sorted({row["data_type"] for row in file_rows})),
                "status": "extracted" if file_rows else ("missing_source_file" if not path.exists() else "not_selected_or_no_rows"),
                "note": "Loaded into data/asps_market_metrics.csv." if file_rows else "No rows were promoted from this file in the selected year filter.",
                "captured_at": captured_at,
            }
        )
    status_path.parent.mkdir(parents=True, exist_ok=True)
    with status_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=STATUS_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in status_rows:
            writer.writerow({field: row.get(field, "") for field in STATUS_FIELDS})


def main() -> None:
    global RAW_DIR

    import argparse

    parser = argparse.ArgumentParser(description="Extract ASPS official statistics PDFs.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--status-output", type=Path, default=STATUS_PATH)
    parser.add_argument("--years", default="2020,2022,2023,2024", help="Comma-separated years to extract.")
    args = parser.parse_args()

    RAW_DIR = args.input_dir

    years_filter = set(re.findall(r"20\d{2}", args.years))
    url_lookup = load_inventory_urls()
    rows: list[dict[str, str]] = []
    for spec in NATIONAL_SPECS + LEGACY_2020_SPECS:
        rows.extend(extract_national_spec(spec, years_filter, url_lookup))
    rows.extend(extract_2024_fees(years_filter, url_lookup))
    rows.extend(extract_2024_regional_distribution(years_filter, url_lookup))

    rows.sort(
        key=lambda item: (
            item["year"],
            item["data_type"],
            item["category_l1"],
            item["category_l2"],
            item["category_l3"],
            item["geo"],
        )
    )
    write_rows(rows, args.output)
    write_status(rows, args.status_output)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "status_output": str(args.status_output),
                "rows": len(rows),
                "years": sorted({row["year"] for row in rows}),
                "data_type_counts": dict(Counter(row["data_type"] for row in rows)),
                "category_counts": dict(Counter(row["category_l1"] for row in rows)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
