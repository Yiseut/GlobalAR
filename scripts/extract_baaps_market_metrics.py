#!/usr/bin/env python3
"""Extract BAAPS annual audit PDFs into a source-labeled UK market metrics lane."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import pdfplumber


PROJECT_DIR = Path(__file__).resolve().parents[1]
BAAPS_DIR = PROJECT_DIR / "data" / "commercial_sources" / "geo_market_sources" / "uk_baaps_annual_audit"
DISCOVERY_PATH = PROJECT_DIR / "data" / "audits" / "commercial_geo_market_source_discovery_latest.csv"
OUTPUT_PATH = PROJECT_DIR / "data" / "baaps_market_metrics.csv"

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

TEXT_CURRENT_YEAR_REPORTS = {
    2020: "2020__pdf__2020-results-of-baaps-audit__30e5ef95.pdf",
    2021: "2021__pdf__2021-results-of-baaps-audit__1df86af2.pdf",
    2023: "2023__pdf__2023-results-of-baaps-audit__e81ecc67.pdf",
}

TABLE_CURRENT_YEAR_REPORTS = {
    2024: "2024__pdf__2024-results-of-baaps-audit__fb12d754.pdf",
    2025: "2025__pdf__2025-results-of-baaps-audit__ead5de1c.pdf",
}

NON_SURGICAL_REPORTS = {
    2022: "2023__pdf__2023-results-of-baaps-audit__e81ecc67.pdf",
    2023: "2023__pdf__2023-results-of-baaps-audit__e81ecc67.pdf",
    2024: "2024__pdf__2024-results-of-baaps-audit__fb12d754.pdf",
    2025: "2025__pdf__2025-results-of-baaps-audit__ead5de1c.pdf",
}

PROCEDURE_NORMALIZATIONS = {
    "breast augmentation": "Breast Augmentation",
    "breast augmentation.": "Breast Augmentation",
    "breast reduction": "Breast Reduction",
    "blepharoplasty (eyelid surgery)": "Blepharoplasty",
    "blepharoplasty": "Blepharoplasty",
    "abdominoplasty": "Abdominoplasty",
    "rhinoplasty": "Rhinoplasty",
    "liposuction": "Liposuction",
    "face/neck lift": "Face/Neck Lift",
    "face lift": "Face/Neck Lift",
    "fat transfer": "Fat Transfer",
    "otoplasty (ear correction)": "Otoplasty",
    "otoplasty": "Otoplasty",
    "breast implant removal": "Breast Implant Removal",
    "breast implants removal": "Breast Implant Removal",
    "browlift": "Brow Lift",
    "brow lifts": "Brow Lift",
    "brow lift": "Brow Lift",
    "brachioplasty": "Brachioplasty",
    "thigh lift": "Thigh Lift",
    "lower body lift": "Lower Body Lift",
    "labiaplasty": "Labiaplasty",
    "superficial gluteal lipofilling": "Superficial Gluteal Lipofilling",
    "supf gluteal lipofilling": "Superficial Gluteal Lipofilling",
    "botox injections": "Botox Injections",
    "filler injections": "Filler Injections",
    "total": "Total",
    "total non-surgical procedures": "Total Non-Surgical Procedures",
}

NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?")


def norm(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def clean_num(value: Any) -> int | None:
    text = norm(value).replace(",", "")
    if not re.fullmatch(r"-?\d+(?:\.\d+)?", text):
        return None
    return int(float(text))


def clean_label(value: Any) -> str:
    text = norm(value).replace("\n", " ").strip(" .")
    text = re.sub(r"^[\u2022\uf0b7\-\*\s]+", "", text)
    text = re.sub(r"\s+", " ", text)
    return PROCEDURE_NORMALIZATIONS.get(text.lower(), text)


def discovery_urls() -> dict[str, str]:
    lookup: dict[str, str] = {}
    if not DISCOVERY_PATH.exists():
        return lookup
    with DISCOVERY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            local_path = norm(row.get("local_path")).replace("\\", "/").lower()
            url = norm(row.get("discovered_url") or row.get("source_url"))
            if row.get("source_id") == "uk_baaps_annual_audit" and local_path and url:
                lookup[local_path] = url
    return lookup


def source_url(path: Path, url_lookup: dict[str, str]) -> str:
    rel = str(path.relative_to(PROJECT_DIR)).replace("\\", "/").lower()
    return url_lookup.get(rel, "https://baaps.org.uk/baaps_annual_audit_results_.aspx")


def report_title(year: int) -> str:
    return f"{year} BAAPS Annual Audit Results"


def metric_row(
    path: Path,
    url_lookup: dict[str, str],
    year: int,
    category_l1: str,
    category_l2: str,
    value: int,
    note: str,
    confidence: str,
) -> dict[str, str]:
    return {
        "source_file": str(path.relative_to(PROJECT_DIR)),
        "data_type": "procedure_volume",
        "category_l1": category_l1,
        "category_l2": category_l2,
        "category_l3": "",
        "geo": "United Kingdom",
        "value": str(value),
        "unit": "procedures",
        "year": str(year),
        "source_org": "BAAPS",
        "report_title": report_title(year),
        "url": source_url(path, url_lookup),
        "note": note,
        "confidence": confidence,
    }


def extract_current_year_surgical_text(path: Path, year: int, url_lookup: dict[str, str]) -> list[dict[str, str]]:
    with pdfplumber.open(path) as pdf:
        page_texts = [page.extract_text(x_tolerance=1, y_tolerance=3) or "" for page in pdf.pages]

    current_text = ""
    header_re = re.compile(rf"men\s*&\s*women\s+in\s+{year}\s+\(total\s+([\d,]+)", re.I)
    total = None
    for text in page_texts:
        match = header_re.search(text)
        if match:
            current_text = text
            total = clean_num(match.group(1))
            break
    if not current_text or total is None:
        raise ValueError(f"Could not find BAAPS surgical total for {year} in {path.name}")

    rows = [
        metric_row(
            path,
            url_lookup,
            year,
            "Surgical procedures",
            "Total surgical procedures",
            total,
            "BAAPS annual audit current-year total surgical procedures. Source-labeled UK association lane; do not merge silently with ISAPS totals.",
            "official_association_report_text_qa_surgical_only",
        )
    ]
    for raw_line in current_text.splitlines():
        line = norm(raw_line)
        if not line or not re.match(r"^[\u2022\uf0b7]", line):
            continue
        core = re.sub(r"^[\u2022\uf0b7]\s*", "", line)
        match = re.match(r"(?P<label>.+?)(?::\s*|\s+)(?P<value>\d[\d,]*)\s+[–-]\s+", core)
        if not match:
            continue
        label = clean_label(match.group("label"))
        value = clean_num(match.group("value"))
        if value is None:
            continue
        rows.append(
            metric_row(
                path,
                url_lookup,
                year,
                "Surgical procedures",
                label,
                value,
                "BAAPS annual audit current-year surgical procedure count. Source-labeled UK association lane.",
                "official_association_report_text_qa_surgical_only",
            )
        )
    return rows


def extract_current_year_surgical_table(path: Path, year: int, url_lookup: dict[str, str]) -> list[dict[str, str]]:
    with pdfplumber.open(path) as pdf:
        tables = pdf.pages[0].extract_tables() or []
    if not tables:
        raise ValueError(f"No surgical table found in {path.name}")
    table = tables[0]
    header = [norm(cell) for cell in table[0]]
    try:
        value_col = next(index for index, cell in enumerate(header) if f"{year} TOTAL" in cell.upper())
    except StopIteration as exc:
        raise ValueError(f"No {year} TOTAL column found in {path.name}") from exc

    rows: list[dict[str, str]] = []
    total_value: int | None = None
    procedure_rows: list[dict[str, str]] = []
    for cells in table[1:]:
        label = clean_label(cells[0])
        value = clean_num(cells[value_col] if value_col < len(cells) else "")
        if not label or value is None:
            continue
        if label == "Total":
            total_value = value
            continue
        procedure_rows.append(
            metric_row(
                path,
                url_lookup,
                year,
                "Surgical procedures",
                label,
                value,
                "BAAPS annual audit current-year surgical procedure count from table. Source-labeled UK association lane.",
                "official_association_report_table_qa_surgical_only",
            )
        )
    if total_value is not None:
        rows.append(
            metric_row(
                path,
                url_lookup,
                year,
                "Surgical procedures",
                "Total surgical procedures",
                total_value,
                "BAAPS annual audit current-year total surgical procedures from table. Source-labeled UK association lane; do not merge silently with ISAPS totals.",
                "official_association_report_table_qa_surgical_only",
            )
        )
    rows.extend(procedure_rows)
    return rows


def extract_non_surgical(path: Path, years: set[int], url_lookup: dict[str, str]) -> list[dict[str, str]]:
    with pdfplumber.open(path) as pdf:
        tables = pdf.pages[0 if "2023__" in path.name else 1].extract_tables() or []
    if not tables:
        return []
    table = tables[0]
    header = [norm(cell) for cell in table[0]]
    rows: list[dict[str, str]] = []
    for year in years:
        try:
            value_col = next(index for index, cell in enumerate(header) if f"{year} Total".lower() == cell.replace("\n", " ").lower())
        except StopIteration:
            continue
        for cells in table[1:]:
            label = clean_label(cells[0])
            value = clean_num(cells[value_col] if value_col < len(cells) else "")
            if not label or value is None:
                continue
            rows.append(
                metric_row(
                    path,
                    url_lookup,
                    year,
                    "Non-surgical procedures",
                    label,
                    value,
                    "BAAPS annual audit non-surgical procedure count. Source-labeled UK association lane.",
                    "official_association_report_table_qa_non_surgical",
                )
            )
    return rows


def dedupe(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    by_key: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for row in rows:
        key = (row["year"], row["category_l1"], row["category_l2"], row["data_type"])
        by_key[key] = row
    return sorted(by_key.values(), key=lambda row: (row["year"], row["category_l1"], row["category_l2"]))


def extract_all() -> list[dict[str, str]]:
    url_lookup = discovery_urls()
    rows: list[dict[str, str]] = []
    for year, filename in TEXT_CURRENT_YEAR_REPORTS.items():
        rows.extend(extract_current_year_surgical_text(BAAPS_DIR / filename, year, url_lookup))
    for year, filename in TABLE_CURRENT_YEAR_REPORTS.items():
        rows.extend(extract_current_year_surgical_table(BAAPS_DIR / filename, year, url_lookup))

    non_surgical_years_by_file: dict[str, set[int]] = {}
    for year, filename in NON_SURGICAL_REPORTS.items():
        non_surgical_years_by_file.setdefault(filename, set()).add(year)
    for filename, years in non_surgical_years_by_file.items():
        rows.extend(extract_non_surgical(BAAPS_DIR / filename, years, url_lookup))
    return dedupe(rows)


def main() -> int:
    rows = extract_all()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUTPUT_PATH} · {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
