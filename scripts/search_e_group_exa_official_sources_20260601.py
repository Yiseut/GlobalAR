#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from apply_e_group_live_url_indications_20260601 import extract_best_candidate, fetch_url
from apply_e_group_local_spec_indication_candidates_20260601 import (
    PRODUCT_MASTER,
    REACQUIRE_QUEUE,
    clean,
    has_indication,
    product_tokens,
    read_csv,
)
from search_e_group_external_official_sources_20260601 import official_score


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_exa_search_summary_latest.json"
SEARCH_RESULTS_CSV = AUDIT_DIR / "e_group_exa_search_results_latest.csv"
FETCH_LOG_CSV = AUDIT_DIR / "e_group_exa_search_fetch_log_latest.csv"
CANDIDATES_CSV = AUDIT_DIR / "e_group_exa_search_candidates_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_exa_search_skipped_latest.csv"

EXA_URL = "https://api.exa.ai/search"
SEARCH_WORKERS = 5
FETCH_WORKERS = 8
MAX_URLS_PER_PRODUCT = 5

PAGE_NOISE_FRAGMENTS = [
    "cookie",
    "privacy policy",
    "terms of use",
    "terms and conditions",
    "subscribe",
    "newsletter",
    "skip to main",
    "skip to content",
    "available in",
    "adverse reactions",
    "contraindications",
    "source:",
]


def ascii_parts(row: dict[str, str]) -> list[str]:
    text = " ".join([clean(row.get("company")), clean(row.get("brand")), clean(row.get("standard_product_name"))])
    tokens = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-]{1,}", text):
        if token.casefold() in {"or", "and", "the", "for", "with"}:
            continue
        tokens.append(token)
    out = []
    seen = set()
    for token in tokens:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(token)
    return out[:10]


def build_query(row: dict[str, str]) -> str:
    parts = ascii_parts(row)
    if not parts:
        parts = [clean(row.get("company")), clean(row.get("brand")), clean(row.get("standard_product_name"))]
    base = " ".join(part for part in parts if part)
    track = clean(row.get("track"))
    form = clean(row.get("form"))
    return f'{base} official product page IFU brochure "indication" "intended use" {track} {form}'.strip()


def exa_search(query: str, num_results: int, timeout: int) -> list[dict[str, str]]:
    key = os.environ.get("EXA_API_KEY")
    if not key:
        raise RuntimeError("EXA_API_KEY is not set")
    payload = {"query": query, "numResults": num_results}
    response = requests.post(
        EXA_URL,
        headers={"x-api-key": key, "Content-Type": "application/json"},
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    rows = []
    for item in data.get("results", []):
        url = clean(item.get("url"))
        title = clean(item.get("title"))
        if url and title:
            rows.append({"query": query, "title": title, "url": url})
    return rows


def select_urls(product: dict[str, str], rows: list[dict[str, str]], threshold: int) -> list[dict[str, str]]:
    scored = []
    for row in rows:
        score = official_score(row["url"], row["title"], product)
        if score < threshold:
            continue
        scored.append({**row, "official_score": str(score)})
    scored.sort(key=lambda row: -int(row["official_score"]))
    out = []
    seen = set()
    for row in scored:
        key = row["url"].split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
        if len(out) >= MAX_URLS_PER_PRODUCT:
            break
    return out


def scrub_page_noise(text: str) -> str:
    cleaned = []
    for line in clean(text).splitlines():
        low = line.casefold()
        if any(fragment in low for fragment in PAGE_NOISE_FRAGMENTS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--num-results", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=45)
    parser.add_argument("--threshold", type=int, default=45)
    args = parser.parse_args()

    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    _, product_rows = read_csv(PRODUCT_MASTER)
    _, queue_rows = read_csv(REACQUIRE_QUEUE)
    _, manual_rows = read_csv(MANUAL_INDICATION)

    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}
    existing_seed_with_indication = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if clean(row.get("seed_record_id")) and has_indication(row)
    }
    targets = [row for row in queue_rows if clean(row.get("seed_record_id")) not in existing_seed_with_indication]
    if args.limit:
        targets = targets[: args.limit]

    search_rows: list[dict[str, str]] = []
    search_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {}
        for row in targets:
            seed = clean(row.get("seed_record_id"))
            query = build_query(row)
            futures[executor.submit(exa_search, query, args.num_results, args.timeout)] = (seed, query)
        for future in as_completed(futures):
            seed, query = futures[future]
            try:
                rows = future.result()
                for result in rows:
                    search_rows.append({"seed_record_id": seed, **result})
            except Exception as exc:
                search_errors.append({"seed_record_id": seed, "query": query, "error": type(exc).__name__, "message": str(exc)[:500]})

    by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in search_rows:
        by_seed[row["seed_record_id"]].append(row)

    selected: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for row in targets:
        seed = clean(row.get("seed_record_id"))
        product = product_by_seed.get(seed)
        if not product:
            skipped.append({"seed_record_id": seed, "reason": "product_not_found"})
            continue
        chosen = select_urls(product, by_seed.get(seed, []), args.threshold)
        if not chosen:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": "no_strong_official_exa_result",
                }
            )
            continue
        for item in chosen:
            selected.append({"seed_record_id": seed, **item})

    fetched: dict[tuple[str, str], dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as executor:
        futures = {executor.submit(fetch_url, row["url"]): row for row in selected}
        for future in as_completed(futures):
            row = futures[future]
            try:
                fetched[(row["seed_record_id"], row["url"])] = future.result()
            except Exception as exc:
                fetched[(row["seed_record_id"], row["url"])] = {
                    "url": row["url"],
                    "final_url": "",
                    "status": "",
                    "error": type(exc).__name__,
                    "title": "",
                    "text": "",
                }

    fetch_log: list[dict[str, str]] = []
    candidates: list[dict[str, str]] = []
    reject_counter: Counter[str] = Counter()
    for row in selected:
        seed = row["seed_record_id"]
        product = product_by_seed.get(seed)
        if not product:
            continue
        fetch = fetched[(seed, row["url"])]
        fetch_log.append(
            {
                "seed_record_id": seed,
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "search_title": row["title"],
                "search_url": row["url"],
                "official_score": row["official_score"],
                "final_url": clean(fetch.get("final_url")),
                "status": clean(fetch.get("status")),
                "error": clean(fetch.get("error")),
                "fetched_title": clean(fetch.get("title")),
                "text_chars": str(len(clean(fetch.get("text")))),
            }
        )
        if clean(fetch.get("error")):
            reject_counter[f"fetch:{clean(fetch.get('error'))}"] += 1
            continue
        scrubbed_fetch = dict(fetch)
        scrubbed_fetch["text"] = scrub_page_noise(clean(fetch.get("text")))
        indication, reason, extract_score = extract_best_candidate(product, scrubbed_fetch)
        if not indication:
            reject_counter[reason] += 1
            continue
        total_score = int(row["official_score"]) + extract_score
        candidates.append(
            {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "track": clean(product.get("commercial_path_l1")),
                "form": clean(product.get("commercial_path_l2")),
                "total_score": str(total_score),
                "source_score": row["official_score"],
                "extract_score": str(extract_score),
                "source_url": clean(fetch.get("final_url") or row["url"]),
                "search_title": row["title"],
                "fetched_title": clean(fetch.get("title")),
                "indication": indication,
            }
        )

    candidates.sort(key=lambda item: (-int(item["total_score"]), item["company"], item["brand"]))

    result_fields = ["seed_record_id", "query", "title", "url", "official_score"]
    enriched_search_rows = []
    for row in search_rows:
        product = product_by_seed.get(row["seed_record_id"], {})
        enriched_search_rows.append({**row, "official_score": str(official_score(row["url"], row["title"], product))})
    with SEARCH_RESULTS_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=result_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(enriched_search_rows)

    with FETCH_LOG_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "seed_record_id",
            "company",
            "brand",
            "standard_product_name",
            "search_title",
            "search_url",
            "official_score",
            "final_url",
            "status",
            "error",
            "fetched_title",
            "text_chars",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(fetch_log)

    with CANDIDATES_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "seed_record_id",
            "product_id",
            "company",
            "brand",
            "standard_product_name",
            "track",
            "form",
            "total_score",
            "source_score",
            "extract_score",
            "source_url",
            "search_title",
            "fetched_title",
            "indication",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)

    with SKIPPED_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = ["seed_record_id", "company", "brand", "standard_product_name", "reason"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(skipped)

    summary = {
        "checked_at": checked_at,
        "target_products": len(targets),
        "search_errors": len(search_errors),
        "search_results": len(enriched_search_rows),
        "selected_fetch_urls": len(selected),
        "fetch_ok": sum(1 for row in fetch_log if not row["error"] and row["text_chars"] != "0"),
        "candidate_rows": len(candidates),
        "candidate_products": len({row["seed_record_id"] for row in candidates}),
        "skipped_products_no_strong_result": sum(1 for row in skipped if row.get("reason") == "no_strong_official_exa_result"),
        "reject_reasons": dict(reject_counter.most_common(30)),
        "outputs": {
            "summary_json": str(SUMMARY_JSON),
            "search_results_csv": str(SEARCH_RESULTS_CSV),
            "fetch_log_csv": str(FETCH_LOG_CSV),
            "candidates_csv": str(CANDIDATES_CSV),
            "skipped_csv": str(SKIPPED_CSV),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    main()
