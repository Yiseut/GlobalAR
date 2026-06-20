#!/usr/bin/env python3
"""Convert local ISAPS survey PDFs into dashboard market metrics."""

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

SOURCE_ORG = "ISAPS"

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

GLOBAL_ROWS_2023 = [
    ("procedure_volume", "All procedures", "Total surgical and non-surgical", "", "Global", 34_995_494, "procedures", "ISAPS page 12 total procedures."),
    ("procedure_volume", "Surgical procedures", "Total surgical procedures", "", "Global", 15_813_353, "procedures", "ISAPS page 9 global surgical total."),
    ("procedure_volume", "Non-surgical procedures", "Total non-surgical procedures", "", "Global", 19_182_141, "procedures", "ISAPS page 10/page 12 global non-surgical total."),
    ("procedure_volume", "Injectables", "Total injectable procedures", "", "Global", 14_787_481, "procedures", "ISAPS page 12 injectable procedure group."),
    ("procedure_volume", "Facial rejuvenation", "Total facial rejuvenation procedures", "", "Global", 1_823_020, "procedures", "ISAPS page 12 non-surgical facial rejuvenation group."),
    ("procedure_volume", "Other non-surgical", "Total other procedures", "", "Global", 2_571_640, "procedures", "ISAPS page 12 other non-surgical group."),
    ("procedure_volume", "Injectables", "Botulinum Toxin", "", "Global", 8_877_991, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Hyaluronic Acid", "", "Global", 5_564_866, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Hair Removal", "", "Global", 1_608_447, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Non-Surgical Skin Tightening", "", "Global", 831_583, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Non-Surgical Fat Reduction", "", "Global", 631_212, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Chemical Peel", "", "Global", 553_785, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Full Field Ablative", "", "Global", 437_652, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Calcium Hydroxylapatite", "", "Global", 344_624, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Cellulite Treatment", "", "Global", 331_981, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
]

GLOBAL_ROWS_2022 = [
    ("procedure_volume", "All procedures", "Total surgical and non-surgical", "", "Global", 33_844_293, "procedures", "ISAPS page 12 total procedures."),
    ("procedure_volume", "Surgical procedures", "Total surgical procedures", "", "Global", 14_986_982, "procedures", "ISAPS page 9 global surgical total."),
    ("procedure_volume", "Non-surgical procedures", "Total non-surgical procedures", "", "Global", 18_857_311, "procedures", "ISAPS page 10/page 12 global non-surgical total."),
    ("procedure_volume", "Injectables", "Total injectable procedures", "", "Global", 13_884_172, "procedures", "ISAPS page 12 injectable procedure group."),
    ("procedure_volume", "Facial rejuvenation", "Total facial rejuvenation procedures", "", "Global", 1_946_855, "procedures", "ISAPS page 12 non-surgical facial rejuvenation group."),
    ("procedure_volume", "Other non-surgical", "Total other procedures", "", "Global", 3_026_284, "procedures", "ISAPS page 12 other non-surgical group."),
    ("procedure_volume", "Injectables", "Botulinum Toxin", "", "Global", 9_221_419, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Hyaluronic Acid", "", "Global", 4_312_037, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Hair Removal", "", "Global", 1_798_253, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Chemical Peel", "", "Global", 844_616, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Non-Surgical Fat Reduction", "", "Global", 778_716, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Non-Surgical Skin Tightening", "", "Global", 734_257, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Cellulite Treatment", "", "Global", 449_314, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Full Field Ablative", "", "Global", 367_983, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Calcium Hydroxylapatite", "", "Global", 350_716, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
]

GLOBAL_ROWS_2021 = [
    ("procedure_volume", "All procedures", "Total surgical and non-surgical", "", "Global", 30_439_576, "procedures", "ISAPS page 12 total procedures."),
    ("procedure_volume", "Surgical procedures", "Total surgical procedures", "", "Global", 12_840_688, "procedures", "ISAPS page 9 global surgical total."),
    ("procedure_volume", "Non-surgical procedures", "Total non-surgical procedures", "", "Global", 17_598_888, "procedures", "ISAPS page 10/page 12 global non-surgical total."),
    ("procedure_volume", "Injectables", "Total injectable procedures", "", "Global", 12_882_055, "procedures", "ISAPS page 12 injectable procedure group."),
    ("procedure_volume", "Facial rejuvenation", "Total facial rejuvenation procedures", "", "Global", 1_770_517, "procedures", "ISAPS page 12 non-surgical facial rejuvenation group."),
    ("procedure_volume", "Other non-surgical", "Total other procedures", "", "Global", 2_946_316, "procedures", "ISAPS page 12 other non-surgical group."),
    ("procedure_volume", "Injectables", "Botulinum Toxin", "", "Global", 7_312_616, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Hyaluronic Acid", "", "Global", 5_279_344, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Hair Removal", "", "Global", 1_836_111, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Non-Surgical Skin Tightening", "", "Global", 1_003_731, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Non-Surgical Fat Reduction", "", "Global", 730_980, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Chemical Peel", "", "Global", 534_831, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Cellulite Treatment", "", "Global", 379_224, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Injectables", "Calcium Hydroxylapatite", "", "Global", 290_095, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Full Field Ablative", "", "Global", 231_955, "procedures", "ISAPS page 10 worldwide non-surgical procedure table."),
]

GLOBAL_ROWS_2020 = [
    ("procedure_volume", "All procedures", "Total surgical and non-surgical", "", "Global", 24_529_875, "procedures", "ISAPS page 12 total procedures."),
    ("procedure_volume", "Surgical procedures", "Total surgical procedures", "", "Global", 10_129_528, "procedures", "ISAPS page 9 global surgical total."),
    ("procedure_volume", "Non-surgical procedures", "Total non-surgical procedures", "", "Global", 14_400_347, "procedures", "ISAPS page 10/page 12 global nonsurgical total."),
    ("procedure_volume", "Injectables", "Total injectable procedures", "", "Global", 10_610_748, "procedures", "ISAPS page 12 injectable procedure group."),
    ("procedure_volume", "Facial rejuvenation", "Total facial rejuvenation procedures", "", "Global", 1_392_083, "procedures", "ISAPS page 12 nonsurgical facial rejuvenation group."),
    ("procedure_volume", "Other non-surgical", "Total other procedures", "", "Global", 2_397_516, "procedures", "ISAPS page 12 other nonsurgical group."),
    ("procedure_volume", "Injectables", "Botulinum Toxin", "", "Global", 6_213_859, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Injectables", "Hyaluronic Acid", "", "Global", 4_053_016, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Hair Removal", "", "Global", 1_837_052, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Other non-surgical", "Non-Surgical Fat Reduction", "", "Global", 560_464, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Photo Rejuvenation", "", "Global", 517_675, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Chemical Peel", "", "Global", 409_054, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Micro-Ablative Resurfacing", "", "Global", 240_213, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Facial rejuvenation", "Full Field Ablative", "", "Global", 225_141, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Injectables", "Calcium Hydroxylapatite", "", "Global", 222_785, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
    ("procedure_volume", "Injectables", "Poly-L-Lactic Acid", "", "Global", 121_087, "procedures", "ISAPS page 10 worldwide nonsurgical procedure table."),
]


COUNTRY_PROCEDURE_LABELS = [
    ("Botulinum Toxin", "Injectables"),
    ("Calcium Hydroxyapatite", "Injectables"),
    ("Calcium Hydroxylapatite", "Injectables"),
    ("Hyaluronic Acid", "Injectables"),
    ("Poly-L-Lactic Acid", "Injectables"),
    ("Chemical Peel", "Facial rejuvenation"),
    ("Full Field Ablative", "Facial rejuvenation"),
    ("Micro-Ablative Resurfacing", "Facial rejuvenation"),
    ("Non-Surgical Skin Tightening", "Facial rejuvenation"),
    ("Photo Rejuvenation", "Facial rejuvenation"),
    ("Cellulite Treatment", "Other non-surgical"),
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

SURGEON_ROWS_2023 = [
    ("US", 7750),
    ("Brazil", 6457),
    ("Japan", 3050),
    ("China", 3000),
    ("India", 3000),
    ("South Korea", 2739),
    ("Argentina", 2500),
    ("Mexico", 2394),
    ("Russia", 2000),
    ("Turkiye", 1600),
    ("Germany", 1550),
    ("Egypt", 1450),
    ("Italy", 1151),
    ("France", 1000),
    ("Spain", 1000),
    ("Colombia", 825),
    ("Taiwan", 750),
    ("Venezuela", 725),
    ("UK", 717),
    ("Netherlands", 600),
    ("Peru", 575),
    ("Thailand", 500),
    ("Canada", 450),
    ("Iran", 450),
    ("Australia", 424),
    ("Saudi Arabia", 420),
    ("Romania", 350),
    ("Ukraine", 350),
    ("Belgium", 335),
    ("Switzerland", 313),
]

SURGEON_ROWS_2022 = [
    ("US", 7461),
    ("Brazil", 6200),
    ("Japan", 3050),
    ("China", 3000),
    ("South Korea", 2718),
    ("India", 2600),
    ("Mexico", 2394),
    ("Argentina", 2200),
    ("Russia", 2000),
    ("Germany", 1550),
    ("Egypt", 1450),
    ("Turkey", 1300),
    ("Colombia", 1200),
    ("Italy", 1151),
    ("France", 1000),
    ("Spain", 900),
    ("Taiwan", 750),
    ("Venezuela", 674),
    ("Netherlands", 600),
    ("United Kingdom", 600),
    ("Peru", 575),
    ("Thailand", 475),
    ("Canada", 450),
    ("Iran (Islamic Republic of)", 429),
    ("Australia", 425),
    ("Greece", 400),
    ("Romania", 350),
    ("Ukraine", 350),
    ("Belgium", 335),
    ("Indonesia", 298),
]

SURGEON_ROWS_2021 = [
    ("USA", 7500),
    ("Brazil", 6000),
    ("China", 3000),
    ("Japan", 2750),
    ("South Korea", 2600),
    ("India", 2400),
    ("Russia", 2000),
    ("Argentina", 2000),
    ("Mexico", 1750),
    ("Germany", 1550),
    ("Turkey", 1300),
    ("Italy", 1200),
    ("Colombia", 1200),
    ("France", 1000),
    ("Spain", 900),
    ("Taiwan", 750),
    ("Venezuela", 700),
    ("United Kingdom", 600),
    ("Netherlands", 600),
    ("Egypt", 600),
    ("Peru", 575),
    ("Thailand", 475),
    ("Canada", 450),
    ("Australia", 425),
    ("Greece", 350),
    ("Ukraine", 350),
    ("Romania", 350),
    ("Iran", 300),
    ("Belgium", 275),
    ("Austria", 250),
]

SURGEON_ROWS_2020 = [
    ("USA", 7000),
    ("Brazil", 5843),
    ("China", 3000),
    ("Japan", 2707),
    ("South Korea", 2581),
    ("India", 2400),
    ("Russia", 2000),
    ("Argentina", 2000),
    ("Mexico", 1749),
    ("Germany", 1541),
    ("Turkey", 1300),
    ("Italy", 1200),
    ("Colombia", 1200),
    ("France", 1020),
    ("Spain", 900),
    ("Taiwan", 759),
    ("Venezuela", 700),
    ("United Kingdom", 619),
    ("Netherlands", 605),
    ("Egypt", 570),
    ("Peru", 563),
    ("Thailand", 465),
    ("Canada", 460),
    ("Australia", 424),
    ("Greece", 350),
    ("Ukraine", 350),
    ("Romania", 342),
    ("Iran", 310),
    ("Belgium", 280),
    ("Austria", 260),
]


COUNTRY_NAME_MAP = {
    "US": "United States",
    "USA": "United States",
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
    "TAIWAN": "Chinese Taipei",
    "TURKEY": "Turkiye",
    "UNITED KINGDOM": "UK",
    "IRAN (ISLAMIC REPUBLIC OF)": "Iran",
}

CANONICAL_PROCEDURE_LABELS = {
    "Calcium Hydroxyapatite": "Calcium Hydroxylapatite",
    "Nonsurgical Fat Reduction": "Non-Surgical Fat Reduction",
}


REPORT_CONFIGS = {
    2024: {
        "year": 2024,
        "report_path": Path(r"E:\shared\行业报告\2024 isaps-global-survey.pdf"),
        "report_title": "2024 ISAPS International Survey on Aesthetic/Cosmetic Procedures Performed in 2024",
        "official_url": "https://www.isaps.org/media/30xldsyf/isaps-global-survey-2024.pdf",
        "global_rows": GLOBAL_ROWS,
        "surgeon_rows": SURGEON_ROWS,
        "country_page_start": 14,
        "country_page_stop": 46,
        "surgeon_note": "ISAPS page 60 ranked estimated number of plastic surgeons.",
    },
    2023: {
        "year": 2023,
        "report_path": Path(r"E:\shared\行业报告\2023isaps-global-survey.pdf"),
        "report_title": "2023 ISAPS International Survey on Aesthetic/Cosmetic Procedures Performed in 2023",
        "official_url": "https://www.isaps.org/media/rxnfqibn/isaps-global-survey_2023.pdf",
        "global_rows": GLOBAL_ROWS_2023,
        "surgeon_rows": SURGEON_ROWS_2023,
        "country_page_start": 14,
        "country_page_stop": 37,
        "surgeon_note": "ISAPS page 47 ranked estimated number of plastic surgeons.",
    },
    2022: {
        "year": 2022,
        "report_path": Path(r"E:\shared\行业报告\2022isaps-global-survey.pdf"),
        "report_title": "2022 ISAPS International Survey on Aesthetic/Cosmetic Procedures Performed in 2022",
        "official_url": "https://www.isaps.org/media/a0qfm4h3/isaps-global-survey_2022.pdf",
        "global_rows": GLOBAL_ROWS_2022,
        "surgeon_rows": SURGEON_ROWS_2022,
        "country_page_start": 14,
        "country_page_stop": 30,
        "surgeon_note": "ISAPS page 38 ranked estimated number of plastic surgeons.",
    },
    2021: {
        "year": 2021,
        "report_path": Path(r"E:\shared\行业报告\2021isaps-global-survey.pdf"),
        "report_title": "2021 ISAPS International Survey on Aesthetic/Cosmetic Procedures Performed in 2021",
        "official_url": "https://www.isaps.org/media/vdpdanke/isaps-global-survey_2021.pdf",
        "global_rows": GLOBAL_ROWS_2021,
        "surgeon_rows": SURGEON_ROWS_2021,
        "country_page_start": 14,
        "country_page_stop": 28,
        "surgeon_note": "ISAPS page 36 ranked estimated number of plastic surgeons.",
    },
    2020: {
        "year": 2020,
        "report_path": Path(r"E:\shared\行业报告\2020isaps-global-survey.pdf"),
        "report_title": "2020 ISAPS International Survey on Aesthetic/Cosmetic Procedures Performed in 2020",
        "official_url": "https://www.isaps.org/media/dzjfg50s/isaps-global-survey_2020.pdf",
        "global_rows": GLOBAL_ROWS_2020,
        "surgeon_rows": SURGEON_ROWS_2020,
        "country_page_start": 14,
        "country_page_stop": 28,
        "surgeon_note": "ISAPS page 36 ranked estimated number of plastic surgeons.",
    },
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


def normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def canonical_geo(value: str) -> str:
    return COUNTRY_NAME_MAP.get(value.upper(), value)


def number_after_label(lines: list[str], label: str) -> int | None:
    pattern = re.compile(re.escape(label) + r"\s+([0-9, ]+)$", re.I)
    target = normalize_label(label)
    for index, line in enumerate(lines):
        match = pattern.search(line)
        if match:
            return clean_num(match.group(1))
        if line.lower() == label.lower():
            for next_line in lines[index + 1 : index + 5]:
                value = clean_num(next_line)
                if value is not None:
                    return value
        combined = ""
        for end_index in range(index, min(index + 3, len(lines))):
            combined = f"{combined} {lines[end_index]}".strip()
            if target and normalize_label(combined) == target:
                for next_line in lines[end_index + 1 : end_index + 6]:
                    value = clean_num(next_line)
                    if value is not None:
                        return value
    return None


def first_number_after_label(lines: list[str], labels: list[str]) -> int | None:
    for label in labels:
        value = number_after_label(lines, label)
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
    if len(candidates) >= 2:
        combined = f"{candidates[-2]} {candidates[-1]}".upper()
        if combined in COUNTRY_NAME_MAP:
            raw = combined
    return canonical_geo(raw.upper()) if raw.upper() in COUNTRY_NAME_MAP else raw.title()


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
    config: dict[str, object],
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
        "geo": canonical_geo(geo),
        "value": str(value),
        "unit": unit,
        "year": str(config["year"]),
        "source_org": SOURCE_ORG,
        "report_title": str(config["report_title"]),
        "url": str(config.get("official_url") or ""),
        "note": note,
        "confidence": "official_association_report",
    }


def extract_rows(report_path: Path, config: dict[str, object]) -> list[dict[str, str]]:
    try:
        import fitz  # type: ignore
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError("PyMuPDF/fitz is required to read the ISAPS PDF.") from exc

    rows: list[dict[str, str]] = []
    for data_type, cat1, cat2, cat3, geo, value, unit, note in config["global_rows"]:
        rows.append(metric_row(report_path, config, data_type, cat1, cat2, cat3, geo, value, unit, note))

    with fitz.open(report_path) as doc:
        start = int(config.get("country_page_start") or 14)
        stop = int(config.get("country_page_stop") or 45)
        for page_index in range(start, min(stop, doc.page_count)):
            lines = clean_lines(doc[page_index].get_text("text"))
            country = country_from_page(lines)
            if not country:
                continue
            page_note = f"ISAPS page {page_index + 1} country procedure table."
            totals = [
                ("procedure_volume", "All procedures", "Country total procedures", country_total(lines)),
                ("procedure_volume", "Surgical procedures", "Country surgical procedures", number_after_label(lines, "TOTAL SURGICAL PROCEDURES")),
                (
                    "procedure_volume",
                    "Non-surgical procedures",
                    "Country non-surgical procedures",
                    first_number_after_label(
                        lines,
                        [
                            "TOTAL NON-SURGICAL PROCEDURES",
                            "TOTAL NONSURGICAL PROCEDURES",
                            "TOTAL NONSURGICAL POCEDURES PROCEDURES",
                        ],
                    ),
                ),
                ("procedure_volume", "Injectables", "Country total injectables", number_after_label(lines, "TOTAL INJECTABLES")),
                ("procedure_volume", "Facial rejuvenation", "Country total facial rejuvenation", number_after_label(lines, "TOTAL FACIAL REJUVENATION")),
                ("procedure_volume", "Other non-surgical", "Country total other non-surgical", number_after_label(lines, "TOTAL OTHER")),
            ]
            for data_type, cat1, cat2, value in totals:
                if value is not None:
                    rows.append(metric_row(report_path, config, data_type, cat1, cat2, "", country, value, "procedures", page_note))

            seen_labels: set[str] = set()
            for label, group in COUNTRY_PROCEDURE_LABELS:
                value = number_after_label(lines, label)
                canonical = CANONICAL_PROCEDURE_LABELS.get(label, label)
                if value is not None and canonical not in seen_labels:
                    seen_labels.add(canonical)
                    rows.append(metric_row(report_path, config, "procedure_volume", group, canonical, "", country, value, "procedures", page_note))

    for country, value in config["surgeon_rows"]:
        rows.append(
            metric_row(
                report_path,
                config,
                "estimated_plastic_surgeons",
                "Workforce",
                "Estimated plastic surgeons",
                "",
                country,
                value,
                "surgeons",
                str(config.get("surgeon_note") or "ISAPS ranked estimated number of plastic surgeons."),
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

    parser = argparse.ArgumentParser(description="Extract ISAPS survey metrics into a dashboard CSV.")
    parser.add_argument("--report", type=Path, default=None, help="Optional report path for a single configured year.")
    parser.add_argument("--year", type=int, choices=sorted(REPORT_CONFIGS), help="Extract one configured survey year.")
    parser.add_argument("--all", action="store_true", help="Extract every configured survey year. This is the default.")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    years = [args.year] if args.year else sorted(REPORT_CONFIGS, reverse=True)
    rows: list[dict[str, str]] = []
    missing_reports = []
    for year in years:
        config = dict(REPORT_CONFIGS[year])
        report_path = args.report if args.report and args.year == year else config["report_path"]
        report_path = Path(report_path)
        if not report_path.exists():
            missing_reports.append({"year": year, "report": str(report_path)})
            continue
        rows.extend(extract_rows(report_path, config))

    if missing_reports:
        raise SystemExit(json.dumps({"status": "missing_report", "missing": missing_reports}, ensure_ascii=False))

    write_rows(rows, args.output)
    countries = sorted({row["geo"] for row in rows if row["geo"] not in {"Global"}})
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "rows": len(rows),
                "countries": len(countries),
                "years": years,
                "source": [str(REPORT_CONFIGS[year]["report_path"]) for year in years],
                "captured_at": now_iso(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
