#!/usr/bin/env python3
"""Collect MDR/CE evidence candidates from the search plan.

These are search-result candidates only. Official MDR/CE facts still need a
certificate, EUDAMED record, IFU, declaration of conformity, or official product
document before they can be treated as verified registration evidence.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from build_data import DATA_DIR, MDR_CE_SEARCH_PLAN_PATH, stable_id


MDR_CE_EVIDENCE_PATH = DATA_DIR / "mdr_ce_evidence_candidates.jsonl"

SECONDARY_DOMAINS = {
    "wikipedia.org",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "marketscreener.com",
    "pitchbook.com",
    "crunchbase.com",
    "bloomberg.com",
    "reuters.com",
}


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def domain(url: str) -> str:
    host = urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def run_exa(query: str, num_results: int, timeout: int) -> str:
    node = Path(r"E:\shared\tools\nodejs\node.exe")
    mcporter_cli = Path(r"E:\shared\tools\npm-global\node_modules\mcporter\dist\cli.js")
    if node.exists() and mcporter_cli.exists():
        command = [str(node), str(mcporter_cli)]
    else:
        command = [shutil.which("mcporter") or "mcporter"]
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
    rows: list[dict[str, str]] = []
    for block in re.split(r"\n---+\n", raw):
        block = block.strip()
        if not block:
            continue
        item = {"raw": block}
        highlights: list[str] = []
        in_highlights = False
        for line in block.splitlines():
            if line.startswith("Title:"):
                item["title"] = line.removeprefix("Title:").strip()
            elif line.startswith("URL:"):
                item["url"] = line.removeprefix("URL:").strip()
            elif line.startswith("Published:"):
                item["published"] = line.removeprefix("Published:").strip()
            elif line.startswith("Highlights:"):
                in_highlights = True
            elif in_highlights:
                highlights.append(line.strip())
        item["excerpt"] = " ".join(part for part in highlights if part)[:1500]
        if item.get("url"):
            rows.append(item)
    return rows


def confidence_for(source_key: str, url: str, title: str) -> tuple[str, str]:
    host = domain(url)
    text = f"{title} {url}".lower()
    if host.endswith("europa.eu") or "eudamed" in text:
        return "official_regulator_candidate", "yes"
    if any(term in text for term in ["declaration of conformity", "certificate", "ifu", "instructions for use", "mdr", "ce "]):
        if not any(host == bad or host.endswith("." + bad) for bad in SECONDARY_DOMAINS):
            return "official_document_candidate", "likely"
    if any(host == bad or host.endswith("." + bad) for bad in SECONDARY_DOMAINS):
        return "secondary_source_crosscheck", "no"
    if source_key == "company_ce_documents":
        return "company_official_search_candidate", "possible"
    return "search_candidate_unverified", "unknown"


def load_plan() -> list[dict[str, str]]:
    if not MDR_CE_SEARCH_PLAN_PATH.exists():
        raise SystemExit(f"Missing plan: {MDR_CE_SEARCH_PLAN_PATH}. Run build_mdr_ce_plan.py first.")
    with MDR_CE_SEARCH_PLAN_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    rows.sort(key=lambda row: (int(row.get("priority_rank") or 999999), row.get("company") or "", row.get("product_family") or "", row.get("source_key") or ""))
    return rows


def load_existing() -> dict[tuple[str, str], dict[str, Any]]:
    existing: dict[tuple[str, str], dict[str, Any]] = {}
    if not MDR_CE_EVIDENCE_PATH.exists():
        return existing
    for line in MDR_CE_EVIDENCE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (norm(row.get("plan_id")), norm(row.get("url")))
        if all(key):
            existing[key] = row
    return existing


def write_existing(records: dict[tuple[str, str], dict[str, Any]]) -> None:
    MDR_CE_EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted(records.values(), key=lambda row: (row.get("priority_rank") or 999999, row.get("company") or "", row.get("product_family") or ""))
    with MDR_CE_EVIDENCE_PATH.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def collect(limit: int, num_results: int, sleep_seconds: float, timeout: int, force: bool) -> dict[str, Any]:
    plan = load_plan()
    existing = load_existing()
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    queried = 0
    added = 0
    errors: list[dict[str, str]] = []
    for row in plan:
        if limit and queried >= limit:
            break
        if not force and any(key[0] == norm(row.get("plan_id")) for key in existing):
            continue
        queried += 1
        try:
            results = parse_exa_output(run_exa(norm(row.get("query")), num_results, timeout))
        except Exception as exc:  # noqa: BLE001
            errors.append({"plan_id": norm(row.get("plan_id")), "company": norm(row.get("company")), "error": str(exc)[:500]})
            continue
        for result in results:
            confidence, official_candidate = confidence_for(norm(row.get("source_key")), norm(result.get("url")), norm(result.get("title")))
            record = {
                "evidence_id": stable_id("mce", row.get("plan_id"), result.get("url")),
                "plan_id": norm(row.get("plan_id")),
                "priority_rank": int(row.get("priority_rank") or 999999),
                "company_id": norm(row.get("company_id")),
                "company": norm(row.get("company")),
                "product_family_id": norm(row.get("product_family_id")),
                "brand": norm(row.get("brand")),
                "product_family": norm(row.get("product_family")),
                "source_key": norm(row.get("source_key")),
                "source_name": norm(row.get("source_name")),
                "title": norm(result.get("title")),
                "url": norm(result.get("url")),
                "published": norm(result.get("published")),
                "captured_at": captured_at,
                "confidence": confidence,
                "official_candidate": official_candidate,
                "evidence_excerpt": norm(result.get("excerpt")),
                "raw_text": norm(result.get("raw"))[:3000],
                "crosscheck_status": "candidate",
            }
            key = (record["plan_id"], record["url"])
            if key not in existing:
                added += 1
            existing[key] = record
        if sleep_seconds:
            time.sleep(sleep_seconds)
    write_existing(existing)
    return {
        "plan_rows": len(plan),
        "queries_run": queried,
        "records_total": len(existing),
        "records_added": added,
        "errors": len(errors),
        "error_samples": errors[:5],
        "path": str(MDR_CE_EVIDENCE_PATH),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30, help="Number of plan rows to query. 0 means all pending rows.")
    parser.add_argument("--num-results", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=0.2)
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = collect(args.limit, args.num_results, args.sleep, args.timeout, args.force)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
