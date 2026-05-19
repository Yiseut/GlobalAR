#!/usr/bin/env python3
"""Collect company official-source candidates through agent-reach/Exa.

Rows collected here are evidence candidates. Official company pages can support
commercial product facts, while media/database hits remain cross-check leads.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from build_data import (
    COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH,
    COMPANY_OFFICIAL_SOURCE_PLAN_PATH,
    stable_id,
)


BAD_SOURCE_DOMAINS = {
    "wikipedia.org",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "bloomberg.com",
    "reuters.com",
    "marketscreener.com",
    "pitchbook.com",
    "crunchbase.com",
    "owler.com",
    "zoominfo.com",
    "dnb.com",
    "globaldata.com",
}

GENERIC_TOKENS = {
    "inc",
    "ltd",
    "llc",
    "corp",
    "corporation",
    "company",
    "group",
    "medical",
    "med",
    "aesthetic",
    "aesthetics",
    "technologies",
    "technology",
    "laboratories",
    "pharma",
    "pharmaceutical",
    "co",
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def company_tokens(company: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", company.lower())
    return [token for token in tokens if len(token) >= 4 and token not in GENERIC_TOKENS]


def registered_domain(url: str) -> str:
    host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


SPECIAL_COMPANY_OFFICIAL_DOMAINS = {
    "skin tech": {
        "skintechpharmagroup.com",
        "skintechcorporation.com",
        "skintechpharmagroup.nl",
        "skintechpharmagroup.bg",
        "skintech.info",
    },
}

SPECIAL_COMPANY_FALSE_POSITIVE_DOMAINS = {
    "skin tech": {
        "skinpen.com",
        "skinpenuk.com",
        "skintech.co.za",
        "skinsolutions.co.uk",
    },
}


def domain_matches(domain: str, target: str) -> bool:
    domain = registered_domain(domain) if "://" in domain else domain.lower().removeprefix("www.")
    target = target.lower().removeprefix("www.")
    return bool(domain and target and (domain == target or domain.endswith("." + target)))


def is_bad_domain(domain: str) -> bool:
    return any(domain == bad or domain.endswith("." + bad) for bad in BAD_SOURCE_DOMAINS)


PRODUCT_LEVEL_QUERY_TYPES = {
    "product_official_page",
    "product_ifu_labeling",
    "product_certificate_registration",
}


def official_candidate(row: dict[str, Any], title: str, url: str, excerpt: str = "") -> tuple[str, str]:
    domain = registered_domain(url)
    company = norm(row.get("company"))
    company_key = company.lower()
    tokens = company_tokens(company)
    brand_tokens = company_tokens(norm(row.get("brand")))
    family_tokens = company_tokens(norm(row.get("product_family")))
    haystack = f"{title} {url} {domain} {excerpt}".lower()
    if is_bad_domain(domain):
        return "no", "secondary_source_crosscheck"
    if any(domain_matches(domain, bad) for bad in SPECIAL_COMPANY_FALSE_POSITIVE_DOMAINS.get(company_key, set())):
        return "no", "similar_name_domain_rejected"
    if any(domain_matches(domain, official) for official in SPECIAL_COMPANY_OFFICIAL_DOMAINS.get(company_key, set())):
        return "likely", "official_domain_candidate"
    compact_domain = domain.replace("-", "")
    if any(token in compact_domain for token in tokens):
        return "likely", "official_domain_candidate"
    if row.get("query_type") in PRODUCT_LEVEL_QUERY_TYPES:
        if any(token in compact_domain for token in brand_tokens + family_tokens):
            return "likely", "product_official_domain_candidate"
        if any(token in haystack for token in family_tokens) and any(
            word in haystack
            for word in ["official", "product", "ifu", "instructions for use", "certificate", "declaration", "registration"]
        ):
            return "possible", "product_official_search_candidate"
        if any(token in haystack for token in brand_tokens) and any(word in haystack for word in ["official", "product", "ifu"]):
            return "possible", "brand_official_search_candidate"
    if any(token in haystack for token in tokens) and any(word in haystack for word in ["official", "product", "investor", "annual", "ifu", "catalog"]):
        return "possible", "company_official_search_candidate"
    return "unknown", "secondary_source_crosscheck"


def run_exa(query: str, num_results: int, timeout: int) -> str:
    node = Path(r"E:\shared\tools\nodejs\node.exe")
    mcporter_cli = Path(r"E:\shared\tools\npm-global\node_modules\mcporter\dist\cli.js")
    if node.exists() and mcporter_cli.exists():
        command = [str(node), str(mcporter_cli)]
    else:
        command = [shutil.which("mcporter") or shutil.which("mcporter.cmd") or "mcporter"]
    proc = subprocess.run(
        [
            *command,
            "call",
            "exa.web_search_exa",
            f"query={query}",
            f"numResults={num_results}",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip()
        raise RuntimeError(detail or f"mcporter exited with {proc.returncode}")
    return proc.stdout


def parse_exa_output(raw: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for block in re.split(r"\n---+\n", raw):
        block = block.strip()
        if not block:
            continue
        item: dict[str, str] = {"raw": block}
        lines = block.splitlines()
        highlight_lines: list[str] = []
        in_highlights = False
        for line in lines:
            if line.startswith("Title:"):
                item["title"] = line.removeprefix("Title:").strip()
            elif line.startswith("URL:"):
                item["url"] = line.removeprefix("URL:").strip()
            elif line.startswith("Published:"):
                item["published"] = line.removeprefix("Published:").strip()
            elif line.startswith("Highlights:"):
                in_highlights = True
            elif in_highlights:
                highlight_lines.append(line.strip())
        item["excerpt"] = " ".join(part for part in highlight_lines if part)[:1500]
        if item.get("url"):
            results.append(item)
    return results


def load_plan() -> list[dict[str, str]]:
    if not COMPANY_OFFICIAL_SOURCE_PLAN_PATH.exists():
        raise SystemExit(f"Missing plan: {COMPANY_OFFICIAL_SOURCE_PLAN_PATH}. Run build_official_source_plans.py first.")
    with COMPANY_OFFICIAL_SOURCE_PLAN_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: (int(row.get("priority") or 99), int(row.get("priority_rank") or 999999), row.get("company") or ""))
    return rows


def existing_key(row: dict[str, Any]) -> tuple[str, str]:
    plan_key = norm(row.get("plan_id")) or "|".join([norm(row.get("company_id")), norm(row.get("query_type"))])
    return (plan_key, norm(row.get("url")))


def load_existing() -> dict[tuple[str, str], dict[str, Any]]:
    records: dict[tuple[str, str], dict[str, Any]] = {}
    if not COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH.exists():
        return records
    for line in COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = existing_key(row)
        if all(key):
            records[key] = row
    return records


def write_records(records: dict[tuple[str, str], dict[str, Any]]) -> None:
    COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        records.values(),
        key=lambda row: (
            row.get("company") or "",
            row.get("product_family") or "",
            row.get("query_type") or "",
            row.get("url") or "",
        ),
    )
    with COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH.open("w", encoding="utf-8") as handle:
        for row in ordered:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def collect(limit: int, num_results: int, sleep_seconds: float, timeout: int, force: bool) -> dict[str, Any]:
    plan = load_plan()
    records = load_existing()
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    queried = 0
    added = 0
    errors: list[dict[str, str]] = []
    for row in plan:
        if limit and queried >= limit:
            break
        key_prefix = norm(row.get("plan_id")) or "|".join([norm(row.get("company_id")), norm(row.get("query_type"))])
        if not force and any(key[0] == key_prefix for key in records):
            continue
        queried += 1
        try:
            raw = run_exa(norm(row.get("query")), num_results, timeout)
            results = parse_exa_output(raw)
        except Exception as exc:  # noqa: BLE001 - one failed query should not stop the batch.
            errors.append({"company": norm(row.get("company")), "query_type": norm(row.get("query_type")), "error": str(exc)[:500]})
            continue
        for result in results:
            candidate, confidence = official_candidate(row, result.get("title", ""), result.get("url", ""), result.get("excerpt", ""))
            record = {
                "evidence_id": stable_id("coev", row.get("plan_id") or row.get("company_id"), row.get("query_type"), result.get("url")),
                "plan_id": norm(row.get("plan_id")),
                "company_id": norm(row.get("company_id")),
                "company": norm(row.get("company")),
                "product_family_id": norm(row.get("product_family_id")),
                "brand": norm(row.get("brand")),
                "product_family": norm(row.get("product_family")),
                "category_l1": norm(row.get("category_l1")),
                "category_l2": norm(row.get("category_l2")),
                "tech_type": norm(row.get("tech_type")),
                "query_type": norm(row.get("query_type")),
                "query": norm(row.get("query")),
                "expected_source": norm(row.get("expected_source")),
                "title": norm(result.get("title")),
                "url": norm(result.get("url")),
                "published": norm(result.get("published")),
                "captured_at": captured_at,
                "source_key": "exa_web_search_official_candidate",
                "source_lane": "company_official",
                "confidence": confidence,
                "official_candidate": candidate,
                "evidence_excerpt": norm(result.get("excerpt")),
                "raw_text": norm(result.get("raw"))[:3000],
                "crosscheck_status": "candidate",
            }
            key = existing_key(record)
            if key not in records:
                added += 1
            records[key] = record
        if sleep_seconds:
            time.sleep(sleep_seconds)
    write_records(records)
    return {
        "plan_rows": len(plan),
        "queries_run": queried,
        "records_total": len(records),
        "records_added": added,
        "errors": len(errors),
        "error_samples": errors[:5],
        "path": str(COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=40, help="Number of plan rows to query. 0 means all pending rows.")
    parser.add_argument("--num-results", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--force", action="store_true", help="Re-query rows that already have evidence.")
    args = parser.parse_args()
    result = collect(args.limit, args.num_results, args.sleep, args.timeout, args.force)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(text)
    except UnicodeEncodeError:
        print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
