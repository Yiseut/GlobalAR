#!/usr/bin/env python3
"""Extract ASPS procedure-volume trend PDFs into market metrics CSV."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "commercial_sources" / "phase1_official_stats" / "asps_plastic_surgery_statistics"
INVENTORY_PATH = PROJECT_DIR / "data" / "audits" / "commercial_phase1_official_source_inventory_latest.csv"
OUTPUT_PATH = PROJECT_DIR / "data" / "asps_market_metrics.csv"

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

TOPIC_CATEGORY = {
    "cosmetic_procedure": "Cosmetic surgery procedures",
    "minimally_invasive": "Minimally invasive procedures",
    "reconstructive_procedure": "Reconstructive procedures",
}


def norm(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def clean_num(value: str) -> int | None:
    text = norm(value)
    if not re.fullmatch(r"-?[0-9][0-9,]*(?:\.\d+)?", text):
        return None
    return int(float(text.replace(",", "")))


def is_number(value: str) -> bool:
    return clean_num(value) is not None


def is_percent(value: str) -> bool:
    return bool(re.fullmatch(r"-?[0-9]+(?:\.[0-9]+)?%", norm(value)))


def clean_procedure(value: str) -> str:
    text = norm(value)
    text = text.replace("**", "").replace("*", "").replace("‡", "")
    return norm(text)


def title_from_pdf(path: Path) -> str:
    doc = fitz.open(path)
    try:
        lines = [norm(line) for line in doc[0].get_text("text").splitlines() if norm(line)]
    finally:
        doc.close()
    for line in lines[:8]:
        if "Procedural Statistics" in line or "Procedures" in line:
            return line
    return path.stem


def local_path_key(path: Path) -> str:
    return path.as_posix().lower()


def load_inventory_urls() -> dict[str, str]:
    if not INVENTORY_PATH.exists():
        return {}
    lookup: dict[str, str] = {}
    with INVENTORY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            local_path = norm(row.get("local_path"))
            if local_path:
                lookup[local_path_key(Path(local_path))] = norm(row.get("canonical_url") or row.get("url"))
    return lookup


def topic_from_file(path: Path) -> str:
    name = path.name.lower()
    for topic in TOPIC_CATEGORY:
        if f"__{topic}__" in name:
            return topic
    return ""


def year_from_file(path: Path) -> str:
    match = re.match(r"(20\d{2})__", path.name)
    return match.group(1) if match else ""


def section_from_header(line: str, fallback: str) -> str:
    text = norm(line)
    if " - " in text:
        return norm(text.rsplit(" - ", 1)[-1]).title()
    return fallback


def table_lines(path: Path) -> list[str]:
    doc = fitz.open(path)
    try:
        text = "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    return [norm(line) for line in text.splitlines() if norm(line)]


def first_table_index(lines: list[str]) -> int:
    for index, line in enumerate(lines):
        if re.fullmatch(r"20\d{2}\s+vs\s+20\d{2}", line, re.I):
            return index + 1
    for index, line in enumerate(lines):
        upper = line.upper()
        if "PROCEDURES -" in upper or upper in {"TOTAL"}:
            return index
    for index, line in enumerate(lines):
        if re.search(r"\b2024\b|\b2023\b|\b2022\b|\b2020\b", line) and index > 3:
            return index + 1
    return 0


def skip_prior_year_columns(lines: list[str], index: int) -> int:
    pos = index
    if pos < len(lines) and is_number(lines[pos]):
        if pos + 1 < len(lines) and is_percent(lines[pos + 1]):
            return pos + 2
    if pos < len(lines) and is_percent(lines[pos]):
        return pos + 1
    return index


def extract_pdf(path: Path, url_lookup: dict[str, str]) -> list[dict[str, str]]:
    topic = topic_from_file(path)
    year = year_from_file(path)
    if topic not in TOPIC_CATEGORY or not year:
        return []

    category_l1 = TOPIC_CATEGORY[topic]
    title = title_from_pdf(path)
    rel_path = path.relative_to(PROJECT_DIR)
    source_url = url_lookup.get(local_path_key(rel_path), "")
    lines = table_lines(path)
    rows: list[dict[str, str]] = []
    section = category_l1
    buffer: list[str] = []
    index = first_table_index(lines)

    while index < len(lines):
        line = lines[index]
        upper = line.upper()
        if upper.startswith("**") or line.startswith("‡"):
            break
        if "PROCEDURES -" in upper:
            section = section_from_header(line, category_l1)
            buffer = []
            index += 1
            continue
        if upper in {
            "2024",
            "2023",
            "2022",
            "2020",
            "% CHANGE",
            "% CHANGE 2024 VS 2023",
            "% CHANGE 2023 VS 2022",
            "% CHANGE 2022 VS 2019",
            "% CHANGE 2020 VS 2019",
        }:
            index += 1
            continue
        if is_percent(line):
            index += 1
            continue
        if is_number(line):
            value = clean_num(line)
            if value is not None and buffer:
                procedure = clean_procedure(" ".join(buffer))
                is_total = procedure.upper() == "TOTAL"
                rows.append(
                    {
                        "source_file": str(rel_path),
                        "data_type": "procedure_volume",
                        "category_l1": category_l1,
                        "category_l2": "Total" if is_total else section,
                        "category_l3": "" if is_total else procedure,
                        "geo": "United States",
                        "value": str(value),
                        "unit": "procedures",
                        "year": year,
                        "source_org": "ASPS",
                        "report_title": title,
                        "url": source_url,
                        "note": "ASPS current-year value extracted from official trend PDF; prior-year comparator columns are not promoted in this CSV.",
                        "confidence": "official_association_report_auto_extracted",
                    }
                )
            buffer = []
            index = skip_prior_year_columns(lines, index + 1)
            continue
        buffer.append(line)
        index += 1

    return rows


def write_rows(rows: list[dict[str, str]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def main() -> None:
    import argparse
    import json
    from collections import Counter

    parser = argparse.ArgumentParser(description="Extract ASPS procedure trend metrics.")
    parser.add_argument("--input-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--years", default="2024", help="Comma-separated years to extract from trend PDFs.")
    args = parser.parse_args()

    years = {part for part in re.findall(r"20\d{2}", args.years)}
    url_lookup = load_inventory_urls()
    rows: list[dict[str, str]] = []
    for path in sorted(args.input_dir.glob("*.pdf")):
        if "procedure-trends" not in path.name.lower():
            continue
        if year_from_file(path) not in years:
            continue
        if topic_from_file(path) not in TOPIC_CATEGORY:
            continue
        rows.extend(extract_pdf(path, url_lookup))

    rows.sort(key=lambda item: (item["year"], item["category_l1"], item["category_l2"], item["category_l3"]))
    write_rows(rows, args.output)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "rows": len(rows),
                "years": sorted({row["year"] for row in rows}),
                "category_counts": dict(Counter(row["category_l1"] for row in rows)),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
