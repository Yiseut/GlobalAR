#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

from apply_e_group_live_url_indications_20260601 import extract_best_candidate, fetch_url
from apply_e_group_local_spec_indication_candidates_20260601 import (
    OFFICIAL_DOMAIN_HINTS,
    PRODUCT_MASTER,
    REACQUIRE_QUEUE,
    clean,
    company_domain_tokens,
    domain_of,
    has_indication,
    product_tokens,
    read_csv,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_external_search_summary_latest.json"
SEARCH_RESULTS_CSV = AUDIT_DIR / "e_group_external_search_results_latest.csv"
FETCH_LOG_CSV = AUDIT_DIR / "e_group_external_search_fetch_log_latest.csv"
CANDIDATES_CSV = AUDIT_DIR / "e_group_external_search_candidates_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_external_search_skipped_latest.csv"
SEARCH_ERRORS_CSV = AUDIT_DIR / "e_group_external_search_errors_latest.csv"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

SEARCH_WORKERS = 1
FETCH_WORKERS = 8
MAX_RESULTS_PER_QUERY = 8
MAX_URLS_PER_PRODUCT = 5
SEARCH_TIMEOUT = 20

REGULATOR_DOMAINS = {
    "accessdata.fda.gov",
    "fda.gov",
    "fda.report",
    "open.fda.gov",
    "ec.europa.eu",
    "webgate.ec.europa.eu",
    "eudamed.ec.europa.eu",
    "gov.uk",
    "mhra.org.uk",
    "health-products.canada.ca",
}

KNOWN_BAD_DOMAINS = {
    "fillermarket.com",
    "centralefillers.com",
    "homemedicallaser.com",
    "prnewswire.com",
    "businesswire.com",
    "medicalexpo.com",
    "pdf.medicalexpo.com",
    "aiqixie.com",
    "sigma-stat.com",
    "mitoconbiomed.in",
    "beyondmedicalaesthetics.uk",
    "azum.ua",
    "nordicms.com",
    "alliedmedica.com",
    "konepharma.co.kr",
    "cosmo-korea.com",
    "mp.weixin.qq.com",
    "alibaba.com",
    "made-in-china.com",
}

QUERY_NOISE = {
    "IFU",
    "OR",
    "SSCP",
    "PDF",
    "filetype",
    "Instructions",
    "Use",
    "brochure",
    "Summary",
}


def ddg_url(href: str) -> str:
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        values = parse_qs(parsed.query).get("uddg")
        if values:
            return unquote(values[0])
    return href


def search_duckduckgo(query: str) -> list[dict[str, str]]:
    url = "https://lite.duckduckgo.com/lite/"
    response = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(url, params={"q": query}, headers=HEADERS, timeout=SEARCH_TIMEOUT)
            response.raise_for_status()
            time.sleep(0.8)
            break
        except Exception as exc:  # external search variability
            last_error = exc
            time.sleep(2.0 + attempt * 2.0)
    if response is None:
        raise RuntimeError(str(last_error))
    soup = BeautifulSoup(response.text, "html.parser")
    results: list[dict[str, str]] = []
    seen = set()
    for link in soup.find_all("a"):
        href = ddg_url(clean(link.get("href")))
        title = clean(link.get_text(" ", strip=True))
        if not href or not title:
            continue
        if href.startswith("http") is False:
            continue
        if "duckduckgo.com" in href:
            continue
        key = href.split("#")[0]
        if key in seen:
            continue
        seen.add(key)
        if title.lower() in {"images", "videos", "news", "maps"}:
            continue
        results.append({"query": query, "title": title, "url": href})
        if len(results) >= MAX_RESULTS_PER_QUERY:
            break
    return results


def ascii_query_parts(row: dict[str, str]) -> list[str]:
    text = " ".join(
        [
            clean(row.get("company")),
            clean(row.get("brand")),
            clean(row.get("standard_product_name")),
        ]
    )
    tokens = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-]{2,}", text):
        if token.upper() in QUERY_NOISE:
            continue
        tokens.append(token)
    deduped = []
    seen = set()
    for token in tokens:
        key = token.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(token)
    return deduped[:8]


def build_queries(row: dict[str, str]) -> list[str]:
    company = clean(row.get("company"))
    brand = clean(row.get("brand"))
    product = clean(row.get("standard_product_name"))
    parts = ascii_query_parts(row)
    primary = " ".join(parts) if parts else " ".join([company, brand, product]).strip()
    queries = [
        f'"{company}" "{brand}" "{product}" indication intended use',
        f'{primary} brochure PDF indication intended use',
        f'{primary} IFU "Instructions for Use" PDF',
    ]
    compact = []
    seen = set()
    for query in queries:
        query = re.sub(r"\s+", " ", query).strip()
        if query and query.casefold() not in seen:
            compact.append(query)
            seen.add(query.casefold())
    return compact[:3]


def is_bad_domain(url: str) -> bool:
    domain = domain_of(url)
    return any(domain == bad or domain.endswith("." + bad) for bad in KNOWN_BAD_DOMAINS)


def is_regulator(url: str) -> bool:
    domain = domain_of(url)
    return any(domain == reg or domain.endswith("." + reg) for reg in REGULATOR_DOMAINS)


def official_score(url: str, title: str, product: dict[str, str]) -> int:
    if is_bad_domain(url):
        return -100
    domain = domain_of(url)
    if not domain:
        return -100
    domain_blob = domain.replace("-", "").replace(".", "")
    haystack = f"{url} {title}".casefold().replace("-", " ")
    score = 0
    if is_regulator(url):
        score += 45
    if any(hint in domain_blob for hint in OFFICIAL_DOMAIN_HINTS):
        score += 30
    company_norm = re.sub(r"[^a-z0-9]+", "", clean(product.get("company")).casefold())
    if len(company_norm) >= 3 and company_norm in domain_blob:
        score += 20
    company_hits = sum(1 for token in company_domain_tokens(product) if token in domain_blob or token in haystack)
    product_hits = sum(1 for token in product_tokens(product) if token in haystack)
    score += min(company_hits, 2) * 12
    score += min(product_hits, 3) * 16
    if url.casefold().endswith(".pdf") or ".pdf" in url.casefold():
        score += 8
    if any(word in haystack for word in ["ifu", "instructions for use", "brochure", "catalog", "eifu", "510(k)", "pma"]):
        score += 8
    return score


def select_urls_for_product(product: dict[str, str], rows: list[dict[str, str]]) -> list[dict[str, str]]:
    scored = []
    for row in rows:
        score = official_score(row["url"], row["title"], product)
        if score < 45:
            continue
        scored.append({**row, "official_score": str(score)})
    scored.sort(key=lambda item: -int(item["official_score"]))
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Limit products for a smoke run.")
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

    search_jobs = []
    for row in targets:
        seed = clean(row.get("seed_record_id"))
        product = product_by_seed.get(seed)
        if not product:
            continue
        for query in build_queries(row):
            search_jobs.append((seed, query))

    search_results_by_seed: dict[str, list[dict[str, str]]] = defaultdict(list)
    search_errors: list[dict[str, str]] = []
    with ThreadPoolExecutor(max_workers=SEARCH_WORKERS) as executor:
        futures = {executor.submit(search_duckduckgo, query): (seed, query) for seed, query in search_jobs}
        for future in as_completed(futures):
            seed, query = futures[future]
            try:
                for item in future.result():
                    search_results_by_seed[seed].append(item)
            except Exception as exc:
                search_errors.append({"seed_record_id": seed, "query": query, "error": type(exc).__name__, "message": str(exc)[:300]})

    selected: list[dict[str, str]] = []
    skipped: list[dict[str, str]] = []
    for row in targets:
        seed = clean(row.get("seed_record_id"))
        product = product_by_seed.get(seed)
        if not product:
            skipped.append({"seed_record_id": seed, "reason": "product_not_found"})
            continue
        chosen = select_urls_for_product(product, search_results_by_seed.get(seed, []))
        if not chosen:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": "no_strong_official_search_result",
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

    candidates: list[dict[str, str]] = []
    fetch_log: list[dict[str, str]] = []
    candidate_reason_counter: Counter[str] = Counter()
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
            candidate_reason_counter[f"fetch:{clean(fetch.get('error'))}"] += 1
            continue
        indication, reason, score = extract_best_candidate(product, fetch)
        if not indication:
            candidate_reason_counter[reason] += 1
            continue
        total_score = score + int(row["official_score"])
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
                "extract_score": str(score),
                "source_url": clean(fetch.get("final_url") or row["url"]),
                "search_title": row["title"],
                "fetched_title": clean(fetch.get("title")),
                "indication": indication,
            }
        )

    candidates.sort(key=lambda item: (-int(item["total_score"]), item["company"], item["brand"]))

    result_fields = ["seed_record_id", "query", "title", "url", "official_score"]
    all_result_rows: list[dict[str, str]] = []
    for seed, rows in search_results_by_seed.items():
        product = product_by_seed.get(seed, {})
        for row in rows:
            all_result_rows.append({**row, "seed_record_id": seed, "official_score": str(official_score(row["url"], row["title"], product))})
    with SEARCH_RESULTS_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=result_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(all_result_rows)

    with SEARCH_ERRORS_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["seed_record_id", "query", "error", "message"],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(search_errors)

    fetch_fields = [
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
    with FETCH_LOG_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fetch_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(fetch_log)

    candidate_fields = [
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
    with CANDIDATES_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=candidate_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(candidates)

    skipped_fields = ["seed_record_id", "company", "brand", "standard_product_name", "reason"]
    with SKIPPED_CSV.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=skipped_fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(skipped)

    summary = {
        "checked_at": checked_at,
        "target_products": len(targets),
        "search_jobs": len(search_jobs),
        "search_errors": len(search_errors),
        "search_result_rows": len(all_result_rows),
        "selected_fetch_urls": len(selected),
        "fetch_ok": sum(1 for row in fetch_log if not row["error"] and row["text_chars"] != "0"),
        "candidate_rows": len(candidates),
        "candidate_products": len({row["seed_record_id"] for row in candidates}),
        "skipped_products_no_strong_result": sum(1 for row in skipped if row.get("reason") == "no_strong_official_search_result"),
        "candidate_reject_reasons": dict(candidate_reason_counter.most_common(30)),
        "outputs": {
            "summary_json": str(SUMMARY_JSON),
            "search_results_csv": str(SEARCH_RESULTS_CSV),
            "search_errors_csv": str(SEARCH_ERRORS_CSV),
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
