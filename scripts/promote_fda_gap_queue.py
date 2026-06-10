#!/usr/bin/env python3
"""Promote FDA evidence from the product gap queue.

The product gap queue already contains product-mapped FDA leads such as
AccessData PMN URLs and Innolitics URLs with K/P numbers. This script verifies
those identifiers against official FDA/openFDA endpoints, optionally extracts
Indications for Use from FDA PDFs, and appends conservative rows to
data/manual_official_indication_evidence.csv. It does not modify the source
Excel workbook.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except Exception:  # noqa: BLE001 - PDF extraction becomes optional.
    fitz = None


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDITS_DIR = DATA_DIR / "audits"
QUEUE_PATH = AUDITS_DIR / "product_gap_queue_latest.csv"
MANUAL_EVIDENCE_PATH = DATA_DIR / "manual_official_indication_evidence.csv"
REGISTRATION_EVIDENCE_PATH = DATA_DIR / "registration_evidence.csv"

OPENFDA_510K = "https://api.fda.gov/device/510k.json"
OPENFDA_PMA = "https://api.fda.gov/device/pma.json"

MANUAL_FIELDS = [
    "product_id",
    "seed_record_id",
    "company_id",
    "company",
    "brand",
    "jurisdiction",
    "regulator",
    "regulatory_pathway",
    "status",
    "registration_no",
    "approval_date",
    "expiry_date",
    "registered_name",
    "approved_indication",
    "intended_use",
    "legal_manufacturer",
    "local_holder",
    "source_key",
    "source_url",
    "source_type",
    "evidence_title",
    "evidence_excerpt",
    "checked_at",
    "reviewed_by",
    "review_status",
    "confidence",
]


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def stable_id(*parts: Any) -> str:
    raw = "|".join(norm(part).lower() for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def fetch_json(url: str, timeout: int = 18, retries: int = 3) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "GlobalAestheticsDashboard/0.1"})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return {}
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(0.8 * (attempt + 1))
                continue
            raise
        except (TimeoutError, urllib.error.URLError, json.JSONDecodeError):
            if attempt < retries:
                time.sleep(0.8 * (attempt + 1))
                continue
            return {}
    return {}


def openfda_search(endpoint: str, search: str, limit: int = 10) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"search": search, "limit": str(limit)})
    payload = fetch_json(f"{endpoint}?{params}")
    return payload.get("results") or []


def fetch_510k(k_number: str) -> dict[str, Any] | None:
    rows = openfda_search(OPENFDA_510K, f'k_number:"{k_number.upper()}"', 1)
    return rows[0] if rows else None


def split_pma_number(value: str) -> tuple[str, str]:
    value = value.upper().replace("/", "")
    match = re.match(r"^(P\d{6})(?:S(\d{3}))?$", value)
    if not match:
        return value, ""
    return match.group(1), match.group(2) or ""


def fetch_pma(pma_or_supplement: str) -> dict[str, Any] | None:
    pma_number, supplement = split_pma_number(pma_or_supplement)
    rows = openfda_search(OPENFDA_PMA, f'pma_number:"{pma_number}"', 100)
    if supplement:
        for row in rows:
            if norm(row.get("supplement_number")).upper() == f"S{supplement}":
                return row
        return None
    for row in rows:
        if not norm(row.get("supplement_number")):
            return row
    return rows[0] if rows else None


def load_existing_keys() -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for path in (REGISTRATION_EVIDENCE_PATH, MANUAL_EVIDENCE_PATH):
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                product_id = norm(row.get("product_id"))
                registration_no = norm(row.get("registration_no")).upper().replace("/", "")
                if product_id and registration_no:
                    keys.add((product_id, registration_no))
    return keys


def queue_rows(limit: int, include_existing_registration: bool) -> list[dict[str, Any]]:
    if not QUEUE_PATH.exists():
        raise SystemExit(f"Missing product gap queue: {QUEUE_PATH}")
    rows: list[dict[str, Any]] = []
    with QUEUE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not include_existing_registration and norm(row.get("registration_rows")) not in {"", "0"}:
                continue
            text = " ".join(
                norm(row.get(field))
                for field in ["lead_registration_url", "lead_spec_url", "lead_official_url", "recommended_next_action"]
            )
            k_numbers = sorted({item.upper() for item in re.findall(r"\bK\d{6}\b", text, flags=re.IGNORECASE)})
            pma_numbers = sorted({item.upper() for item in re.findall(r"\bP\d{6}(?:S\d{3})?\b", text, flags=re.IGNORECASE)})
            if not k_numbers and not pma_numbers:
                continue
            rows.append({**row, "_k_numbers": k_numbers, "_pma_numbers": pma_numbers})
            if limit and len(rows) >= limit:
                break
    return rows


def pdf_url_candidates(k_number: str) -> list[str]:
    k_number = k_number.upper()
    year_digits = k_number[1:3]
    candidates = []
    try:
        year = int(year_digits)
    except ValueError:
        year = -1
    if year == 0:
        candidates.extend(
            [
                f"https://www.accessdata.fda.gov/cdrh_docs/pdf/{k_number}.pdf",
                f"https://www.accessdata.fda.gov/cdrh_docs/pdf0/{k_number}.pdf",
            ]
        )
    elif 0 < year < 10:
        candidates.append(f"https://www.accessdata.fda.gov/cdrh_docs/pdf{year}/{k_number}.pdf")
    elif year >= 10:
        candidates.append(f"https://www.accessdata.fda.gov/cdrh_docs/pdf{year:02d}/{k_number}.pdf")
    candidates.append(f"https://www.accessdata.fda.gov/cdrh_docs/pdf/{k_number}.pdf")
    return list(dict.fromkeys(candidates))


def fetch_url_bytes(url: str, timeout: int = 8) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "GlobalAestheticsDashboard/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type", "")
        payload = response.read()
    if "pdf" not in content_type.lower() and not payload.startswith(b"%PDF"):
        return b""
    return payload


def pdf_text(payload: bytes, max_pages: int = 12) -> str:
    if not payload or fitz is None:
        return ""
    try:
        doc = fitz.open(stream=payload, filetype="pdf")
    except Exception:
        return ""
    chunks: list[str] = []
    try:
        for index, page in enumerate(doc):
            if index >= max_pages:
                break
            chunks.append(page.get_text("text"))
    finally:
        doc.close()
    return "\n".join(chunks)


def clean_indication_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" :-\u2013\u2014\t\r\n")
    text = re.sub(r"\s*(Prescription Use|Over-The-Counter Use|Type of Use).*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*(CONTINUE ON A SEPARATE PAGE|Concurrence of CDRH).*", "", text, flags=re.IGNORECASE)
    text = text.strip(" .:-\u2013\u2014")
    if len(text) > 1400:
        text = text[:1400].rsplit(" ", 1)[0].strip()
    return text


def extract_indication(text: str) -> str:
    if not text:
        return ""
    normalized = re.sub(r"[ \t]+", " ", text)
    normalized = re.sub(r"\n{2,}", "\n", normalized)
    patterns = [
        r"Indications\s+for\s+Use\s*(?:\([^)]*\))?\s*[:\n\- ]+(.{40,1800})",
        r"Indications\s*/\s*Intended\s+Use\s*[:\n\- ]+(.{40,1800})",
        r"Intended\s+Use\s*/\s*Indications\s+for\s+Use\s*[:\n\- ]+(.{40,1800})",
        r"Intended\s+Use\s*[:\n\- ]+(.{40,1800})",
        r"([A-Z0-9®™+\-/ ,()]{1,140}\s+(?:is|are)\s+indicated for .{40,1400})",
        r"([A-Z0-9®™+\-/ ,()]{1,140}\s+(?:is|are)\s+intended for .{40,1400})",
    ]
    for pattern in patterns:
        match = re.search(pattern, normalized, flags=re.IGNORECASE | re.DOTALL)
        if not match:
            continue
        candidate = clean_indication_text(match.group(1))
        if len(candidate) >= 35 and not re.search(r"\bsubstantially equivalent\b", candidate, flags=re.IGNORECASE):
            return candidate
    return ""


def extract_510k_indication(k_number: str) -> tuple[str, str, str]:
    for url in pdf_url_candidates(k_number):
        try:
            payload = fetch_url_bytes(url)
        except Exception:
            continue
        text = pdf_text(payload)
        indication = extract_indication(text)
        if indication:
            return indication, url, text[:900]
    return "", "", ""


def pmn_url(k_number: str) -> str:
    return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={urllib.parse.quote(k_number.upper())}"


def pma_url(pma_number: str) -> str:
    pma_number, supplement = split_pma_number(pma_number)
    suffix = f"S{supplement}" if supplement else ""
    return f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpma/pma.cfm?ID={urllib.parse.quote(pma_number + suffix)}"


def row_company_id(product_id: str) -> str:
    return stable_id("company-from-product", product_id)


def build_510k_row(
    queue_row: dict[str, Any],
    fda_row: dict[str, Any],
    indication: str,
    indication_source_url: str,
    checked_at: str,
) -> dict[str, str]:
    k_number = norm(fda_row.get("k_number")).upper()
    registered_name = norm(fda_row.get("device_name")) or norm(queue_row.get("standard_product_name"))
    decision = norm(fda_row.get("decision_description") or fda_row.get("decision_code"))
    source_url = indication_source_url or pmn_url(k_number)
    excerpt_parts = [
        f"FDA 510(k) {k_number}",
        registered_name,
        norm(fda_row.get("applicant")),
        decision,
        norm(fda_row.get("decision_date")),
    ]
    if indication:
        excerpt_parts.append(indication[:500])
    return {
        "product_id": norm(queue_row.get("product_id")),
        "seed_record_id": norm(queue_row.get("seed_record_id")),
        "company_id": "",
        "company": norm(queue_row.get("company")),
        "brand": norm(queue_row.get("brand")),
        "jurisdiction": "US",
        "regulator": "FDA",
        "regulatory_pathway": "510(k)",
        "status": decision,
        "registration_no": k_number,
        "approval_date": norm(fda_row.get("decision_date")),
        "expiry_date": "",
        "registered_name": registered_name,
        "approved_indication": indication,
        "intended_use": indication,
        "legal_manufacturer": norm(fda_row.get("applicant")),
        "local_holder": "",
        "source_key": "fda_510k_gap_queue_official",
        "source_url": source_url,
        "source_type": "official_fda_document" if indication_source_url else "official_fda_510k_api",
        "evidence_title": f"FDA 510(k) {k_number} - {registered_name}",
        "evidence_excerpt": " | ".join(part for part in excerpt_parts if part),
        "checked_at": checked_at,
        "reviewed_by": "codex_fda_gap_queue_backfill",
        "review_status": "auto_cross_checked",
        "confidence": "official_fda_document_promoted" if indication else "official_regulator_record",
    }


def build_pma_row(queue_row: dict[str, Any], fda_row: dict[str, Any], registration_no: str, checked_at: str) -> dict[str, str]:
    pma_number, supplement = split_pma_number(registration_no)
    full_no = f"{pma_number}/S{supplement}" if supplement else pma_number
    registered_name = norm(fda_row.get("trade_name")) or norm(fda_row.get("generic_name")) or norm(queue_row.get("standard_product_name"))
    indication = clean_indication_text(norm(fda_row.get("ao_statement")))
    pathway = "PMA Supplement" if supplement else "PMA"
    excerpt = " | ".join(
        part
        for part in [
            f"FDA {pathway} {full_no}",
            registered_name,
            norm(fda_row.get("applicant")),
            norm(fda_row.get("decision_code")),
            norm(fda_row.get("decision_date")),
            indication[:500],
        ]
        if part
    )
    return {
        "product_id": norm(queue_row.get("product_id")),
        "seed_record_id": norm(queue_row.get("seed_record_id")),
        "company_id": "",
        "company": norm(queue_row.get("company")),
        "brand": norm(queue_row.get("brand")),
        "jurisdiction": "US",
        "regulator": "FDA",
        "regulatory_pathway": pathway,
        "status": norm(fda_row.get("decision_code")) or "FDA PMA record",
        "registration_no": full_no,
        "approval_date": norm(fda_row.get("decision_date")),
        "expiry_date": "",
        "registered_name": registered_name,
        "approved_indication": indication,
        "intended_use": indication,
        "legal_manufacturer": norm(fda_row.get("applicant")),
        "local_holder": "",
        "source_key": "fda_pma_gap_queue_official",
        "source_url": pma_url(registration_no),
        "source_type": "official_fda_pma",
        "evidence_title": f"FDA {pathway} {full_no} - {registered_name}",
        "evidence_excerpt": excerpt,
        "checked_at": checked_at,
        "reviewed_by": "codex_fda_gap_queue_backfill",
        "review_status": "auto_cross_checked",
        "confidence": "official_regulator_record" if indication else "official_regulator_record_pending_indication",
    }


def append_manual_rows(rows: list[dict[str, str]]) -> int:
    if not rows:
        return 0
    exists = MANUAL_EVIDENCE_PATH.exists()
    with MANUAL_EVIDENCE_PATH.open("a", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANUAL_FIELDS)
        if not exists or MANUAL_EVIDENCE_PATH.stat().st_size == 0:
            writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in MANUAL_FIELDS})
    return len(rows)


def write_report(batch_id: str, rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    path = AUDITS_DIR / f"fda_gap_queue_backfill_{batch_id}.csv"
    fieldnames = [
        "status",
        "company",
        "brand",
        "product",
        "product_id",
        "track",
        "registration_no",
        "pathway",
        "approval_date",
        "registered_name",
        "indication_captured",
        "source_url",
        "note",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    latest = AUDITS_DIR / "fda_gap_queue_backfill_latest.csv"
    latest.write_text(path.read_text(encoding="utf-8-sig"), encoding="utf-8-sig")
    summary_path = AUDITS_DIR / f"fda_gap_queue_backfill_{batch_id}.json"
    summary["report_csv"] = str(path)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (AUDITS_DIR / "fda_gap_queue_backfill_latest.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(path)


def collect(args: argparse.Namespace) -> dict[str, Any]:
    selected = queue_rows(args.limit, args.include_existing_registration)
    existing = load_existing_keys()
    checked_at = datetime.now().astimezone().isoformat(timespec="seconds")
    appended_rows: list[dict[str, str]] = []
    report_rows: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    seen_in_run: set[tuple[str, str]] = set()

    for queue_row in selected:
        product_id = norm(queue_row.get("product_id"))
        for k_number in queue_row.get("_k_numbers") or []:
            key = (product_id, k_number.upper())
            if key in existing or key in seen_in_run:
                counters["skipped_existing"] += 1
                continue
            fda_row = fetch_510k(k_number)
            if not fda_row:
                counters["missing_openfda_510k"] += 1
                report_rows.append(
                    {
                        "status": "missing_openfda",
                        "company": queue_row.get("company"),
                        "brand": queue_row.get("brand"),
                        "product": queue_row.get("standard_product_name"),
                        "product_id": product_id,
                        "track": queue_row.get("track"),
                        "registration_no": k_number,
                        "pathway": "510(k)",
                        "approval_date": "",
                        "registered_name": "",
                        "indication_captured": "no",
                        "source_url": "",
                        "note": "K number found in queue but not returned by openFDA 510(k).",
                    }
                )
                continue
            indication = ""
            pdf_url = ""
            pdf_excerpt = ""
            if not args.skip_pdf:
                indication, pdf_url, pdf_excerpt = extract_510k_indication(k_number)
                if pdf_url:
                    counters["pdf_found"] += 1
                if indication:
                    counters["indication_captured"] += 1
            row = build_510k_row(queue_row, fda_row, indication, pdf_url, checked_at)
            appended_rows.append(row)
            seen_in_run.add(key)
            counters["promoted_510k"] += 1
            report_rows.append(
                {
                    "status": "promoted",
                    "company": row["company"],
                    "brand": row["brand"],
                    "product": queue_row.get("standard_product_name"),
                    "product_id": product_id,
                    "track": queue_row.get("track"),
                    "registration_no": row["registration_no"],
                    "pathway": row["regulatory_pathway"],
                    "approval_date": row["approval_date"],
                    "registered_name": row["registered_name"],
                    "indication_captured": "yes" if indication else "no",
                    "source_url": row["source_url"],
                    "note": pdf_excerpt[:280] if indication else "Official openFDA 510(k) record promoted; PDF indication not captured.",
                }
            )
            if args.sleep:
                time.sleep(args.sleep)

        for pma_number in queue_row.get("_pma_numbers") or []:
            normalized = pma_number.upper().replace("/", "")
            key = (product_id, normalized)
            if key in existing or key in seen_in_run:
                counters["skipped_existing"] += 1
                continue
            fda_row = fetch_pma(pma_number)
            if not fda_row:
                counters["missing_openfda_pma"] += 1
                report_rows.append(
                    {
                        "status": "missing_openfda",
                        "company": queue_row.get("company"),
                        "brand": queue_row.get("brand"),
                        "product": queue_row.get("standard_product_name"),
                        "product_id": product_id,
                        "track": queue_row.get("track"),
                        "registration_no": pma_number,
                        "pathway": "PMA",
                        "approval_date": "",
                        "registered_name": "",
                        "indication_captured": "no",
                        "source_url": "",
                        "note": "PMA number found in queue but not returned by openFDA PMA.",
                    }
                )
                continue
            row = build_pma_row(queue_row, fda_row, pma_number, checked_at)
            appended_rows.append(row)
            seen_in_run.add(key)
            counters["promoted_pma"] += 1
            if row["intended_use"]:
                counters["indication_captured"] += 1
            report_rows.append(
                {
                    "status": "promoted",
                    "company": row["company"],
                    "brand": row["brand"],
                    "product": queue_row.get("standard_product_name"),
                    "product_id": product_id,
                    "track": queue_row.get("track"),
                    "registration_no": row["registration_no"],
                    "pathway": row["regulatory_pathway"],
                    "approval_date": row["approval_date"],
                    "registered_name": row["registered_name"],
                    "indication_captured": "yes" if row["intended_use"] else "no",
                    "source_url": row["source_url"],
                    "note": row["intended_use"][:280],
                }
            )
            if args.sleep:
                time.sleep(args.sleep)

    appended = 0 if args.dry_run else append_manual_rows(appended_rows)
    counters["manual_rows_appended"] = appended
    counters["queue_rows_selected"] = len(selected)
    counters["candidate_identifiers"] = sum(len(row.get("_k_numbers") or []) + len(row.get("_pma_numbers") or []) for row in selected)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = write_report(batch_id, report_rows, dict(counters))
    return {**dict(counters), "report_csv": report_path}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Queue rows to scan. 0 means all.")
    parser.add_argument("--include-existing-registration", action="store_true")
    parser.add_argument("--skip-pdf", action="store_true")
    parser.add_argument("--sleep", type=float, default=0.04)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(collect(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
