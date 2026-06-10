#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import fitz
import requests
from bs4 import BeautifulSoup

from apply_e_group_local_spec_indication_candidates_20260601 import (
    CLINICAL_TERMS,
    HARD_REJECT_FRAGMENTS,
    INDICATION_FIELDS,
    OFFICIAL_DOMAIN_HINTS,
    OTHER_PRODUCT_MARKERS,
    PRODUCT_MASTER,
    PRODUCT_SPEC,
    REACQUIRE_QUEUE,
    REJECT_URL_PARTS,
    WRONG_PATH_FRAGMENTS,
    clean,
    company_domain_tokens,
    contains_bad_text,
    domain_of,
    has_indication,
    looks_truncated,
    make_manual_row,
    normalize_candidate,
    product_tokens,
    read_csv,
    source_is_official,
    stable_id,
    text_has_clinical_term,
    write_csv,
)


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
AUDIT_DIR = DATA_DIR / "audits"
MANUAL_INDICATION = DATA_DIR / "manual_official_indication_evidence.csv"

SUMMARY_JSON = AUDIT_DIR / "e_group_live_url_indication_apply_latest.json"
APPLIED_CSV = AUDIT_DIR / "e_group_live_url_indication_applied_latest.csv"
SKIPPED_CSV = AUDIT_DIR / "e_group_live_url_indication_skipped_latest.csv"
CANDIDATES_CSV = AUDIT_DIR / "e_group_live_url_indication_candidates_latest.csv"
FETCH_LOG_CSV = AUDIT_DIR / "e_group_live_url_fetch_log_latest.csv"


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

MAX_WORKERS = 8
REQUEST_TIMEOUT = 15
MAX_CANDIDATE_URLS_PER_PRODUCT = 4
MAX_HTML_CHARS = 280_000
MAX_PDF_BYTES = 14_000_000


STRONG_PATTERN = re.compile(
    r"\b(indications?\s*(?:for use)?|indicated for|is indicated for|are indicated for|"
    r"intended for|is intended for|are intended for|intended use|intended purpose|"
    r"approved for|cleared for|fda cleared for|for the correction of|for the treatment of)\b|"
    r"适应症|适用于|用于",
    re.I,
)

WEAK_USED_PATTERN = re.compile(r"\b(is used for|are used for|used for|used to treat)\b", re.I)

SEGMENT_SPLIT_RE = re.compile(r"(?<=[.!?。；;])\s+|\n+|\s+\[\.\.\.\]\s+")


def url_is_fetchable_official(url: str, product: dict[str, str]) -> bool:
    if not url or not url.startswith(("http://", "https://")):
        return False
    low_url = url.casefold()
    if any(part in low_url for part in REJECT_URL_PARTS):
        return False
    domain = domain_of(url)
    if not domain:
        return False
    domain_blob = domain.replace("-", "").replace(".", "")
    if any(hint in domain_blob for hint in OFFICIAL_DOMAIN_HINTS):
        return True
    if any(token in domain_blob for token in company_domain_tokens(product)):
        return True
    if any(token in low_url for token in product_tokens(product)):
        return True
    return False


def clean_visible_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n\s+", "\n", text)
    return text.strip()


def html_to_text(content: bytes) -> tuple[str, str]:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "header", "footer", "nav"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = soup.get_text("\n", strip=True)
    return title, clean_visible_text(text[:MAX_HTML_CHARS])


def pdf_to_text(content: bytes) -> tuple[str, str]:
    with fitz.open(stream=content, filetype="pdf") as doc:
        chunks = []
        meta_title = clean(doc.metadata.get("title") if doc.metadata else "")
        for page in doc[:12]:
            chunks.append(page.get_text("text"))
            if sum(len(chunk) for chunk in chunks) > MAX_HTML_CHARS:
                break
    return meta_title, clean_visible_text("\n".join(chunks))


def fetch_url(url: str) -> dict[str, str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=False)
        content_type = response.headers.get("content-type", "")
        status_code = str(response.status_code)
        final_url = response.url
        if response.status_code >= 400:
            return {"url": url, "final_url": final_url, "status": status_code, "error": "http_error", "title": "", "text": ""}
        content = response.content
        if "pdf" in content_type.casefold() or final_url.casefold().endswith(".pdf"):
            if len(content) > MAX_PDF_BYTES:
                return {"url": url, "final_url": final_url, "status": status_code, "error": "pdf_too_large", "title": "", "text": ""}
            title, text = pdf_to_text(content)
            return {"url": url, "final_url": final_url, "status": status_code, "error": "", "title": title, "text": text}
        title, text = html_to_text(content)
        return {"url": url, "final_url": final_url, "status": status_code, "error": "", "title": title, "text": text}
    except Exception as exc:
        return {"url": url, "final_url": "", "status": "", "error": type(exc).__name__, "title": "", "text": ""}


def own_marker_in_url_or_title(product: dict[str, str], url: str, title: str) -> bool:
    haystack = f"{url} {title}".casefold().replace("-", " ")
    tokens = product_tokens(product)
    if not tokens:
        return False
    return any(token in haystack for token in tokens)


def segment_candidates(text: str) -> list[tuple[str, bool]]:
    normalized = clean_visible_text(text)
    pieces = [piece.strip(" -|") for piece in SEGMENT_SPLIT_RE.split(normalized) if piece.strip(" -|")]
    out: list[tuple[str, bool]] = []
    for idx, piece in enumerate(pieces):
        strong = STRONG_PATTERN.search(piece)
        weak = WEAK_USED_PATTERN.search(piece)
        if strong:
            segment = piece[strong.start() :]
            if idx + 1 < len(pieces) and len(segment) < 150:
                segment = f"{segment}; {pieces[idx + 1]}"
            out.append((segment, True))
        elif weak and re.search(r"\bindications?\b|适应症", piece, re.I):
            out.append((piece[weak.start() :], False))
    return out


def mentions_other_product(text: str, product: dict[str, str]) -> bool:
    low = text.casefold()
    own_tokens = product_tokens(product)
    for marker in OTHER_PRODUCT_MARKERS:
        marker_key = marker.replace(" ", "")
        if marker_key in own_tokens:
            continue
        if marker in low:
            return True
    return False


def product_near_candidate(segment: str, product: dict[str, str], url: str, title: str) -> bool:
    low_segment = segment.casefold()
    tokens = product_tokens(product)
    if not tokens:
        return False
    if any(token in low_segment for token in tokens):
        return True
    return own_marker_in_url_or_title(product, url, title)


def extract_best_candidate(product: dict[str, str], fetch: dict[str, str]) -> tuple[str, str, int]:
    text = clean(fetch.get("text"))
    if not text or len(text) < 80:
        return "", "empty_or_short_text", 0
    low_full = text.casefold()
    for fragment in HARD_REJECT_FRAGMENTS + WRONG_PATH_FRAGMENTS:
        if fragment in low_full and fragment not in {"clinical evaluation"}:
            return "", f"page_bad_text:{fragment}", 0

    best: tuple[str, str, int] = ("", "no_candidate", 0)
    for raw_segment, strong in segment_candidates(text):
        candidate = normalize_candidate(raw_segment)
        if len(candidate) < 45 or len(candidate) > 650:
            continue
        bad = contains_bad_text(candidate)
        if bad:
            best = ("", bad, 0)
            continue
        if looks_truncated(candidate):
            best = ("", "truncated_or_navigation_text", 0)
            continue
        if mentions_other_product(candidate, product):
            best = ("", "mentions_other_product", 0)
            continue
        if not product_near_candidate(candidate, product, clean(fetch.get("final_url") or fetch.get("url")), clean(fetch.get("title"))):
            best = ("", "product_token_not_near_candidate", 0)
            continue
        if not text_has_clinical_term(candidate):
            best = ("", "no_clinical_term", 0)
            continue
        score = 20
        if strong:
            score += 30
        if re.search(r"\bindicated for|intended for|intended use|approved for|cleared for\b", candidate, re.I):
            score += 25
        if clean(fetch.get("final_url") or fetch.get("url")).casefold().endswith(".pdf"):
            score += 10
        if own_marker_in_url_or_title(product, clean(fetch.get("final_url") or fetch.get("url")), clean(fetch.get("title"))):
            score += 12
        if score > best[2]:
            best = (candidate, "accepted", score)
    return best


def collect_candidate_urls(
    queue_rows: list[dict[str, str]],
    spec_rows: list[dict[str, str]],
    product_by_id: dict[str, dict[str, str]],
    product_by_seed: dict[str, dict[str, str]],
    target_seeds: set[str],
) -> dict[str, list[str]]:
    urls: dict[str, list[str]] = defaultdict(list)
    for row in queue_rows:
        seed = clean(row.get("seed_record_id"))
        product = product_by_seed.get(seed)
        url = clean(row.get("old_url_to_discard_or_deprioritize"))
        if seed in target_seeds and product and url_is_fetchable_official(url, product):
            urls[seed].append(url)

    for spec in spec_rows:
        product = product_by_id.get(clean(spec.get("product_id")))
        if not product:
            continue
        seed = clean(product.get("seed_record_id"))
        if seed not in target_seeds:
            continue
        url = clean(spec.get("source_page_url"))
        if not url_is_fetchable_official(url, product):
            continue
        fake_spec = dict(spec)
        if not source_is_official(fake_spec, product):
            continue
        urls[seed].append(url)

    unique_urls: dict[str, list[str]] = {}
    for seed, values in urls.items():
        seen = set()
        ordered = []
        for url in values:
            if url in seen:
                continue
            seen.add(url)
            ordered.append(url)
            if len(ordered) >= MAX_CANDIDATE_URLS_PER_PRODUCT:
                break
        unique_urls[seed] = ordered
    return unique_urls


def main() -> None:
    checked_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    _, product_rows = read_csv(PRODUCT_MASTER)
    _, spec_rows = read_csv(PRODUCT_SPEC)
    manual_fields, manual_rows = read_csv(MANUAL_INDICATION)
    _, queue_rows = read_csv(REACQUIRE_QUEUE)

    product_by_id = {clean(row.get("product_id")): row for row in product_rows if clean(row.get("product_id"))}
    product_by_seed = {clean(row.get("seed_record_id")): row for row in product_rows if clean(row.get("seed_record_id"))}

    queue_seeds = {clean(row.get("seed_record_id")) for row in queue_rows if clean(row.get("seed_record_id"))}
    existing_seed_with_indication = {
        clean(row.get("seed_record_id"))
        for row in manual_rows
        if clean(row.get("seed_record_id")) and has_indication(row)
    }
    target_seeds = queue_seeds - existing_seed_with_indication

    urls_by_seed = collect_candidate_urls(queue_rows, spec_rows, product_by_id, product_by_seed, target_seeds)
    url_jobs = []
    for seed, urls in urls_by_seed.items():
        for url in urls:
            url_jobs.append((seed, url))

    fetched: dict[tuple[str, str], dict[str, str]] = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_url, url): (seed, url) for seed, url in url_jobs}
        for future in as_completed(futures):
            seed, url = futures[future]
            fetched[(seed, url)] = future.result()

    fetch_log: list[dict[str, str]] = []
    candidates: list[dict[str, str]] = []
    best_by_seed: dict[str, tuple[int, str, dict[str, str]]] = {}
    skip_counter: Counter[str] = Counter()
    skipped: list[dict[str, str]] = []

    for seed in sorted(target_seeds):
        product = product_by_seed.get(seed)
        if not product:
            skipped.append({"seed_record_id": seed, "reason": "product_not_found"})
            skip_counter["product_not_found"] += 1
            continue
        urls = urls_by_seed.get(seed, [])
        if not urls:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": "no_fetchable_official_url",
                }
            )
            skip_counter["no_fetchable_official_url"] += 1
            continue
        best_reason = "no_candidate"
        for url in urls:
            fetch = fetched.get((seed, url), {"url": url, "error": "missing_fetch_result", "text": ""})
            fetch_log.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "url": url,
                    "final_url": clean(fetch.get("final_url")),
                    "status": clean(fetch.get("status")),
                    "error": clean(fetch.get("error")),
                    "title": clean(fetch.get("title")),
                    "text_chars": str(len(clean(fetch.get("text")))),
                }
            )
            if clean(fetch.get("error")):
                best_reason = f"fetch:{clean(fetch.get('error'))}"
                skip_counter[best_reason] += 1
                continue
            indication, reason, score = extract_best_candidate(product, fetch)
            if not indication:
                best_reason = reason
                skip_counter[reason] += 1
                continue
            candidate = {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "score": str(score),
                "url": url,
                "final_url": clean(fetch.get("final_url")) or url,
                "title": clean(fetch.get("title")),
                "indication": indication,
            }
            candidates.append(candidate)
            current = best_by_seed.get(seed)
            if current is None or score > current[0]:
                best_by_seed[seed] = (score, indication, fetch)
        if seed not in best_by_seed:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": best_reason,
                    "candidate_urls": str(len(urls)),
                }
            )

    existing_keys = {
        (
            clean(row.get("product_id")),
            clean(row.get("source_url")),
            clean(row.get("official_description_exact") or row.get("approved_indication") or row.get("intended_use")),
        )
        for row in manual_rows
    }

    new_rows: list[dict[str, str]] = []
    applied: list[dict[str, str]] = []
    for seed, (score, indication, fetch) in sorted(best_by_seed.items(), key=lambda item: (-item[1][0], item[0])):
        product = product_by_seed[seed]
        source_url = clean(fetch.get("final_url") or fetch.get("url"))
        source = {
            "source_page_url": source_url,
            "source_query_type": "live_official_url_fetch",
            "source_title": clean(fetch.get("title")),
            "evidence_excerpt": indication,
        }
        manual = make_manual_row(product, source, indication, checked_at)
        manual["source_key"] = stable_id("egroup_live_url_indication", clean(product.get("product_id")), source_url, indication)
        manual["source_type"] = "live_official_url_fetch"
        manual["regulatory_pathway"] = "live official URL/IFU full-text extraction"
        manual["official_description_source_field"] = "live fetched page/pdf text"
        manual["reviewed_by"] = "auto_live_url_indication_extraction_20260601"
        manual["review_status"] = "auto_promoted_live_official_source_indication"
        key = (
            clean(manual.get("product_id")),
            clean(manual.get("source_url")),
            clean(manual.get("official_description_exact")),
        )
        if key in existing_keys:
            skipped.append(
                {
                    "seed_record_id": seed,
                    "company": clean(product.get("company")),
                    "brand": clean(product.get("brand")),
                    "standard_product_name": clean(product.get("standard_product_name")),
                    "reason": "duplicate_exact_key",
                }
            )
            skip_counter["duplicate_exact_key"] += 1
            continue
        existing_keys.add(key)
        new_rows.append(manual)
        applied.append(
            {
                "seed_record_id": seed,
                "product_id": clean(product.get("product_id")),
                "company": clean(product.get("company")),
                "brand": clean(product.get("brand")),
                "standard_product_name": clean(product.get("standard_product_name")),
                "score": str(score),
                "source_url": source_url,
                "indication": indication,
            }
        )

    if new_rows:
        backup_path = AUDIT_DIR / f"manual_official_indication_evidence_backup_before_live_url_indication_{stamp}.csv"
        shutil.copy2(MANUAL_INDICATION, backup_path)
        output_fields = manual_fields or INDICATION_FIELDS
        for field in INDICATION_FIELDS:
            if field not in output_fields:
                output_fields.append(field)
        write_csv(MANUAL_INDICATION, output_fields, manual_rows + new_rows)
    else:
        backup_path = None

    write_csv(
        CANDIDATES_CSV,
        ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "score", "url", "final_url", "title", "indication"],
        candidates,
    )
    write_csv(
        APPLIED_CSV,
        ["seed_record_id", "product_id", "company", "brand", "standard_product_name", "score", "source_url", "indication"],
        applied,
    )
    write_csv(
        SKIPPED_CSV,
        ["seed_record_id", "company", "brand", "standard_product_name", "reason", "candidate_urls"],
        skipped,
    )
    write_csv(
        FETCH_LOG_CSV,
        ["seed_record_id", "company", "brand", "standard_product_name", "url", "final_url", "status", "error", "title", "text_chars"],
        fetch_log,
    )

    summary = {
        "checked_at": checked_at,
        "target_queue_rows": len(target_seeds),
        "candidate_url_jobs": len(url_jobs),
        "fetched_ok": sum(1 for row in fetch_log if not row["error"] and row["text_chars"] != "0"),
        "candidate_rows": len(candidates),
        "candidate_products": len({row["seed_record_id"] for row in candidates}),
        "applied_rows": len(applied),
        "skipped_products": len(skipped),
        "backup_path": str(backup_path) if backup_path else "",
        "skip_reasons": dict(skip_counter.most_common()),
        "outputs": {
            "summary_json": str(SUMMARY_JSON),
            "applied_csv": str(APPLIED_CSV),
            "skipped_csv": str(SKIPPED_CSV),
            "candidates_csv": str(CANDIDATES_CSV),
            "fetch_log_csv": str(FETCH_LOG_CSV),
        },
    }
    SUMMARY_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]
    main()
