#!/usr/bin/env python3
"""Append-only openFDA 510(k) evidence collector.

This FDA-only collector is intentionally narrower than
collect_verification_evidence.py: it reads the dashboard SQLite database and
the existing staging JSONL, queries the official openFDA 510(k) API for missing
priority companies, appends only new FDA JSONL records, and writes timestamped
FDA reports. It does not write SQLite, rebuild the total database, or touch the
source Excel workbook.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "global_aesthetics.db"
STAGING_PATH = DATA_DIR / "verification_evidence_staging.jsonl"
OPENFDA_510K = "https://api.fda.gov/device/510k.json"
SOURCE_KEY = "fda_openfda_510k"
GENERIC_TERMS = {
    "aesthetic",
    "applicator",
    "body",
    "cannula",
    "cream",
    "device",
    "filler",
    "gel",
    "handpiece",
    "kit",
    "laser",
    "mask",
    "medical",
    "needle",
    "platform",
    "serum",
    "skin",
    "system",
    "tip",
}
CORPORATE_SUFFIX_RE = re.compile(
    r"\b(inc|incorporated|ltd|limited|llc|corp|corporation|co|company|plc|ag|sa|sas|spa|srl|gmbh|ab|bv|nv|pte|kk|co ltd)\b",
    re.IGNORECASE,
)


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def clean_search_term(value: Any) -> str:
    text = norm(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^A-Za-z0-9 ._+/-]+", " ", text)
    text = " ".join(text.split())
    if len(text) < 3:
        return ""
    if text.lower() in GENERIC_TERMS:
        return ""
    return text


def compact_company_token(value: str) -> str:
    text = clean_search_term(value).lower()
    text = CORPORATE_SUFFIX_RE.sub(" ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def stable_id(*parts: Any) -> str:
    import hashlib

    raw = "|".join(norm(part).lower() for part in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def connect_readonly() -> sqlite3.Connection:
    uri = f"file:{DB_PATH.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_existing_fda_keys() -> tuple[set[tuple[str, str, str]], Counter[str], Counter[str]]:
    keys: set[tuple[str, str, str]] = set()
    companies: Counter[str] = Counter()
    confidence: Counter[str] = Counter()
    if not STAGING_PATH.exists():
        return keys, companies, confidence
    with STAGING_PATH.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if item.get("source_key") != SOURCE_KEY:
                continue
            key = (SOURCE_KEY, norm(item.get("source_record_id")), norm(item.get("company_id")))
            keys.add(key)
            if item.get("company_id"):
                companies[norm(item.get("company_id"))] += 1
            confidence[norm(item.get("confidence")) or "unknown"] += 1
    return keys, companies, confidence


def fetch_openfda(
    field: str,
    term: str,
    limit: int,
    timeout: int = 25,
    retries: int = 2,
    retry_sleep: float = 0.8,
) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"search": f'{field}:"{term}"', "limit": str(limit)})
    request = urllib.request.Request(
        f"{OPENFDA_510K}?{query}",
        headers={"User-Agent": "GlobalAestheticsFDAIncremental/0.1"},
    )
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload.get("results", [])
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return []
            if exc.code in {502, 503, 504} and attempt < retries:
                time.sleep(retry_sleep * (attempt + 1))
                continue
            raise
    return []


def company_aliases(company: sqlite3.Row) -> list[str]:
    aliases: list[str] = []
    try:
        aliases = json.loads(company["aliases"] or "[]")
    except json.JSONDecodeError:
        aliases = []
    candidates = [company["canonical_name"], *aliases]
    seen: set[str] = set()
    terms: list[str] = []
    for candidate in candidates:
        term = clean_search_term(candidate)
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            terms.append(term)
    return terms


def product_terms(conn: sqlite3.Connection, company_id: str, limit: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT brand, standard_product_name, core_product
        FROM product_master
        WHERE company_id = ?
        ORDER BY review_status DESC, standard_product_name
        """,
        (company_id,),
    ).fetchall()
    seen: set[str] = set()
    terms: list[str] = []
    for row in rows:
        for value in [row["brand"], row["standard_product_name"], row["core_product"]]:
            term = clean_search_term(value)
            key = term.lower()
            if not term or len(term) < 4 or key in seen:
                continue
            seen.add(key)
            terms.append(term)
            if len(terms) >= limit:
                return terms
    return terms


def product_match(conn: sqlite3.Connection, company_id: str, result: dict[str, Any], query_term: str) -> dict[str, str]:
    device_name = norm(result.get("device_name")).lower()
    rows = conn.execute(
        """
        SELECT product_id, brand, standard_product_name, core_product
        FROM product_master
        WHERE company_id = ?
        """,
        (company_id,),
    ).fetchall()
    for row in rows:
        for value in [row["brand"], row["standard_product_name"], row["core_product"]]:
            term = clean_search_term(value)
            if term and term.lower() in device_name:
                return {
                    "product_id": norm(row["product_id"]),
                    "brand": norm(row["brand"] or row["standard_product_name"]),
                    "match_reason": "device_name_contains_seed_product",
                    "matched_text": term,
                }
    if query_term and clean_search_term(query_term).lower() in device_name:
        return {
            "product_id": "",
            "brand": query_term,
            "match_reason": "device_name_contains_query_term",
            "matched_text": query_term,
        }
    return {"product_id": "", "brand": "", "match_reason": "no_seed_product_match", "matched_text": ""}


def applicant_matches(company: sqlite3.Row, result: dict[str, Any], aliases: list[str]) -> bool:
    applicant = compact_company_token(norm(result.get("applicant")))
    if not applicant:
        return False
    tokens = [compact_company_token(company["canonical_name"]), *(compact_company_token(alias) for alias in aliases)]
    return any(token and (token in applicant or applicant in token) for token in tokens)


def confidence_for(applicant_match: bool, match_reason: str) -> str:
    if applicant_match and match_reason != "no_seed_product_match":
        return "official_api_applicant_and_product_match_unreviewed"
    if applicant_match:
        return "official_api_applicant_match_unreviewed"
    if match_reason != "no_seed_product_match":
        return "official_api_product_name_candidate_unreviewed"
    return "official_api_unreviewed"


def make_record(
    conn: sqlite3.Connection,
    company: sqlite3.Row,
    result: dict[str, Any],
    aliases: list[str],
    query_mode: str,
    query_term: str,
    captured_at: str,
) -> dict[str, Any]:
    k_number = norm(result.get("k_number"))
    matched = product_match(conn, company["company_id"], result, query_term)
    applicant_match = applicant_matches(company, result, aliases)
    openfda = result.get("openfda") or {}
    fields = {
        "registration_no": k_number,
        "registered_name": norm(result.get("device_name")),
        "status": norm(result.get("decision_description") or result.get("decision_code")),
        "approval_date": norm(result.get("decision_date")),
        "legal_manufacturer": norm(result.get("applicant")),
        "regulatory_pathway": "510(k)",
        "product_code": norm(result.get("product_code")),
        "device_class": norm(openfda.get("device_class")),
        "approved_indication": "",
        "intended_use": "",
        "query_mode": query_mode,
        "query_term": query_term,
        "applicant_match": "yes" if applicant_match else "no",
        "match_reason": matched["match_reason"],
        "matched_text": matched["matched_text"],
    }
    title = " | ".join(part for part in [k_number, fields["registered_name"]] if part)
    excerpt = " | ".join(
        part
        for part in [fields["legal_manufacturer"], fields["registered_name"], fields["status"], fields["approval_date"]]
        if part
    )
    return {
        "source_key": SOURCE_KEY,
        "source_lane": "regulatory",
        "company_id": company["company_id"],
        "product_id": matched["product_id"],
        "company": company["canonical_name"],
        "brand": matched["brand"],
        "jurisdiction": "US",
        "evidence_type": "510k_clearance",
        "title": title,
        "url": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={urllib.parse.quote(k_number)}"
        if k_number
        else "",
        "source_record_id": k_number,
        "captured_at": captured_at,
        "field_candidates": fields,
        "excerpt": excerpt,
        "raw_json": result,
        "review_status": "needs_review",
        "confidence": confidence_for(applicant_match, matched["match_reason"]),
        "merge_target": "registration_evidence",
        "merge_status": "staged_only",
    }


def select_companies(
    conn: sqlite3.Connection,
    max_companies: int,
    start_rank: int,
    existing_companies: Counter[str],
    skip_existing_companies: bool,
) -> list[sqlite3.Row]:
    rows = conn.execute(
        """
        SELECT company_id, canonical_name, aliases, priority_rank
        FROM company_master
        WHERE priority_rank IS NOT NULL
          AND priority_rank >= ?
        ORDER BY priority_rank
        """,
        (start_rank,),
    ).fetchall()
    selected: list[sqlite3.Row] = []
    for row in rows:
        if skip_existing_companies and row["company_id"] in existing_companies:
            continue
        selected.append(row)
        if max_companies and len(selected) >= max_companies:
            break
    return selected


def write_jsonl_append(records: list[dict[str, Any]]) -> int:
    if not records:
        return 0
    # Re-read keys immediately before append so a concurrent FDA writer is less
    # likely to cause duplicate rows. We still never rewrite the full file.
    existing_keys, _, _ = load_existing_fda_keys()
    new_records = [
        record
        for record in records
        if (SOURCE_KEY, norm(record.get("source_record_id")), norm(record.get("company_id"))) not in existing_keys
    ]
    if not new_records:
        return 0
    STAGING_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STAGING_PATH.open("a", encoding="utf-8", newline="\n") as handle:
        for record in new_records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return len(new_records)


def write_reports(
    batch_id: str,
    before_rows: int,
    before_companies: int,
    appended: int,
    selected: list[sqlite3.Row],
    query_log: list[dict[str, Any]],
    new_records: list[dict[str, Any]],
    errors: list[dict[str, str]],
) -> dict[str, str]:
    after_keys, after_company_counts, after_confidence = load_existing_fda_keys()
    coverage_path = DATA_DIR / f"fda_openfda_coverage_{batch_id}.csv"
    report_path = DATA_DIR / f"fda_openfda_incremental_{batch_id}.json"
    hits_by_company = Counter(record["company"] for record in new_records)
    with coverage_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "priority_rank",
                "company_id",
                "company",
                "queried",
                "new_rows",
                "existing_fda_rows_after",
                "query_count",
                "hit_count",
                "notes",
            ],
        )
        writer.writeheader()
        for company in selected:
            logs = [item for item in query_log if item["company_id"] == company["company_id"]]
            hit_count = sum(int(item["result_count"]) for item in logs)
            notes = ""
            if not logs:
                notes = "not_queried"
            elif hits_by_company[company["canonical_name"]] == 0 and hit_count == 0:
                notes = "no_openfda_510k_hits_for_alias_or_seed_product_terms"
            elif hits_by_company[company["canonical_name"]] == 0:
                notes = "api_hits_already_staged_or_missing_k_number"
            writer.writerow(
                {
                    "priority_rank": company["priority_rank"],
                    "company_id": company["company_id"],
                    "company": company["canonical_name"],
                    "queried": "yes" if logs else "no",
                    "new_rows": hits_by_company[company["canonical_name"]],
                    "existing_fda_rows_after": after_company_counts.get(company["company_id"], 0),
                    "query_count": len(logs),
                    "hit_count": hit_count,
                    "notes": notes,
                }
            )
    report = {
        "batch_id": batch_id,
        "source": "openFDA Device 510(k) API",
        "api_url": OPENFDA_510K,
        "staging_path": str(STAGING_PATH),
        "coverage_report_path": str(coverage_path),
        "before": {"fda_rows": before_rows, "covered_companies": before_companies},
        "after": {"fda_rows": len(after_keys), "covered_companies": len(after_company_counts)},
        "delta": {"new_rows_appended": appended, "companies_queried": len(selected)},
        "confidence_after": dict(after_confidence),
        "new_records_top": [
            {
                "company": record.get("company"),
                "k_number": record.get("source_record_id"),
                "registered_name": record.get("field_candidates", {}).get("registered_name"),
                "applicant": record.get("field_candidates", {}).get("legal_manufacturer"),
                "approval_date": record.get("field_candidates", {}).get("approval_date"),
                "confidence": record.get("confidence"),
                "url": record.get("url"),
            }
            for record in new_records[:25]
        ],
        "query_log": query_log,
        "errors": errors,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"coverage_report": str(coverage_path), "json_report": str(report_path)}


def collect(args: argparse.Namespace) -> dict[str, Any]:
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}")
    existing_keys, existing_company_counts, _ = load_existing_fda_keys()
    before_rows = len(existing_keys)
    before_companies = len(existing_company_counts)
    conn = connect_readonly()
    selected = select_companies(
        conn,
        args.companies,
        args.start_rank,
        existing_company_counts,
        args.skip_existing_companies,
    )
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    candidates: list[dict[str, Any]] = []
    query_log: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    seen_candidate_keys = set(existing_keys)
    for company in selected:
        aliases = company_aliases(company)[: args.aliases]
        terms = product_terms(conn, company["company_id"], args.product_terms)
        queries: list[tuple[str, str, str]] = [("applicant", alias, "applicant_alias") for alias in aliases]
        queries.extend(("device_name", term, "product_or_brand") for term in terms)
        seen_queries: set[tuple[str, str]] = set()
        for field, term, query_mode in queries:
            query_key = (field, term.lower())
            if query_key in seen_queries:
                continue
            seen_queries.add(query_key)
            try:
                results = fetch_openfda(field, term, args.per_alias_limit, args.timeout, args.retries, args.retry_sleep)
            except Exception as exc:  # noqa: BLE001 - report and continue.
                errors.append(
                    {
                        "company": company["canonical_name"],
                        "field": field,
                        "term": term,
                        "error": str(exc),
                    }
                )
                results = []
            query_log.append(
                {
                    "company_id": company["company_id"],
                    "company": company["canonical_name"],
                    "field": field,
                    "term": term,
                    "query_mode": query_mode,
                    "result_count": len(results),
                }
            )
            for result in results:
                record = make_record(conn, company, result, aliases, query_mode, term, captured_at)
                if not record.get("source_record_id"):
                    continue
                key = (SOURCE_KEY, record["source_record_id"], company["company_id"])
                if key in seen_candidate_keys:
                    continue
                seen_candidate_keys.add(key)
                candidates.append(record)
            if args.sleep:
                time.sleep(args.sleep)
    conn.close()
    appended = 0 if args.dry_run else write_jsonl_append(candidates)
    batch_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_paths = write_reports(
        batch_id=batch_id,
        before_rows=before_rows,
        before_companies=before_companies,
        appended=appended,
        selected=selected,
        query_log=query_log,
        new_records=candidates,
        errors=errors,
    )
    after_keys, after_company_counts, _ = load_existing_fda_keys()
    return {
        "batch_id": batch_id,
        "companies_selected": len(selected),
        "queries": len(query_log),
        "candidate_new_rows": len(candidates),
        "appended_rows": appended,
        "fda_rows_before": before_rows,
        "fda_rows_after": len(after_keys),
        "covered_companies_before": before_companies,
        "covered_companies_after": len(after_company_counts),
        "errors": errors[:10],
        **report_paths,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", type=int, default=10, help="Maximum missing priority companies to query. 0 means all.")
    parser.add_argument("--start-rank", type=int, default=1, help="Start from this company priority_rank.")
    parser.add_argument("--aliases", type=int, default=4, help="Company aliases to query per company.")
    parser.add_argument("--per-alias-limit", type=int, default=3, help="Maximum openFDA rows per query.")
    parser.add_argument("--product-terms", type=int, default=3, help="Seed product/brand terms to query per company.")
    parser.add_argument("--sleep", type=float, default=0.08, help="Delay between openFDA requests.")
    parser.add_argument("--timeout", type=int, default=25, help="HTTP timeout seconds.")
    parser.add_argument("--retries", type=int, default=2, help="Retries for transient openFDA 502/503/504 responses.")
    parser.add_argument("--retry-sleep", type=float, default=0.8, help="Base retry sleep for transient openFDA errors.")
    parser.add_argument("--skip-existing-companies", action="store_true", help="Skip companies already covered by FDA staging.")
    parser.add_argument("--dry-run", action="store_true", help="Query and report without appending staging JSONL.")
    args = parser.parse_args()
    result = collect(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
