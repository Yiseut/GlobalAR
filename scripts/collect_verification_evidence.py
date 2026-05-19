#!/usr/bin/env python3
"""Collect review-stage official evidence for the global aesthetics dashboard.

The collector never edits the source workbook. It appends official-source hits
to the staging JSONL file and mirrors them into SQLite tables for the review UI.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from build_data import DB_PATH, STAGING_JSONL_PATH, stable_id


OPENFDA_510K = "https://api.fda.gov/device/510k.json"
OPENFDA_SOURCE_KEY = "fda_openfda_510k"
GENERIC_PRODUCT_TERMS = {
    "device",
    "system",
    "laser",
    "platform",
    "applicator",
    "handpiece",
    "filler",
    "gel",
    "cream",
    "serum",
    "mask",
    "kit",
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def load_existing_jsonl() -> dict[tuple[str, str, str], dict[str, Any]]:
    records: dict[tuple[str, str, str], dict[str, Any]] = {}
    if not STAGING_JSONL_PATH.exists():
        return records
    for line in STAGING_JSONL_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (item.get("source_key") or "", item.get("source_record_id") or "", item.get("company_id") or "")
        records[key] = item
    return records


def save_jsonl(records: dict[tuple[str, str, str], dict[str, Any]]) -> None:
    STAGING_JSONL_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in records.values()]
    STAGING_JSONL_PATH.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def fetch_json(url: str, timeout: int = 25) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "GlobalAestheticsVerification/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def openfda_search(field: str, term: str, limit: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"search": f'{field}:"{term}"', "limit": str(limit)})
    url = f"{OPENFDA_510K}?{query}"
    try:
        payload = fetch_json(url)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return []
        raise
    return payload.get("results", [])


def clean_search_term(value: Any) -> str:
    text = norm(value)
    if not text:
        return ""
    text = text.replace("®", "").replace("™", "")
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"\([^A-Za-z0-9][^)]*\)", " ", text)
    text = re.sub(r"[^A-Za-z0-9 ._+/-]+", " ", text)
    text = " ".join(text.split())
    if len(text) < 4:
        return ""
    if text.lower() in GENERIC_PRODUCT_TERMS:
        return ""
    return text


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
    terms: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for value in [row["brand"], row["standard_product_name"], row["core_product"]]:
            term = clean_search_term(value)
            key = term.lower()
            if term and key not in seen:
                seen.add(key)
                terms.append(term)
            if len(terms) >= limit:
                return terms
    return terms


def product_match(conn: sqlite3.Connection, company_id: str, result: dict[str, Any], query_term: str = "") -> dict[str, str]:
    device_name = norm(result.get("device_name")).lower()
    rows = conn.execute(
        """
        SELECT product_id, brand, standard_product_name, core_product, search_blob
        FROM product_master
        WHERE company_id = ?
        """,
        (company_id,),
    ).fetchall()
    for row in rows:
        candidates = [row["brand"], row["standard_product_name"], row["core_product"]]
        for candidate in candidates:
            candidate_text = clean_search_term(candidate)
            if candidate_text and candidate_text.lower() in device_name:
                return {
                    "product_id": row["product_id"],
                    "brand": row["brand"] or row["standard_product_name"] or "",
                    "match_reason": "device_name_contains_seed_product",
                    "matched_text": candidate_text,
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
    applicant = norm(result.get("applicant")).lower()
    if not applicant:
        return False
    candidates = [company["canonical_name"], *aliases]
    return any(clean_search_term(candidate).lower() in applicant for candidate in candidates if clean_search_term(candidate))


def confidence_for(applicant_match: bool, product_match_reason: str) -> str:
    if applicant_match and product_match_reason != "no_seed_product_match":
        return "official_api_applicant_and_product_match_unreviewed"
    if applicant_match:
        return "official_api_applicant_match_unreviewed"
    if product_match_reason != "no_seed_product_match":
        return "official_api_product_name_candidate_unreviewed"
    return "official_api_unreviewed"


def make_stage_record(
    conn: sqlite3.Connection,
    company: sqlite3.Row,
    result: dict[str, Any],
    captured_at: str,
    aliases: list[str],
    query_mode: str,
    query_term: str,
) -> dict[str, Any]:
    k_number = norm(result.get("k_number"))
    matched = product_match(conn, company["company_id"], result, query_term)
    applicant_match = applicant_matches(company, result, aliases)
    detail_url = f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={urllib.parse.quote(k_number)}" if k_number else ""
    field_candidates = {
        "registration_no": k_number,
        "registered_name": norm(result.get("device_name")),
        "status": norm(result.get("decision_description") or result.get("decision_code")),
        "approval_date": norm(result.get("decision_date")),
        "legal_manufacturer": norm(result.get("applicant")),
        "regulatory_pathway": "510(k)",
        "product_code": norm(result.get("product_code")),
        "device_class": norm((result.get("openfda") or {}).get("device_class")),
        "approved_indication": "",
        "intended_use": "",
        "query_mode": query_mode,
        "query_term": query_term,
        "applicant_match": "yes" if applicant_match else "no",
        "match_reason": matched["match_reason"],
        "matched_text": matched["matched_text"],
    }
    title = " · ".join(x for x in [k_number, field_candidates["registered_name"]] if x)
    excerpt = (
        f"{field_candidates['legal_manufacturer']} | {field_candidates['registered_name']} | "
        f"{field_candidates['status']} | {field_candidates['approval_date']}"
    )
    return {
        "source_key": OPENFDA_SOURCE_KEY,
        "source_lane": "regulatory",
        "company_id": company["company_id"],
        "product_id": matched["product_id"],
        "company": company["canonical_name"],
        "brand": matched["brand"],
        "jurisdiction": "US",
        "evidence_type": "510k_clearance",
        "title": title,
        "url": detail_url,
        "source_record_id": k_number,
        "captured_at": captured_at,
        "field_candidates": field_candidates,
        "excerpt": excerpt,
        "raw_json": result,
        "review_status": "needs_review",
        "confidence": confidence_for(applicant_match, matched["match_reason"]),
        "merge_target": "registration_evidence",
        "merge_status": "staged_only",
    }


def merge_existing_record(existing: dict[str, Any], candidate: dict[str, Any]) -> bool:
    changed = False
    existing_fields = existing.setdefault("field_candidates", {})
    for field in ["query_mode", "query_term", "applicant_match", "match_reason", "matched_text"]:
        if not existing_fields.get(field) and candidate.get("field_candidates", {}).get(field):
            existing_fields[field] = candidate["field_candidates"][field]
            changed = True
    if not existing.get("product_id") and candidate.get("product_id"):
        existing["product_id"] = candidate["product_id"]
        changed = True
    if not existing.get("brand") and candidate.get("brand"):
        existing["brand"] = candidate["brand"]
        changed = True
    if existing.get("confidence") == "official_api_unreviewed" and candidate.get("confidence") != "official_api_unreviewed":
        existing["confidence"] = candidate["confidence"]
        changed = True
    return changed


def insert_stage(conn: sqlite3.Connection, item: dict[str, Any]) -> None:
    fields = [
        "source_key",
        "source_lane",
        "company_id",
        "product_id",
        "company",
        "brand",
        "jurisdiction",
        "evidence_type",
        "title",
        "url",
        "source_record_id",
        "captured_at",
        "field_candidates",
        "excerpt",
        "raw_json",
        "review_status",
        "confidence",
        "merge_target",
        "merge_status",
    ]
    values = []
    for field in fields:
        value = item.get(field)
        if field in {"field_candidates", "raw_json"}:
            value = json.dumps(value or {}, ensure_ascii=False)
        values.append(value)
    conn.execute(
        f"INSERT INTO evidence_staging ({','.join(fields)}) VALUES ({','.join(['?'] * len(fields))})",
        values,
    )
    candidates = item["field_candidates"]
    conn.execute(
        """
        INSERT INTO registration_evidence
        (product_id, seed_record_id, company_id, company, brand, jurisdiction, regulator,
         regulatory_pathway, status, registration_no, approval_date, expiry_date, registered_name,
         approved_indication, intended_use, legal_manufacturer, local_holder, source_key, source_url,
         source_type, evidence_title, evidence_excerpt, checked_at, reviewed_by, review_status, confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item.get("product_id"),
            "",
            item.get("company_id"),
            item.get("company"),
            item.get("brand"),
            "US",
            "FDA",
            candidates.get("regulatory_pathway"),
            candidates.get("status"),
            candidates.get("registration_no"),
            candidates.get("approval_date"),
            "",
            candidates.get("registered_name"),
            candidates.get("approved_indication"),
            candidates.get("intended_use"),
            candidates.get("legal_manufacturer"),
            "",
            item.get("source_key"),
            item.get("url"),
            "official_api",
            item.get("title"),
            item.get("excerpt"),
            item.get("captured_at"),
            "",
            "needs_review",
            item.get("confidence"),
        ),
    )


def collect(
    limit_companies: int,
    per_alias_limit: int,
    product_term_limit: int,
    sleep_seconds: float,
    start_rank: int,
    skip_existing_companies: bool,
) -> dict[str, Any]:
    conn = connect()
    existing = load_existing_jsonl()
    existing_company_ids = {
        company_id
        for source_key, _record_id, company_id in existing
        if source_key == OPENFDA_SOURCE_KEY and company_id
    }
    companies = conn.execute(
        """
        SELECT company_id, canonical_name, aliases, priority_rank
        FROM company_master
        WHERE priority_rank IS NOT NULL
          AND priority_rank >= ?
        ORDER BY priority_rank
        LIMIT ?
        """,
        (start_rank, limit_companies),
    ).fetchall()
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    inserted = 0
    updated = 0
    queried = 0
    errors: list[dict[str, str]] = []
    for company in companies:
        if skip_existing_companies and company["company_id"] in existing_company_ids:
            continue
        aliases = json.loads(company["aliases"] or "[]")
        aliases = [company["canonical_name"], *aliases]
        queries: list[tuple[str, str, str]] = []
        seen_aliases: set[str] = set()
        for alias in aliases[:4]:
            alias = norm(alias)
            if not alias or alias.lower() in seen_aliases:
                continue
            seen_aliases.add(alias.lower())
            queries.append(("applicant", alias, "applicant_alias"))
        for term in product_terms(conn, company["company_id"], product_term_limit):
            queries.append(("device_name", term, "product_or_brand"))
        seen_queries: set[tuple[str, str]] = set()
        for field, term, query_mode in queries:
            query_key = (field, term.lower())
            if query_key in seen_queries:
                continue
            seen_queries.add(query_key)
            queried += 1
            try:
                results = openfda_search(field, term, per_alias_limit)
            except Exception as exc:  # noqa: BLE001 - keep collector resilient.
                errors.append({"company": company["canonical_name"], "query": f"{field}:{term}", "error": str(exc)})
                continue
            for result in results:
                item = make_stage_record(conn, company, result, captured_at, aliases, query_mode, term)
                if not item["source_record_id"]:
                    continue
                key = (item["source_key"], item["source_record_id"], item["company_id"])
                if key in existing:
                    if merge_existing_record(existing[key], item):
                        updated += 1
                    continue
                existing[key] = item
                insert_stage(conn, item)
                inserted += 1
            if sleep_seconds:
                time.sleep(sleep_seconds)
    for company in companies:
        count = conn.execute(
            "SELECT COUNT(*) FROM evidence_staging WHERE company_id = ? AND source_key = ?",
            (company["company_id"], OPENFDA_SOURCE_KEY),
        ).fetchone()[0]
        conn.execute(
            """
            UPDATE verification_queue
            SET evidence_count = ?, status = CASE WHEN ? > 0 THEN 'evidence_staged' ELSE status END
            WHERE company_id = ? AND fact_group = 'registration_us'
            """,
            (count, count, company["company_id"]),
        )
    conn.commit()
    conn.close()
    save_jsonl(existing)
    return {
        "companies": len(companies),
        "start_rank": start_rank,
        "skip_existing_companies": skip_existing_companies,
        "queries": queried,
        "inserted": inserted,
        "updated": updated,
        "jsonl_path": str(STAGING_JSONL_PATH),
        "errors": errors[:10],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--companies", type=int, default=5, help="Number of priority companies to query.")
    parser.add_argument("--per-alias-limit", type=int, default=5, help="Maximum openFDA rows per alias.")
    parser.add_argument("--product-terms", type=int, default=4, help="Product/brand terms to query per company.")
    parser.add_argument("--sleep", type=float, default=0.15, help="Delay between API calls.")
    parser.add_argument("--start-rank", type=int, default=1, help="Start from this company priority_rank.")
    parser.add_argument("--skip-existing-companies", action="store_true", help="Skip companies that already have openFDA staging rows.")
    args = parser.parse_args()
    if not DB_PATH.exists():
        raise SystemExit(f"Database not found: {DB_PATH}. Run scripts/build_data.py first.")
    result = collect(
        args.companies,
        args.per_alias_limit,
        args.product_terms,
        args.sleep,
        args.start_rank,
        args.skip_existing_companies,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
