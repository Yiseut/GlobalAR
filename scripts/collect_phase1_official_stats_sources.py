#!/usr/bin/env python3
"""Collect official phase-1 procedure-statistics source pages and PDFs.

This script uses the locally installed Scrapling package for page discovery.
Downloaded source files are stored under data/commercial_sources, which is
ignored by git via data/*; compact inventories are written to data/audits.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse
from urllib.request import Request, urlopen

try:
    from scrapling.fetchers import Fetcher
except Exception as exc:  # pragma: no cover - import guard for local runs
    raise SystemExit(f"Scrapling is required: {exc}") from exc


PROJECT_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_DIR / "data" / "commercial_sources" / "phase1_official_stats"
AUDIT_DIR = PROJECT_DIR / "data" / "audits"
INVENTORY_PATH = AUDIT_DIR / "commercial_phase1_official_source_inventory_latest.csv"
SUMMARY_PATH = AUDIT_DIR / "commercial_phase1_official_source_inventory_latest.json"

ASPS_BASE = "https://www.plasticsurgery.org/news/plastic-surgery-statistics"
AESTHETIC_SOCIETY_BASE = "https://www.theaestheticsociety.org/media/procedural-statistics"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

FIELDS = [
    "source_id",
    "source_org",
    "source_page",
    "source_page_title",
    "link_text",
    "url",
    "canonical_url",
    "year",
    "artifact_type",
    "topic",
    "status",
    "http_status",
    "content_type",
    "local_path",
    "sha256",
    "bytes",
    "captured_at",
    "note",
]


@dataclass(frozen=True)
class SourcePage:
    source_id: str
    source_org: str
    url: str
    year: str


def now_iso() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def safe_text(value: Any) -> str:
    return " ".join(str(value or "").replace("\x00", "").split())


def slugify(value: str, fallback: str = "source") -> str:
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._").lower()
    return text[:140] or fallback


def infer_year(text: str, url: str) -> str:
    haystack = f"{text} {url}"
    combo = re.search(r"\b(20\d{2})\s*[-/]\s*(20\d{2})\b", haystack)
    if combo:
        return f"{combo.group(1)}-{combo.group(2)}"
    match = re.search(r"\b(20\d{2})\b", haystack)
    return match.group(1) if match else ""


def infer_artifact_type(url: str, link_text: str) -> str:
    lower = f"{url} {link_text}".lower()
    if ".pdf" in lower:
        return "pdf"
    if "statistics?sub=" in lower or "plastic-surgery-statistics" in lower:
        return "html_year_page"
    return "html_link"


def infer_topic(link_text: str, url: str) -> str:
    lower = f"{link_text} {url}".lower()
    if "complete" in lower or "statistics-report" in lower:
        return "complete_report"
    if "average" in lower or "cost" in lower:
        return "average_fee"
    if "region" in lower:
        return "regional_distribution"
    if "age" in lower or "ages-" in lower:
        return "age_distribution"
    if re.search(r"\b(women|woman|female|females|men|male|males)\b", lower):
        return "gender_distribution"
    if "minimally" in lower:
        return "minimally_invasive"
    if "cosmetic" in lower:
        return "cosmetic_procedure"
    if "reconstructive" in lower:
        return "reconstructive_procedure"
    if "procedural" in lower or "statistics" in lower:
        return "procedure_statistics"
    return "source_link"


def is_relevant_link(source_id: str, url: str, link_text: str) -> bool:
    lower = f"{url} {link_text}".lower()
    if source_id == "asps_plastic_surgery_statistics":
        return any(
            token in lower
            for token in [
                "plastic-surgery-statistics",
                "/documents/news/statistics/",
                "procedure-trends",
                "procedures-regions",
                "average-cost",
                "top-five",
            ]
        )
    if source_id == "aesthetic_society_statistics":
        return "theaestheticsociety" in lower and (
            "/media/statistics/" in lower or "procedural-statistics" in lower
        )
    return False


def normalize_url(page_url: str, href: str) -> str:
    href = safe_text(href)
    if not href or href.startswith(("mailto:", "tel:", "javascript:")):
        return ""
    if "plasticsurgery.org" in page_url.lower() and href.lower().startswith("documents/"):
        return urljoin("https://www.plasticsurgery.org/", href)
    return urljoin(page_url, href)


def source_pages(years: list[int]) -> list[SourcePage]:
    pages = [SourcePage("asps_plastic_surgery_statistics", "ASPS", ASPS_BASE, "latest")]
    for year in years:
        pages.append(
            SourcePage(
                "asps_plastic_surgery_statistics",
                "ASPS",
                f"{ASPS_BASE}?sub={quote_plus(f'{year} Plastic Surgery Statistics')}",
                str(year),
            )
        )
    pages.append(SourcePage("aesthetic_society_statistics", "The Aesthetic Society", AESTHETIC_SOCIETY_BASE, "latest"))
    return pages


def fetch_page(fetcher: Fetcher, source: SourcePage) -> tuple[Any | None, dict[str, str]]:
    try:
        page = fetcher.get(source.url, timeout=35, follow_redirects=True)
    except Exception as exc:
        return None, {"status": "fetch_failed", "note": str(exc)}
    return page, {
        "status": "fetched" if getattr(page, "status", 0) and int(page.status) < 400 else "fetch_http_error",
        "http_status": str(getattr(page, "status", "")),
        "content_type": safe_text(getattr(page, "headers", {}).get("content-type", "")),
    }


def page_title(page: Any) -> str:
    title = page.css_first("title") if page else None
    return safe_text(getattr(title, "text", "")) if title else ""


def page_links(page: Any, source: SourcePage) -> list[dict[str, str]]:
    rows = []
    seen: set[tuple[str, str]] = set()
    if page is None:
        return rows
    for anchor in page.css("a"):
        href = normalize_url(source.url, anchor.attrib.get("href") or "")
        text = safe_text(getattr(anchor, "text", ""))
        if not href or not is_relevant_link(source.source_id, href, text):
            continue
        key = (href, text)
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "source_id": source.source_id,
                "source_org": source.source_org,
                "source_page": source.url,
                "source_page_title": "",
                "link_text": text,
                "url": href,
                "canonical_url": href.split("#", 1)[0],
                "year": infer_year(text, href),
                "artifact_type": infer_artifact_type(href, text),
                "topic": infer_topic(text, href),
                "status": "discovered",
                "http_status": "",
                "content_type": "",
                "local_path": "",
                "sha256": "",
                "bytes": "",
                "captured_at": "",
                "note": "",
            }
        )
    return rows


def local_path_for(row: dict[str, str]) -> Path:
    parsed = urlparse(row["canonical_url"])
    suffix = Path(parsed.path).suffix.lower()
    if suffix not in {".pdf", ".html", ".htm"}:
        suffix = ".html"
    year = slugify(row.get("year") or "unknown-year")
    topic = slugify(row.get("topic") or "source")
    name_source = row.get("link_text") or Path(parsed.path).stem or parsed.netloc
    filename = f"{year}__{topic}__{slugify(name_source)}{suffix}"
    return RAW_DIR / row["source_id"] / filename


def download_bytes(url: str) -> tuple[bytes, str, str]:
    request = Request(url, headers=REQUEST_HEADERS)
    with urlopen(request, timeout=60) as response:
        content_type = response.headers.get("content-type", "")
        final_url = response.geturl()
        return response.read(), safe_text(content_type), final_url


def download_artifact(row: dict[str, str]) -> dict[str, str]:
    if row["artifact_type"] != "pdf":
        return row
    target = local_path_for(row)
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        body, content_type, final_url = download_bytes(row["canonical_url"])
    except Exception as exc:
        row.update({"status": "download_failed", "note": str(exc), "captured_at": now_iso()})
        return row
    target.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    row.update(
        {
            "status": "downloaded",
            "content_type": content_type,
            "url": final_url,
            "local_path": str(target.relative_to(PROJECT_DIR)),
            "sha256": digest,
            "bytes": str(len(body)),
            "captured_at": now_iso(),
        }
    )
    return row


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in FIELDS})


def summarize(rows: list[dict[str, str]], page_rows: list[dict[str, str]]) -> dict[str, Any]:
    by_source: dict[str, dict[str, Any]] = {}
    for row in rows:
        source = row["source_id"]
        item = by_source.setdefault(
            source,
            {
                "source_id": source,
                "source_org": row["source_org"],
                "discovered_links": 0,
                "downloaded_pdfs": 0,
                "download_failures": 0,
                "years": set(),
                "topics": set(),
            },
        )
        item["discovered_links"] += 1
        if row["status"] == "downloaded":
            item["downloaded_pdfs"] += 1
        if row["status"] == "download_failed":
            item["download_failures"] += 1
        if row.get("year"):
            item["years"].add(row["year"])
        if row.get("topic"):
            item["topics"].add(row["topic"])
    for item in by_source.values():
        item["years"] = sorted(item["years"])
        item["topics"] = sorted(item["topics"])
    return {
        "status": "ok",
        "generated_at": now_iso(),
        "inventory_path": str(INVENTORY_PATH),
        "raw_dir": str(RAW_DIR),
        "page_fetches": page_rows,
        "sources": sorted(by_source.values(), key=lambda item: item["source_id"]),
        "total_links": len(rows),
        "total_downloaded_pdfs": sum(1 for row in rows if row["status"] == "downloaded"),
        "total_download_failures": sum(1 for row in rows if row["status"] == "download_failed"),
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Collect ASPS and Aesthetic Society official statistics sources.")
    parser.add_argument("--years", default="2020,2021,2022,2023,2024", help="Comma-separated ASPS years to probe.")
    parser.add_argument("--no-download", action="store_true", help="Only inventory links; do not download PDFs.")
    parser.add_argument("--clean", action="store_true", help="Clear this script's raw output directory before downloading.")
    args = parser.parse_args()

    years = sorted({int(part) for part in re.findall(r"20\d{2}", args.years)})
    if args.clean and RAW_DIR.exists():
        resolved_raw = RAW_DIR.resolve()
        resolved_data = (PROJECT_DIR / "data" / "commercial_sources").resolve()
        if resolved_data not in resolved_raw.parents:
            raise SystemExit(f"Refusing to clean unexpected path: {resolved_raw}")
        shutil.rmtree(resolved_raw)
    fetcher = Fetcher()
    rows: list[dict[str, str]] = []
    page_rows: list[dict[str, str]] = []
    seen_urls: set[str] = set()

    for source in source_pages(years):
        page, status = fetch_page(fetcher, source)
        title = page_title(page)
        page_rows.append(
            {
                "source_id": source.source_id,
                "source_org": source.source_org,
                "url": source.url,
                "year": source.year,
                "title": title,
                **status,
            }
        )
        for row in page_links(page, source):
            row["source_page_title"] = title
            key = f"{row['source_id']} {row['canonical_url']} {row.get('link_text')}"
            if key in seen_urls:
                continue
            seen_urls.add(key)
            if not args.no_download:
                row = download_artifact(row)
            rows.append(row)

    rows.sort(key=lambda item: (item["source_id"], item["year"], item["topic"], item["canonical_url"], item["link_text"]))
    write_csv(rows, INVENTORY_PATH)
    summary = summarize(rows, page_rows)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["total_download_failures"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
