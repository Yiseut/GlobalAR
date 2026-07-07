#!/usr/bin/env python3
"""Build aggregate channel-density denominator rows from official sources."""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_DIR / "data" / "commercial_channel_density_detail.csv"
HK_DH_SOURCE_DIR = PROJECT_DIR / "data" / "commercial_sources" / "geo_market_sources" / "hong_kong_dh_day_procedure_centres"

FIELDS = [
    "source_id",
    "country",
    "admin_level",
    "admin_name",
    "admin_code",
    "city",
    "metric",
    "value",
    "unit",
    "year",
    "source_org",
    "report_title",
    "source_url",
    "source_page",
    "note",
    "confidence",
]

BRAZIL_SOURCE_ID = "brazil_sbcp_pesquisas_censo"
BRAZIL_SOURCE_ORG = "SBCP"
BRAZIL_REPORT_TITLE = "Plastiko's 2025 Demografia da Cirurgia Plastica Brasileira"
BRAZIL_SOURCE_URL = "https://online.fliphtml5.com/urtuw/REVISTA_CENSO_2025_V06/"
BRAZIL_STATE_SURGEON_COUNTS = [
    ("Roraima", "RR", 6),
    ("Amazonas", "AM", 31),
    ("Acre", "AC", 4),
    ("Rondonia", "RO", 27),
    ("Mato Grosso", "MT", 69),
    ("Para", "PA", 70),
    ("Amapa", "AP", 6),
    ("Maranhao", "MA", 33),
    ("Tocantins", "TO", 22),
    ("Goias", "GO", 254),
    ("Distrito Federal", "DF", 196),
    ("Mato Grosso do Sul", "MS", 83),
    ("Rio Grande do Sul", "RS", 457),
    ("Santa Catarina", "SC", 244),
    ("Parana", "PR", 388),
    ("Sao Paulo", "SP", 2184),
    ("Rio de Janeiro", "RJ", 922),
    ("Espirito Santo", "ES", 129),
    ("Minas Gerais", "MG", 762),
    ("Bahia", "BA", 197),
    ("Sergipe", "SE", 36),
    ("Alagoas", "AL", 37),
    ("Pernambuco", "PE", 161),
    ("Paraiba", "PB", 56),
    ("Rio Grande do Norte", "RN", 50),
    ("Ceara", "CE", 141),
    ("Piaui", "PI", 39),
]

HK_SOURCE_ID = "hong_kong_dh_day_procedure_centres"
HK_SOURCE_ORG = "Hong Kong Department of Health"
HK_REPORT_TITLE = "Private healthcare facilities with valid licence / letter of exemption under Cap. 633"
HK_SOURCE_URL = "https://www.dh.gov.hk/datagovhk/orphf/DPC_Cap.633_20251217_eng.csv"
HK_SNAPSHOT_YEAR = "2025"
HK_DISTRICT_RE = re.compile(r"([A-Z][A-Z &]+ DISTRICT)")

TAIWAN_SOURCE_ID = "taiwan_mohw_aesthetic_medicine_institutions"
TAIWAN_SOURCE_ORG = "Taiwan MOHW"
TAIWAN_REPORT_TITLE = "Approved Medical Institutions for Specific Aesthetic Medicine Surgery"
TAIWAN_SOURCE_URL = "https://www.mohw.gov.tw/dl-54656-61753779-bc51-414b-9f16-1ea8624387a8.html"
TAIWAN_SNAPSHOT_YEAR = "2025"
TAIWAN_CITY_APPROVED_INSTITUTION_COUNTS = [
    ("Taipei City", "TPE", "Taipei City", 151),
    ("New Taipei City", "NWT", "New Taipei City", 18),
    ("Taoyuan City", "TAO", "Taoyuan City", 27),
    ("Hsinchu City", "HSZ", "Hsinchu City", 7),
    ("Hsinchu County", "HSQ", "Hsinchu County", 12),
    ("Miaoli County", "MIA", "Miaoli County", 2),
    ("Taichung City", "TXG", "Taichung City", 89),
    ("Changhua County", "CHA", "Changhua County", 7),
    ("Yunlin County", "YUN", "Yunlin County", 2),
    ("Chiayi County", "CYQ", "Chiayi County", 2),
    ("Chiayi City", "CYI", "Chiayi City", 7),
    ("Tainan City", "TNN", "Tainan City", 30),
    ("Kaohsiung City", "KHH", "Kaohsiung City", 62),
    ("Hualien County", "HUA", "Hualien County", 3),
    ("Yilan County", "ILA", "Yilan County", 4),
    ("Keelung City", "KEE", "Keelung City", 3),
    ("Pingtung County", "PIF", "Pingtung County", 4),
    ("Taitung County", "TTT", "Taitung County", 3),
    ("Nantou County", "NAN", "Nantou County", 2),
    ("Penghu County", "PEN", "Penghu County", 0),
    ("Lienchiang County", "LIE", "Lienchiang County", 0),
    ("Kinmen County", "KIN", "Kinmen County", 0),
]


def build_brazil_sbcp_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for state_name, state_code, value in BRAZIL_STATE_SURGEON_COUNTS:
        rows.append(
            {
                "source_id": BRAZIL_SOURCE_ID,
                "country": "Brazil",
                "admin_level": "state",
                "admin_name": state_name,
                "admin_code": state_code,
                "city": "",
                "metric": "plastic_surgeon_count",
                "value": str(value),
                "unit": "surgeons",
                "year": "2025",
                "source_org": BRAZIL_SOURCE_ORG,
                "report_title": BRAZIL_REPORT_TITLE,
                "source_url": BRAZIL_SOURCE_URL,
                "source_page": "4",
                "note": (
                    "SBCP Censo 2025 page 4 state-level map, number of plastic surgeons. "
                    "Use as Brazil channel-density denominator, not treatment volume."
                ),
                "confidence": "official_association_flipbook_manual_qa_state_denominator",
            }
        )
    return rows


def extract_hk_district(address: str) -> str:
    match = HK_DISTRICT_RE.search(address or "")
    if match:
        return match.group(1).title().replace(" And ", " & ")
    if "DES VOEUX ROAD CENTRAL" in (address or "").upper() or "CENTRAL, HONG KONG" in (address or "").upper():
        return "Central & Western District"
    return ""


def read_hk_dh_rows() -> list[dict[str, str]]:
    candidates = sorted(HK_DH_SOURCE_DIR.glob("*b17b9354.csv"))
    if not candidates:
        raise FileNotFoundError(f"Hong Kong DH English CSV not found under {HK_DH_SOURCE_DIR}")
    with candidates[0].open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def hk_density_row(
    *,
    admin_level: str,
    admin_name: str,
    metric: str,
    value: int,
    note_suffix: str,
) -> dict[str, str]:
    return {
        "source_id": HK_SOURCE_ID,
        "country": "Hong Kong",
        "admin_level": admin_level,
        "admin_name": admin_name,
        "admin_code": "",
        "city": "",
        "metric": metric,
        "value": str(value),
        "unit": "facilities",
        "year": HK_SNAPSHOT_YEAR,
        "source_org": HK_SOURCE_ORG,
        "report_title": HK_REPORT_TITLE,
        "source_url": HK_SOURCE_URL,
        "source_page": "",
        "note": (
            "DATA.GOV.HK / Hong Kong DH Cap. 633 CSV snapshot filename DPC_Cap.633_20251217_eng.csv. "
            f"{note_suffix} Use as channel-density proxy, not treatment volume."
        ),
        "confidence": "official_government_open_data_csv_aggregate_no_contacts",
    }


def build_hong_kong_dh_rows() -> list[dict[str, str]]:
    source_rows = read_hk_dh_rows()
    unique_rows = {row.get("PHF_num", ""): row for row in source_rows if row.get("PHF_num")}
    dpc_rows = [row for row in unique_rows.values() if row.get("PHF_category") == "Day Procedure Centre"]
    hospital_rows = [row for row in unique_rows.values() if row.get("PHF_category") == "Hospital"]

    output = [
        hk_density_row(
            admin_level="country",
            admin_name="Hong Kong",
            metric="licensed_day_procedure_centre_count",
            value=len(dpc_rows),
            note_suffix="Country total counts licensed day procedure centres only.",
        ),
        hk_density_row(
            admin_level="country",
            admin_name="Hong Kong",
            metric="licensed_private_hospital_count",
            value=len(hospital_rows),
            note_suffix="Country total counts private hospitals only.",
        ),
    ]

    for metric, rows, description in [
        ("licensed_day_procedure_centre_count", dpc_rows, "District aggregate counts licensed day procedure centres."),
        ("licensed_private_hospital_count", hospital_rows, "District aggregate counts private hospitals."),
    ]:
        counts = Counter()
        for row in rows:
            district = extract_hk_district(row.get("PHF_address", ""))
            if district:
                counts[district] += 1
        for district, value in sorted(counts.items()):
            output.append(
                hk_density_row(
                    admin_level="district",
                    admin_name=district,
                    metric=metric,
                    value=value,
                    note_suffix=description,
                )
            )
    return output


def build_taiwan_mohw_rows() -> list[dict[str, str]]:
    total = sum(row[3] for row in TAIWAN_CITY_APPROVED_INSTITUTION_COUNTS)
    note = (
        "MOHW PDF page 1 summary table, updated to 2025-06-30 (ROC 114-06-30). "
        "Counts approved medical institutions for specific aesthetic medicine surgery. "
        "Use as Taiwan city/county channel-density denominator, not treatment volume."
    )
    rows = [
        {
            "source_id": TAIWAN_SOURCE_ID,
            "country": "Taiwan",
            "admin_level": "country",
            "admin_name": "Taiwan",
            "admin_code": "",
            "city": "",
            "metric": "approved_aesthetic_medicine_institution_count",
            "value": str(total),
            "unit": "institutions",
            "year": TAIWAN_SNAPSHOT_YEAR,
            "source_org": TAIWAN_SOURCE_ORG,
            "report_title": TAIWAN_REPORT_TITLE,
            "source_url": TAIWAN_SOURCE_URL,
            "source_page": "1",
            "note": note,
            "confidence": "official_government_pdf_summary_manual_qa_city_denominator",
        }
    ]
    for admin_name, admin_code, city, value in TAIWAN_CITY_APPROVED_INSTITUTION_COUNTS:
        rows.append(
            {
                "source_id": TAIWAN_SOURCE_ID,
                "country": "Taiwan",
                "admin_level": "city_county",
                "admin_name": admin_name,
                "admin_code": admin_code,
                "city": city,
                "metric": "approved_aesthetic_medicine_institution_count",
                "value": str(value),
                "unit": "institutions",
                "year": TAIWAN_SNAPSHOT_YEAR,
                "source_org": TAIWAN_SOURCE_ORG,
                "report_title": TAIWAN_REPORT_TITLE,
                "source_url": TAIWAN_SOURCE_URL,
                "source_page": "1",
                "note": note,
                "confidence": "official_government_pdf_summary_manual_qa_city_denominator",
            }
        )
    return rows


def build_rows() -> list[dict[str, str]]:
    return [*build_brazil_sbcp_rows(), *build_hong_kong_dh_rows(), *build_taiwan_mohw_rows()]


def main() -> int:
    rows = build_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    total = sum(int(row["value"]) for row in rows if row["admin_level"] in {"country", "state"})
    print(f"Wrote {OUTPUT_PATH} · {len(rows)} rows · aggregate_total={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
