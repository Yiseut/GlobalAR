#!/usr/bin/env python3
from __future__ import annotations

import csv
import re
from pathlib import Path

import pdfplumber


PROJECT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = PROJECT_DIR / "data" / "europe_association_market_metrics.csv"

SECPRE_PDF_PATH = (
    PROJECT_DIR
    / "data"
    / "commercial_sources"
    / "geo_market_sources"
    / "spain_secpre_aesthetic_surgery_report"
    / "unknown-year__pdf__secpre-aesthetic-surgery-reality-in-spain-report__765a793c.pdf"
)
SECPRE_URL = "https://portalsecpre.org/images/noticias/Informe%20SECPRE_IMOP%202022%20prensa.pdf"
SECPRE_REPORT_TITLE = "La realidad de la cirugia estetica en Espana. 2022"

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

GROUP_LABELS = {
    "Cirugia de la mama",
    "Cirugia de la cabeza",
    "Liposuccion",
    "Cirugia corporal",
    "Rellenos con grasa autologa",
}

LABEL_NORMALIZATIONS = {
    "Cirugía de la mama": "Cirugia de la mama",
    "Aumento de mamas con implante": "Aumento de mamas con implante",
    "Aumento de mamas con grasa autóloga": "Aumento de mamas con grasa autologa",
    "Elevación de Mamas": "Elevacion de mamas",
    "Aumento + Elevación de mamas": "Aumento + elevacion de mamas",
    "Reducción de Mamas": "Reduccion de mamas",
    "Ginecomastia": "Ginecomastia",
    "Cirugía de la cabeza": "Cirugia de la cabeza",
    "Blefaroplastia": "Blefaroplastia",
    "Lifting Facial": "Lifting facial",
    "Mentoplastia": "Mentoplastia",
    "Otoplastia": "Otoplastia",
    "Rinoplastia": "Rinoplastia",
    "Liposucción": "Liposuccion",
    "Liposucción por aspiración convencional": "Liposuccion por aspiracion convencional",
    "Liposucción asistida por láser, ultrasonido o radiofrecuencia": "Liposuccion asistida por laser, ultrasonido o radiofrecuencia",
    "Cirugía corporal": "Cirugia corporal",
    "Abdominoplastia": "Abdominoplastia",
    "Aumento de glúteos": "Aumento de gluteos",
    "Lifting de brazos": "Lifting de brazos",
    "Lifting de muslos": "Lifting de muslos",
    "Cirugía genital": "Cirugia genital",
    "Rellenos con grasa autóloga": "Rellenos con grasa autologa",
    "Relleno facial con grasa autóloga": "Relleno facial con grasa autologa",
    "Relleno de glúteos con grasa autóloga": "Relleno de gluteos con grasa autologa",
}

COUNT_RE = re.compile(r"^(?P<label>.+?)\s+(?P<count>\d{1,3}(?:\.\d{3})*)\s+(?P<pct>\d{1,3},\d%?)$")
TOTAL_RE = re.compile(r"^(?P<count>\d{1,3}(?:\.\d{3})*)\s+100%$")


def normalize_label(label: str) -> str:
    return LABEL_NORMALIZATIONS.get(label.strip(), label.strip())


def parse_secpre_2021_table() -> list[dict[str, str]]:
    if not SECPRE_PDF_PATH.exists():
        raise FileNotFoundError(SECPRE_PDF_PATH)

    with pdfplumber.open(SECPRE_PDF_PATH) as pdf:
        text = pdf.pages[15].extract_text(x_tolerance=1, y_tolerance=3) or ""

    rows: list[dict[str, str]] = []
    current_group = ""
    in_table = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "TIPO DE INTERVENCIÓN":
            in_table = True
            continue
        if line.startswith("Con relación"):
            break
        if not in_table or not line or line in {"Nº %", "INTERVENCIONES EN 2021"}:
            continue

        total_match = TOTAL_RE.match(line)
        if total_match:
            count = int(total_match.group("count").replace(".", ""))
            rows.insert(
                0,
                metric_row(
                    value=count,
                    category_l2="Total aesthetic surgery interventions",
                    category_l3="",
                    pct="100%",
                    note_extra="SECPRE Table 1 total aesthetic surgery interventions in Spain, surgical-only count.",
                ),
            )
            continue

        match = COUNT_RE.match(line)
        if not match:
            continue
        label = normalize_label(match.group("label"))
        count = int(match.group("count").replace(".", ""))
        pct = match.group("pct")

        if label in GROUP_LABELS:
            current_group = label
            rows.append(
                metric_row(
                    value=count,
                    category_l2=label,
                    category_l3="",
                    pct=pct,
                    note_extra="SECPRE Table 1 grouped aesthetic surgery intervention count.",
                )
            )
        elif current_group:
            rows.append(
                metric_row(
                    value=count,
                    category_l2=current_group,
                    category_l3=label,
                    pct=pct,
                    note_extra="SECPRE Table 1 procedure-level aesthetic surgery intervention count.",
                )
            )
    return rows


def metric_row(value: int, category_l2: str, category_l3: str, pct: str, note_extra: str) -> dict[str, str]:
    note = (
        f"{note_extra} Percent column in source table: {pct}. "
        "Keep as Spain surgical-only association lane; do not merge silently with ISAPS total procedures."
    )
    return {
        "source_file": str(SECPRE_PDF_PATH.relative_to(PROJECT_DIR)),
        "data_type": "procedure_volume",
        "category_l1": "Surgical procedures",
        "category_l2": category_l2,
        "category_l3": category_l3,
        "geo": "Spain",
        "value": str(value),
        "unit": "procedures",
        "year": "2021",
        "source_org": "SECPRE",
        "report_title": SECPRE_REPORT_TITLE,
        "url": SECPRE_URL,
        "note": (
            note
            + " Use the source-reported total row as authoritative; grouped/subprocedure rows are not used to recalculate the total."
        ),
        "confidence": "official_association_report_manual_qa_surgical_only",
    }


def main() -> int:
    rows = parse_secpre_2021_table()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {OUTPUT_PATH} · {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
