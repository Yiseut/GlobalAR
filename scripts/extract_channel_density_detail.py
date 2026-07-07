#!/usr/bin/env python3
"""Build aggregate channel-density denominator rows from official sources."""

from __future__ import annotations

import csv
import re
import zipfile
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_DIR / "data" / "commercial_channel_density_detail.csv"
HK_DH_SOURCE_DIR = PROJECT_DIR / "data" / "commercial_sources" / "geo_market_sources" / "hong_kong_dh_day_procedure_centres"
TAIWAN_MEDICAL_FACILITY_SOURCE_DIR = (
    PROJECT_DIR / "data" / "commercial_sources" / "geo_market_sources" / "taiwan_mohw_medical_facility_open_data"
)

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
TAIWAN_CITY_CODE_NAMES = [
    ("臺北市", "Taipei City", "TPE"),
    ("台北市", "Taipei City", "TPE"),
    ("新北市", "New Taipei City", "NWT"),
    ("桃園市", "Taoyuan City", "TAO"),
    ("新竹市", "Hsinchu City", "HSZ"),
    ("新竹縣", "Hsinchu County", "HSQ"),
    ("苗栗縣", "Miaoli County", "MIA"),
    ("臺中市", "Taichung City", "TXG"),
    ("台中市", "Taichung City", "TXG"),
    ("彰化縣", "Changhua County", "CHA"),
    ("雲林縣", "Yunlin County", "YUN"),
    ("嘉義縣", "Chiayi County", "CYQ"),
    ("嘉義市", "Chiayi City", "CYI"),
    ("臺南市", "Tainan City", "TNN"),
    ("台南市", "Tainan City", "TNN"),
    ("高雄市", "Kaohsiung City", "KHH"),
    ("花蓮縣", "Hualien County", "HUA"),
    ("宜蘭縣", "Yilan County", "ILA"),
    ("基隆市", "Keelung City", "KEE"),
    ("屏東縣", "Pingtung County", "PIF"),
    ("臺東縣", "Taitung County", "TTT"),
    ("台東縣", "Taitung County", "TTT"),
    ("南投縣", "Nantou County", "NAN"),
    ("澎湖縣", "Penghu County", "PEN"),
    ("連江縣", "Lienchiang County", "LIE"),
    ("金門縣", "Kinmen County", "KIN"),
]
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

TAIWAN_MEDICAL_FACILITY_SOURCE_ID = "taiwan_mohw_medical_facility_open_data"
TAIWAN_MEDICAL_FACILITY_SOURCE_ORG = "Taiwan MOHW"
TAIWAN_MEDICAL_FACILITY_REPORT_TITLE = "Medical Institutions and Personnel Basic Data 2024-12-31"
TAIWAN_MEDICAL_FACILITY_SOURCE_URL = "https://www.mohw.gov.tw/dl-96581-66dbb751-f83a-416a-a998-893222e20fef.html"
TAIWAN_MEDICAL_FACILITY_YEAR = "2024"
ODS_TABLE_NS = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
ODS_TEXT_NS = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"

JAPAN_SOURCE_ID = "japan_mhlw_aesthetic_medicine_status"
JAPAN_SOURCE_ORG = "MHLW"
JAPAN_REPORT_TITLE = "Current Status of Aesthetic Medicine"
JAPAN_SOURCE_URL = "https://www.mhlw.go.jp/content/10803000/001363278.pdf"
JAPAN_SURVEY_FRAME_COUNTS = [
    ("2019", 3093, 423),
    ("2020", 2835, 580),
    ("2021", 2872, 306),
    ("2022", 5270, 517),
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


def taiwan_city_from_district(value: str) -> tuple[str, str]:
    for prefix, name, code in TAIWAN_CITY_CODE_NAMES:
        if (value or "").startswith(prefix):
            return name, code
    return "", ""


def ods_cell_text(cell: ET.Element) -> str:
    return "".join(cell.itertext()).strip()


def iter_ods_rows(path: Path, max_columns: int = 24):
    table_row_tag = f"{{{ODS_TABLE_NS}}}table-row"
    table_cell_tag = f"{{{ODS_TABLE_NS}}}table-cell"
    repeat_rows_key = f"{{{ODS_TABLE_NS}}}number-rows-repeated"
    repeat_cols_key = f"{{{ODS_TABLE_NS}}}number-columns-repeated"
    with zipfile.ZipFile(path) as archive:
        with archive.open("content.xml") as handle:
            for _event, elem in ET.iterparse(handle, events=("end",)):
                if elem.tag != table_row_tag:
                    continue
                repeat_rows = int(elem.attrib.get(repeat_rows_key, "1"))
                values: list[str] = []
                for cell in elem.findall(table_cell_tag):
                    repeat_cols = int(cell.attrib.get(repeat_cols_key, "1"))
                    value = ods_cell_text(cell)
                    for _ in range(repeat_cols):
                        values.append(value)
                        if len(values) >= max_columns:
                            break
                    if len(values) >= max_columns:
                        break
                if any(values):
                    for _ in range(min(repeat_rows, 1)):
                        yield values
                elem.clear()


def read_taiwan_medical_facility_aggregates() -> tuple[Counter, Counter]:
    candidates = sorted(TAIWAN_MEDICAL_FACILITY_SOURCE_DIR.glob("*.ods"))
    if not candidates:
        raise FileNotFoundError(f"Taiwan MOHW medical facility ODS not found under {TAIWAN_MEDICAL_FACILITY_SOURCE_DIR}")
    facility_counts: Counter = Counter()
    physician_counts: Counter = Counter()
    header: list[str] | None = None
    city_index = -1
    physician_index = -1
    code_index = -1
    for values in iter_ods_rows(candidates[0]):
        if header is None:
            if "機構代碼" in values and "縣市區名" in values:
                header = values
                code_index = header.index("機構代碼")
                city_index = header.index("縣市區名")
                physician_index = header.index("A醫師")
            continue
        if code_index >= len(values) or not values[code_index]:
            continue
        city_name, city_code = taiwan_city_from_district(values[city_index] if city_index < len(values) else "")
        if not city_name:
            continue
        key = (city_name, city_code)
        facility_counts[key] += 1
        try:
            physician_counts[key] += int(float(values[physician_index] if physician_index < len(values) else 0))
        except ValueError:
            pass
    return facility_counts, physician_counts


def taiwan_medical_facility_row(
    *,
    admin_level: str,
    admin_name: str,
    admin_code: str,
    metric: str,
    value: int,
) -> dict[str, str]:
    return {
        "source_id": TAIWAN_MEDICAL_FACILITY_SOURCE_ID,
        "country": "Taiwan",
        "admin_level": admin_level,
        "admin_name": admin_name,
        "admin_code": admin_code,
        "city": admin_name if admin_level == "city_county" else "",
        "metric": metric,
        "value": str(value),
        "unit": "facilities" if metric == "medical_facility_count" else "physicians",
        "year": TAIWAN_MEDICAL_FACILITY_YEAR,
        "source_org": TAIWAN_MEDICAL_FACILITY_SOURCE_ORG,
        "report_title": TAIWAN_MEDICAL_FACILITY_REPORT_TITLE,
        "source_url": TAIWAN_MEDICAL_FACILITY_SOURCE_URL,
        "source_page": "",
        "note": (
            "MOHW open-data ODS snapshot 2024-12-31. Aggregated from county/district rows and excludes phone/address fields. "
            "This is a general medical-supply denominator, not aesthetic-specific facility coverage or treatment volume."
        ),
        "confidence": "official_government_open_data_ods_aggregate_no_contacts",
    }


def build_taiwan_medical_facility_rows() -> list[dict[str, str]]:
    facility_counts, physician_counts = read_taiwan_medical_facility_aggregates()
    rows = [
        taiwan_medical_facility_row(
            admin_level="country",
            admin_name="Taiwan",
            admin_code="",
            metric="medical_facility_count",
            value=sum(facility_counts.values()),
        ),
        taiwan_medical_facility_row(
            admin_level="country",
            admin_name="Taiwan",
            admin_code="",
            metric="western_physician_count",
            value=sum(physician_counts.values()),
        ),
    ]
    for city_name, city_code in sorted(facility_counts.keys()):
        rows.append(
            taiwan_medical_facility_row(
                admin_level="city_county",
                admin_name=city_name,
                admin_code=city_code,
                metric="medical_facility_count",
                value=facility_counts[(city_name, city_code)],
            )
        )
        rows.append(
            taiwan_medical_facility_row(
                admin_level="city_county",
                admin_name=city_name,
                admin_code=city_code,
                metric="western_physician_count",
                value=physician_counts[(city_name, city_code)],
            )
        )
    return rows


def build_japan_mhlw_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    note = (
        "MHLW material page 5 reproduces the JSAPS national aesthetic medicine survey overview. "
        "Counts are survey target and responding medical institutions; use as Japan local survey-frame/channel-coverage proxy, "
        "not treatment volume or full provider census."
    )
    for year, target_count, response_count in JAPAN_SURVEY_FRAME_COUNTS:
        for metric, value in [
            ("aesthetic_survey_target_institution_count", target_count),
            ("aesthetic_survey_response_institution_count", response_count),
        ]:
            rows.append(
                {
                    "source_id": JAPAN_SOURCE_ID,
                    "country": "Japan",
                    "admin_level": "country",
                    "admin_name": "Japan",
                    "admin_code": "",
                    "city": "",
                    "metric": metric,
                    "value": str(value),
                    "unit": "institutions",
                    "year": year,
                    "source_org": JAPAN_SOURCE_ORG,
                    "report_title": JAPAN_REPORT_TITLE,
                    "source_url": JAPAN_SOURCE_URL,
                    "source_page": "5",
                    "note": note,
                    "confidence": "official_government_meeting_material_survey_frame_manual_qa",
                }
            )
    return rows


def build_rows() -> list[dict[str, str]]:
    return [
        *build_brazil_sbcp_rows(),
        *build_hong_kong_dh_rows(),
        *build_taiwan_mohw_rows(),
        *build_taiwan_medical_facility_rows(),
        *build_japan_mhlw_rows(),
    ]


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
