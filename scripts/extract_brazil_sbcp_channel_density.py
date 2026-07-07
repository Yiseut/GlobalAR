#!/usr/bin/env python3
"""Build Brazil SBCP 2025 state-level plastic surgeon denominator rows."""

from __future__ import annotations

import csv
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_DIR / "data" / "commercial_channel_density_detail.csv"

SOURCE_ID = "brazil_sbcp_pesquisas_censo"
SOURCE_ORG = "SBCP"
REPORT_TITLE = "Plastiko's 2025 Demografia da Cirurgia Plastica Brasileira"
SOURCE_URL = "https://online.fliphtml5.com/urtuw/REVISTA_CENSO_2025_V06/"

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


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for state_name, state_code, value in BRAZIL_STATE_SURGEON_COUNTS:
        rows.append(
            {
                "source_id": SOURCE_ID,
                "country": "Brazil",
                "admin_level": "state",
                "admin_name": state_name,
                "admin_code": state_code,
                "city": "",
                "metric": "plastic_surgeon_count",
                "value": str(value),
                "unit": "surgeons",
                "year": "2025",
                "source_org": SOURCE_ORG,
                "report_title": REPORT_TITLE,
                "source_url": SOURCE_URL,
                "source_page": "4",
                "note": (
                    "SBCP Censo 2025 page 4 state-level map, number of plastic surgeons. "
                    "Use as Brazil channel-density denominator, not treatment volume."
                ),
                "confidence": "official_association_flipbook_manual_qa_state_denominator",
            }
        )
    return rows


def main() -> int:
    rows = build_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUTPUT_PATH} · {len(rows)} rows · total={sum(int(row['value']) for row in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
