#!/usr/bin/env python3
"""Convert the local ISAPS 2024 survey PDF into dashboard market metrics."""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_DIR / "data"
DEFAULT_REPORT_PATH = Path(r"E:\shared\行业报告\2024 isaps-global-survey.pdf")
OUTPUT_PATH = DATA_DIR / "isaps_market_metrics.csv"

REPORT_TITLE = "2024 ISAPS International Survey on Aesthetic/Cosmetic Procedures Performed in 2024"
SOURCE_ORG = "ISAPS"
YEAR = 2024

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


GLOBAL_ROWS = [
    ("procedure_volume", "All procedures", "Total surgical and non-surgical", "", "Global", 37_951_364, "procedures", "ISAPS page 12 total procedures."),
    ("procedure_volume", "Surgical procedures", "Total surgical procedures", "", "Global", 17_415_678, "procedures", "ISAPS page 7 global surgical total."),
    ("procedure_volume", "Non-surgical procedures", "Total non-surgical procedures", "", "Global", 20_535_686, "procedures", "ISAPS page 10/page 12 global non-surgical total."),
    ("procedure_volume", "Injectables", "Total injectable procedures", "", "Global", 15_286_878, "procedures", "ISAPS page 12 injectable procedure group."),
    ("procedure_volume", "Facial rejuvenation", "Total facial rejuvenation procedures", "", "Global", 2_812_249, "procedures", "ISAPS page 12 non-surgical facial rejuvenation group."),
    ("procedure_volume", "Other non-surgical", "Total other procedures", "", "Global", 2_436_560, "procedures", "ISAPS page 12 other non-surgical group."),
    ("procedure_volume", "Injectables", "Botulinum Toxin", "", "Global", 7_887_955, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Hyaluronic Acid", "", "Global", 6_338_184, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Hair Removal", "", "Global", 1_487_130, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Non-Surgical Skin Tightening", "", "Global", 1_239_306, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Chemical Peel", "", "Global", 820_225, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Full Field Ablative", "", "Global", 752_717, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Non-Surgical Fat Reduction", "", "Global", 702_836, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Poly-L-Lactic Acid", "", "Global", 642_566, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Calcium Hydroxylapatite", "", "Global", 418_173, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Tattoo Removal", "", "Global", 246_594, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
]


COUNTRY_PROCEDURE_LABELS = [
    ("Botulinum Toxin", "Injectables"),
    ("Calcium Hydroxyapatite", "Injectables"),
    ("Hyaluronic Acid", "Injectables"),
    ("Poly-L-Lactic Acid", "Injectables"),
    ("Chemical Peel", "Facial rejuvenation"),
    ("Full Field Ablative", "Facial rejuvenation"),
    ("Non-Surgical Skin Tightening", "Facial rejuvenation"),
    ("Hair Removal", "Other non-surgical"),
    ("Non-Surgical Fat Reduction", "Other non-surgical"),
    ("Tattoo Removal", "Other non-surgical"),
]


SURGEON_ROWS = [
    ("US", 7752),
    ("Brazil", 6497),
    ("China", 5000),
    ("Japan", 4000),
    ("South Korea", 2808),
    ("India", 2800),
    ("Italy", 2188),
    ("Russia", 2000),
    ("Mexico", 1991),
    ("Germany", 1762),
    ("France", 1400),
    ("Turkiye", 1200),
    ("Colombia", 960),
    ("Spain", 951),
    ("Argentina", 912),
    ("Chinese Taipei", 833),
    ("UK", 729),
    ("Venezuela", 725),
    ("UAE", 640),
    ("Vietnam", 600),
    ("Egypt", 580),
    ("Peru", 575),
    ("Australia", 525),
    ("Thailand", 475),
    ("Iran", 470),
    ("Canada", 450),
    ("Netherlands", 431),
    ("Greece", 400),
    ("Romania", 400),
    ("Ukraine", 350),
]


COUNTRY_NAME_MAP = {
    "US": "United States",
    "BRAZIL": "Brazil",
    "JAPAN": "Japan",
    "ITALY": "Italy",
    "GERMANY": "Germany",
    "MEXICO": "Mexico",
    "INDIA": "India",
    "TURKIYE": "Turkiye",
    "FRANCE": "France",
    "CHINESE TAIPEI": "Chinese Taipei",
    "SPAIN": "Spain",
    "GREECE": "Greece",
    "COLOMBIA": "Colombia",
    "UAE": "UAE",
    "ARGENTINA": "Argentina",
    "IRAN": "Iran",
    "VIETNAM": "Vietnam",
    "THAILAND": "Thailand",
    "AUSTRALIA": "Australia",
    "SAUDI ARABIA": "Saudi Arabia",
    "UK": "UK",
    "TUNISIA": "Tunisia",
    "MOROCCO": "Morocco",
    "SOUTH AFRICA": "South Africa",
    "CZECHIA": "Czechia",
    "CHILE": "Chile",
    "NORWAY": "Norway",
    "MALAYSIA": "Malaysia",
    "PHILIPPINES": "Philippines",
    "SINGAPORE": "Singapore",
    "PANAMA": "Panama",
}


def now_iso() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")


def clean_num(value: object) -> int | None:
    text = str(value or "")
    if not re.search(r"\d", text):
        return None
    return int(re.sub(r"[^0-9]", "", text))


def clean_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def number_after_label(lines: list[str], label: str) -> int | None:
    pattern = re.compile(re.escape(label) + r"\s+([0-9, ]+)$", re.I)
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            return clean_num(match.group(1))
        if line.lower() == label.lower():
            for next_line in lines[index + 1 : index + 5]:
                value = clean_num(next_line)
                if value is not None:
                    return value
    return None


def country_from_page(lines: list[str]) -> str:
    try:
        pos = lines.index("TOTAL NUMBER OF")
    except ValueError:
        return ""
    candidates = []
    for line in lines[:pos]:
        if line in {"INTERNATIONAL", "SURVEY", "2024"}:
            continue
        if "Please credit" in line:
            continue
        if re.fullmatch(r"\d+", line):
            continue
        candidates.append(line)
    raw = candidates[-1] if candidates else ""
    return COUNTRY_NAME_MAP.get(raw.upper(), raw.title())


def country_total(lines: list[str]) -> int | None:
    try:
        start = lines.index("TOTAL NUMBER OF")
    except ValueError:
        return None
    for line in lines[start : start + 8]:
        value = clean_num(line)
        if value is not None:
            return value
    return None


def metric_row(
    report_path: Path,
    data_type: str,
    category_l1: str,
    category_l2: str,
    category_l3: str,
    geo: str,
    value: int | float,
    unit: str,
    note: str,
) -> dict[str, str]:
    return {
        "source_file": str(report_path),
        "data_type": data_type,
        "category_l1": category_l1,
        "category_l2": category_l2,
        "category_l3": category_l3,
        "geo": geo,
        "value": str(value),
        "unit": unit,
        "year": str(YEAR),
        "source_org": SOURCE_ORG,
        "report_title": REPORT_TITLE,
        "url": "",
        "note": note,
        "confidence": "official_association_report",
    }


def extract_rows(report_path: Path) -> list[dict[str, str]]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("PyMuPDF/fitz is required to read the ISAPS PDF.") from exc

    rows: list[dict[str, str]] = []
    for data_type, cat1, cat2, cat3, geo, value, unit, note in GLOBAL_ROWS:
        rows.append(metric_row(report_path, data_type, cat1, cat2, cat3, geo, value, unit, note))

    with fitz.open(report_path) as doc:
        for page_index in range(14, min(45, doc.page_count)):
            lines = clean_lines(doc[page_index].get_text("text"))
            country = country_from_page(lines)
            if not country:
                continue
            page_note = f"ISAPS page {page_index + 1} country procedure table."
            totals = [
                ("procedure_volume", "All procedures", "Country total procedures", country_total(lines)),
                ("procedure_volume", "Surgical procedures", "Country surgical procedures", number_after_label(lines, "TOTAL SURGICAL PROCEDURES")),
                ("procedure_volume", "Non-surgical procedures", "Country non-surgical procedures", number_after_label(lines, "TOTAL NON-SURGICAL PROCEDURES")),
                ("procedure_volume", "Injectables", "Country total injectables", number_after_label(lines, "TOTAL INJECTABLES")),
                ("procedure_volume", "Facial rejuvenation", "Country total facial rejuvenation", number_after_label(lines, "TOTAL FACIAL REJUVENATION")),
                ("procedure_volume", "Other non-surgical", "Country total other non-surgical", number_after_label(lines, "TOTAL OTHER")),
            ]
            for data_type, cat1, cat2, value in totals:
                if value is not None:
                    rows.append(metric_row(report_path, data_type, cat1, cat2, "", country, value, "procedures", page_note))

            for label, group in COUNTRY_PROCEDURE_LABELS:
                value = number_after_label(lines, label)
                if value is not None:
                    canonical = "Calcium Hydroxylapatite" if label == "Calcium Hydroxyapatite" else label
                    rows.append(metric_row(report_path, "procedure_volume", group, canonical, "", country, value, "procedures", page_note))

    for country, value in SURGEON_ROWS:
        rows.append(
            metric_row(
                report_path,
                "estimated_plastic_surgeons",
                "Workforce",
                "Estimated plastic surgeons",
                "",
                country,
                value,
                "surgeons",
                "ISAPS page 60 ranked estimated number of plastic surgeons.",
            )
        )

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

    parser = argparse.ArgumentParser(description="Extract ISAPS 2024 survey metrics into a dashboard CSV.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH)
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    if not args.report.exists():
        raise SystemExit(json.dumps({"status": "missing_report", "report": str(args.report)}, ensure_ascii=False))

    rows = extract_rows(args.report)
    write_rows(rows, args.output)
    countries = sorted({row["geo"] for row in rows if row["geo"] not in {"Global"}})
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "rows": len(rows),
                "countries": len(countries),
                "source": str(args.report),
                "captured_at": now_iso(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
