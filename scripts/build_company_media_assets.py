#!/usr/bin/env python3
"""Build official website, media asset, and product-specification indexes.

The workbook seed can name a company, while commercial product facts often live
on a different official surface: listed-parent investor site, operating company
site, brand site, or product-line site. This script keeps those layers separate
instead of collapsing everything to one company URL.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import mimetypes
import re
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from build_data import (
    COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH,
    DATA_DIR,
    PRODUCT_FAMILY_MASTER_PATH,
    PRODUCT_SKU_MASTER_PATH,
    PROJECT_DIR,
    stable_id,
)


OFFICIAL_WEBSITE_MASTER_PATH = DATA_DIR / "official_website_master.csv"
COMPANY_OFFICIAL_WEBSITE_PATH = DATA_DIR / "company_official_website.csv"
COMPANY_MEDIA_ASSET_INDEX_PATH = DATA_DIR / "company_media_asset_index.csv"
PRODUCT_SPECIFICATION_EVIDENCE_PATH = DATA_DIR / "product_specification_evidence.csv"
ASSET_ROOT = PROJECT_DIR / "assets" / "official_media"

BAD_DOMAINS = {
    "wikipedia.org",
    "linkedin.com",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "finance.yahoo.com",
    "marketscreener.com",
    "pitchbook.com",
    "crunchbase.com",
    "bloomberg.com",
    "reuters.com",
    "cnbc.com",
    "nasdaq.com",
    "stockanalysis.com",
    "seekingalpha.com",
    "tipranks.com",
    "simplywall.st",
    "gurufocus.com",
}

IMAGE_EXT_BY_MIME = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/svg+xml": ".svg",
    "image/x-icon": ".ico",
    "image/vnd.microsoft.icon": ".ico",
}

WEBSITE_FIELDS = [
    "website_id",
    "entity_scope",
    "company_id",
    "company",
    "listed_parent_company",
    "related_company_id",
    "related_company",
    "brand",
    "product_family_id",
    "product_family",
    "product_id",
    "standard_product_name",
    "official_website_url",
    "official_domain",
    "source_evidence_id",
    "source_url",
    "source_title",
    "source_query_type",
    "confidence",
    "official_candidate",
    "asset_folder",
    "captured_at",
    "review_status",
    "relationship_notes",
]

COMPANY_WEBSITE_FIELDS = [
    "company_id",
    "company",
    "listed_parent_url",
    "listed_parent_domain",
    "operating_company_url",
    "operating_company_domain",
    "brand_website_urls",
    "product_line_page_count",
    "product_line_page_urls",
    "primary_official_url",
    "primary_official_domain",
    "source_evidence_id",
    "source_url",
    "source_title",
    "confidence",
    "official_candidate",
    "asset_folder",
    "captured_at",
    "review_status",
    "notes",
]

ASSET_FIELDS = [
    "asset_id",
    "entity_scope",
    "website_id",
    "company_id",
    "company",
    "brand",
    "product_family_id",
    "product_family",
    "asset_type",
    "asset_role",
    "source_page_url",
    "image_url",
    "local_path",
    "file_name",
    "mime_type",
    "file_bytes",
    "captured_at",
    "confidence",
    "review_status",
    "notes",
]

SPEC_FIELDS = [
    "spec_id",
    "company_id",
    "company",
    "brand",
    "product_family_id",
    "product_family",
    "product_id",
    "standard_product_name",
    "source_page_url",
    "source_title",
    "source_evidence_id",
    "source_query_type",
    "spec_name",
    "spec_value",
    "spec_unit",
    "spec_category",
    "evidence_excerpt",
    "captured_at",
    "confidence",
    "review_status",
    "notes",
]

SPEC_PATTERNS: list[tuple[str, str, re.Pattern[str]]] = [
    (
        "volume_or_fill",
        "volume_packaging",
        re.compile(r"\b\d+(?:\.\d+)?\s?(?:mL|ml|cc|syringes?|vials?|ampoules?)\b", re.I),
    ),
    (
        "dose_or_unit",
        "dose_strength",
        re.compile(r"\b\d+(?:\.\d+)?\s?(?:U|unit|units|IU|mg|mcg|g)\b", re.I),
    ),
    (
        "energy_wavelength",
        "device_energy",
        re.compile(r"\b\d+(?:\.\d+)?\s?(?:nm|mm|cm|Hz|kHz|MHz|W|J/cm2|J/cm²)\b", re.I),
    ),
    (
        "composition",
        "material_or_ingredient",
        re.compile(
            r"\b(?:hyaluronic acid|cross-linked HA|HA\b|lidocaine|botulinum toxin|"
            r"daxibotulinumtoxinA|onabotulinumtoxinA|calcium hydroxylapatite|CaHA|"
            r"poly-l-lactic acid|PLLA|polycaprolactone|PCL|PMMA|PDLLA|"
            r"Nd:YAG|CO2|diode|IPL|radiofrequency|RF|HIFU|ultrasound|cryolipolysis)\b",
            re.I,
        ),
    ),
    (
        "packaging_or_sku",
        "packaging",
        re.compile(r"\b(?:packaging|package|box|carton|syringe|vial|needle|cannula|SKU|model)\b[^.;\n]{0,160}", re.I),
    ),
    (
        "certification_claim",
        "commercial_certification",
        re.compile(r"\b(?:CE marked|CE mark|FDA cleared|510\(k\)|MDR|ISO 13485|MDSAP|TGA|ARTG|ANVISA)\b", re.I),
    ),
]


def norm(value: Any) -> str:
    return "" if value is None else str(value).strip()


def norm_ascii(value: Any) -> str:
    text = unicodedata.normalize("NFKD", norm(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return text.lower()


def compact(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", norm_ascii(value))


def domain(url: str) -> str:
    host = urllib.parse.urlparse(url).netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def base_url_for(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/"


def is_bad_domain(host: str) -> bool:
    return any(host == bad or host.endswith("." + bad) for bad in BAD_DOMAINS)


def slugify(value: str) -> str:
    text = re.sub(r"[^A-Za-z0-9]+", "_", norm_ascii(value)).strip("_").lower()
    return text[:70] or "entity"


def read_csv(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_official_evidence() -> list[dict[str, Any]]:
    if not COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH.exists():
        return []
    rows = []
    for line in COMPANY_OFFICIAL_SOURCE_EVIDENCE_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


class CsvSink:
    def __init__(self, path: Path, fieldnames: list[str], append: bool = False) -> None:
        self.path = path
        self.fieldnames = fieldnames
        has_existing = append and path.exists() and path.stat().st_size > 0
        self.handle = path.open("a" if has_existing else "w", encoding="utf-8-sig", newline="")
        self.writer = csv.DictWriter(self.handle, fieldnames=fieldnames, extrasaction="ignore")
        if not has_existing:
            self.writer.writeheader()
        self.count = 0

    def write(self, row: dict[str, Any]) -> None:
        self.writer.writerow(row)
        self.handle.flush()
        self.count += 1

    def close(self) -> None:
        self.handle.close()


def family_aliases(item: dict[str, Any]) -> list[str]:
    raw_names = []
    for field in ["brand", "product_family", "sku_candidate_names"]:
        raw_names.extend(re.split(r"[/,;|()（）]+", norm(item.get(field))))
    aliases = []
    seen = set()
    for name in raw_names:
        cleaned = re.sub(r"\b(?:collection|series|system|device|injectable|filler)\b", "", norm_ascii(name), flags=re.I).strip()
        if len(compact(cleaned)) < 3:
            continue
        key = compact(cleaned)
        if key not in seen:
            seen.add(key)
            aliases.append(cleaned)
    return aliases


def load_family_indexes() -> tuple[dict[str, list[dict[str, Any]]], dict[str, list[dict[str, Any]]]]:
    families = read_csv(PRODUCT_FAMILY_MASTER_PATH)
    skus = read_csv(PRODUCT_SKU_MASTER_PATH)
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    sku_by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in families:
        item["aliases"] = family_aliases(item)
        by_company[norm(item.get("company_id"))].append(item)
    for item in skus:
        sku_by_family[norm(item.get("product_family_id"))].append(item)
    return by_company, sku_by_family


def match_family_rows(row: dict[str, Any], family_by_company: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    company_id = norm(row.get("company_id"))
    if not company_id:
        return []
    direct_family_id = norm(row.get("product_family_id"))
    if direct_family_id:
        direct = [
            item
            for item in family_by_company.get(company_id, [])
            if norm(item.get("product_family_id")) == direct_family_id
        ]
        if direct:
            return direct[:1]
    text = compact(" ".join([norm(row.get("title")), norm(row.get("url")), norm(row.get("evidence_excerpt")), norm(row.get("raw_text"))[:2500]]))
    matches = []
    for item in family_by_company.get(company_id, []):
        score = 0
        for alias in item.get("aliases", []):
            key = compact(alias)
            if key and key in text:
                score += max(2, min(8, len(key) // 3))
        brand_key = compact(item.get("brand"))
        if brand_key and brand_key in text:
            score += 3
        family_key = compact(item.get("product_family"))
        if family_key and family_key in text:
            score += 4
        if score:
            matches.append((score, item))
    matches.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _score, item in matches[:4]]


def scope_folder(row: dict[str, Any]) -> Path:
    scope = row["entity_scope"]
    if scope == "listed_parent":
        return ASSET_ROOT / "company" / slugify(row.get("listed_parent_company") or row.get("company"))
    if scope in {"brand", "operating_company"}:
        return ASSET_ROOT / scope / slugify(row.get("brand") or row.get("company"))
    company_slug = slugify(row.get("company"))
    family_slug = slugify(row.get("product_family") or row.get("brand") or row.get("standard_product_name"))
    return ASSET_ROOT / "product_line" / company_slug / family_slug


def official_candidate_allowed(row: dict[str, Any]) -> bool:
    candidate = norm(row.get("official_candidate"))
    confidence = norm(row.get("confidence"))
    query_type = norm(row.get("query_type"))
    host_key = compact(domain(norm(row.get("url"))))
    company_key = compact(row.get("company"))
    parent_key = compact(infer_parent_company(row))
    evidence_text = compact(" ".join([norm(row.get("title")), norm(row.get("url")), norm(row.get("evidence_excerpt")), norm(row.get("raw_text"))[:1500]]))
    brand_key = compact(row.get("brand"))
    family_key = compact(row.get("product_family"))
    if candidate in {"likely", "possible"}:
        return True
    if confidence in {
        "official_domain_candidate",
        "company_official_search_candidate",
        "product_official_domain_candidate",
        "product_official_search_candidate",
        "brand_official_search_candidate",
    }:
        return True
    if query_type in {"product_official_page", "product_ifu_labeling", "product_certificate_registration"}:
        return bool((family_key and family_key in evidence_text) or (brand_key and brand_key in host_key + evidence_text))
    if query_type == "investor_relations_or_annual_report" and not is_bad_domain(domain(norm(row.get("url")))):
        return bool((company_key and company_key in host_key) or (parent_key and parent_key in host_key))
    return False


def infer_parent_company(row: dict[str, Any]) -> str:
    title = norm(row.get("title"))
    excerpt = norm(row.get("evidence_excerpt"))
    company = norm(row.get("company"))
    for candidate in ["AbbVie", "Galderma", "Merz", "Cynosure", "Hugel", "Ipsen", "Evolus"]:
        if candidate.lower() in f"{title} {excerpt}".lower():
            return candidate
    return company


def website_row(
    row: dict[str, Any],
    entity_scope: str,
    captured_at: str,
    product_family: dict[str, Any] | None = None,
    brand_only: str = "",
) -> dict[str, Any]:
    source_url = norm(row.get("url"))
    host = domain(source_url)
    brand = norm(product_family.get("brand")) if product_family else brand_only
    family_id = norm(product_family.get("product_family_id")) if product_family else ""
    family_name = norm(product_family.get("product_family")) if product_family else ""
    page_url = source_url if entity_scope in {"brand", "product_line", "product"} else base_url_for(source_url)
    related_company = norm(row.get("company"))
    listed_parent = infer_parent_company(row) if entity_scope == "listed_parent" else ""
    item = {
        "website_id": stable_id("site", row.get("company_id"), entity_scope, host, brand, family_id, page_url),
        "entity_scope": entity_scope,
        "company_id": norm(row.get("company_id")),
        "company": norm(row.get("company")),
        "listed_parent_company": listed_parent,
        "related_company_id": norm(row.get("company_id")),
        "related_company": related_company,
        "brand": brand,
        "product_family_id": family_id,
        "product_family": family_name,
        "category_l1": norm(product_family.get("category_l1")) if product_family else "",
        "category_l2": norm(product_family.get("category_l2")) if product_family else "",
        "tech_type": norm(product_family.get("tech_type")) if product_family else "",
        "product_id": "",
        "standard_product_name": brand or family_name,
        "official_website_url": page_url,
        "official_domain": host,
        "source_evidence_id": norm(row.get("evidence_id")),
        "source_url": source_url,
        "source_title": norm(row.get("title")),
        "source_query_type": norm(row.get("query_type")),
        "confidence": norm(row.get("confidence")),
        "official_candidate": norm(row.get("official_candidate")),
        "asset_folder": "",
        "captured_at": captured_at,
        "review_status": "candidate",
        "relationship_notes": "",
    }
    item["asset_folder"] = str(scope_folder(item).relative_to(PROJECT_DIR))
    if entity_scope == "listed_parent":
        item["relationship_notes"] = "Parent/listed/investor surface. Do not use as product portfolio unless product evidence also points here."
    elif entity_scope == "product_line":
        item["relationship_notes"] = "Official page matched to a product family. Use for commercial product facts/specs; registration facts still require regulator evidence."
    elif entity_scope == "brand":
        item["relationship_notes"] = "Brand-level official surface. Some products under the brand may require separate product-line pages."
    else:
        item["relationship_notes"] = "Operating-company or product-portfolio official surface."
    return item


def build_website_master(evidence_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    family_by_company, _sku_by_family = load_family_indexes()
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    rows: dict[str, dict[str, Any]] = {}
    domain_counter: Counter[tuple[str, str]] = Counter()

    for raw in evidence_rows:
        source_url = norm(raw.get("url"))
        host = domain(source_url)
        if not source_url or not host or is_bad_domain(host) or not official_candidate_allowed(raw):
            continue
        query_type = norm(raw.get("query_type"))
        family_matches = match_family_rows(raw, family_by_company)
        if query_type == "investor_relations_or_annual_report":
            candidates = [website_row(raw, "listed_parent", captured_at)]
        elif family_matches:
            candidates = [website_row(raw, "operating_company", captured_at)]
            candidates.extend(website_row(raw, "product_line", captured_at, product_family=item) for item in family_matches)
        else:
            candidates = [website_row(raw, "operating_company", captured_at)]

        for item in candidates:
            key = item["website_id"]
            if key not in rows:
                rows[key] = item
            else:
                current = rows[key]
                if norm(item.get("official_candidate")) == "likely" and norm(current.get("official_candidate")) != "likely":
                    rows[key] = item
            domain_counter[(item["company_id"], item["official_domain"])] += 1

    output = list(rows.values())
    output.sort(
        key=lambda item: (
            item["company"],
            {"operating_company": 0, "brand": 1, "product_line": 2, "listed_parent": 3, "product": 4}.get(item["entity_scope"], 9),
            item["brand"],
            item["product_family"],
            item["official_domain"],
        )
    )
    return output


def first_by_scope(rows: list[dict[str, Any]], scope: str) -> dict[str, Any] | None:
    candidates = [row for row in rows if row.get("entity_scope") == scope]
    if not candidates:
        return None
    candidates.sort(key=site_rank)
    return candidates[0]


def site_rank(row: dict[str, Any]) -> tuple[Any, ...]:
    host_key = compact(row.get("official_domain"))
    company_key = compact(row.get("company"))
    brand_key = compact(row.get("brand"))
    parent_key = compact(row.get("listed_parent_company"))
    expected_keys = [key for key in [brand_key, company_key, parent_key] if key]
    direct_domain_match = any(key in host_key for key in expected_keys)
    return (
        norm(row.get("official_candidate")) != "likely",
        norm(row.get("confidence")) != "official_domain_candidate",
        not direct_domain_match,
        not norm(row.get("official_domain")).endswith(".com"),
        "investor" in host_key and row.get("entity_scope") != "listed_parent",
        len(norm(row.get("official_website_url"))),
    )


def build_company_website_view(websites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in websites:
        grouped[norm(row.get("company_id"))].append(row)

    output = []
    for company_id, rows in grouped.items():
        operating = first_by_scope(rows, "operating_company")
        parent = first_by_scope(rows, "listed_parent")
        primary = operating or first_by_scope(rows, "product_line") or parent or rows[0]
        product_pages = []
        brand_pages = []
        for row in rows:
            if row["entity_scope"] == "product_line":
                product_pages.append(row["official_website_url"])
            elif row["entity_scope"] == "brand":
                brand_pages.append(row["official_website_url"])
        product_pages = sorted(dict.fromkeys(product_pages))
        brand_pages = sorted(dict.fromkeys(brand_pages))
        output.append(
            {
                "company_id": company_id,
                "company": primary.get("company"),
                "listed_parent_url": parent.get("official_website_url") if parent else "",
                "listed_parent_domain": parent.get("official_domain") if parent else "",
                "operating_company_url": operating.get("official_website_url") if operating else "",
                "operating_company_domain": operating.get("official_domain") if operating else "",
                "brand_website_urls": "; ".join(brand_pages[:20]),
                "product_line_page_count": len(product_pages),
                "product_line_page_urls": "; ".join(product_pages[:30]),
                "primary_official_url": primary.get("official_website_url"),
                "primary_official_domain": primary.get("official_domain"),
                "source_evidence_id": primary.get("source_evidence_id"),
                "source_url": primary.get("source_url"),
                "source_title": primary.get("source_title"),
                "confidence": primary.get("confidence"),
                "official_candidate": primary.get("official_candidate"),
                "asset_folder": str((ASSET_ROOT / "company" / slugify(primary.get("company"))).relative_to(PROJECT_DIR)),
                "captured_at": captured_at,
                "review_status": "candidate",
                "notes": "Derived company-level view. Use Official_Website_Master for parent/brand/product-line separation.",
            }
        )
    output.sort(key=lambda row: norm(row.get("company")))
    return output


class MediaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self.meta: list[dict[str, str]] = []
        self.images: list[dict[str, str]] = []
        self.text_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {k.lower(): v or "" for k, v in attrs}
        if tag.lower() == "link":
            self.links.append(data)
        elif tag.lower() == "meta":
            self.meta.append(data)
        elif tag.lower() == "img":
            self.images.append(data)

    def handle_data(self, data: str) -> None:
        text = norm(html.unescape(data))
        if text:
            self.text_chunks.append(text)

    def page_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.text_chunks)).strip()


def fetch_text(url: str, timeout: int) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GlobalAestheticsAssetBot/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = response.read(2_000_000)
    return raw.decode("utf-8", errors="replace")


def image_candidates(page_url: str, html_text: str, asset_role: str) -> list[dict[str, str]]:
    parser = MediaParser()
    parser.feed(html_text)
    candidates: list[dict[str, str]] = []
    for link in parser.links:
        rel = link.get("rel", "").lower()
        href = link.get("href", "")
        if href and any(token in rel for token in ["icon", "apple-touch-icon", "mask-icon"]):
            candidates.append({"image_url": urllib.parse.urljoin(page_url, href), "asset_type": "logo_candidate", "asset_role": "favicon_or_touch_icon", "hint": rel})
    for meta in parser.meta:
        key = (meta.get("property") or meta.get("name") or "").lower()
        content = meta.get("content", "")
        if content and key in {"og:image", "og:image:url", "twitter:image", "twitter:image:src"}:
            candidates.append({"image_url": urllib.parse.urljoin(page_url, content), "asset_type": "product_image_candidate" if asset_role in {"product_line", "product"} else "brand_image_candidate", "asset_role": f"{asset_role}_meta_image", "hint": key})
    for image in parser.images:
        src = image.get("src") or image.get("data-src") or image.get("data-lazy-src") or ""
        alt = f"{image.get('alt', '')} {image.get('title', '')}".lower()
        klass = image.get("class", "").lower()
        if not src:
            continue
        if "logo" in alt or "logo" in klass:
            candidates.append({"image_url": urllib.parse.urljoin(page_url, src), "asset_type": "logo_candidate", "asset_role": f"{asset_role}_logo_img", "hint": alt.strip() or klass})
        elif asset_role in {"product_line", "product"} and any(token in alt or token in klass for token in ["product", "device", "filler", "laser", "system", "botox", "juvederm"]):
            candidates.append({"image_url": urllib.parse.urljoin(page_url, src), "asset_type": "product_image_candidate", "asset_role": "product_page_img", "hint": alt.strip() or klass})
    seen = set()
    output = []
    for item in candidates:
        key = item["image_url"].split("#", 1)[0]
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output[:10]


def download_image(url: str, target_dir: Path, file_stem: str, timeout: int, max_bytes: int) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 GlobalAestheticsAssetBot/0.2"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
        raw = response.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError(f"image exceeds max_bytes={max_bytes}")
    if not content_type.startswith("image/"):
        guessed_type = mimetypes.guess_type(urllib.parse.urlparse(url).path)[0] or ""
        if not guessed_type.startswith("image/"):
            raise ValueError(f"not an image: {content_type or 'unknown'}")
        content_type = guessed_type
    ext = IMAGE_EXT_BY_MIME.get(content_type) or Path(urllib.parse.urlparse(url).path).suffix[:8] or ".img"
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    file_name = f"{file_stem}_{digest}{ext}"
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / file_name
    path.write_bytes(raw)
    return {"local_path": str(path.relative_to(PROJECT_DIR)), "file_name": file_name, "mime_type": content_type, "file_bytes": len(raw)}


def error_asset_row(website: dict[str, Any], page_url: str, captured_at: str, exc: Exception) -> dict[str, Any]:
    return {
        "asset_id": stable_id("asset_error", website.get("website_id"), page_url),
        "entity_scope": website.get("entity_scope"),
        "website_id": website.get("website_id"),
        "company_id": website.get("company_id"),
        "company": website.get("company"),
        "brand": website.get("brand"),
        "product_family_id": website.get("product_family_id"),
        "product_family": website.get("product_family"),
        "asset_type": "page_fetch_error",
        "asset_role": website.get("entity_scope"),
        "source_page_url": page_url,
        "image_url": "",
        "local_path": "",
        "file_name": "",
        "mime_type": "",
        "file_bytes": "",
        "captured_at": captured_at,
        "confidence": "fetch_error",
        "review_status": "error",
        "notes": str(exc)[:500],
    }


def marker_asset_row(website: dict[str, Any], page_url: str, captured_at: str, status: str, notes: str) -> dict[str, Any]:
    return {
        "asset_id": stable_id("asset_marker", website.get("website_id"), status),
        "entity_scope": website.get("entity_scope"),
        "website_id": website.get("website_id"),
        "company_id": website.get("company_id"),
        "company": website.get("company"),
        "brand": website.get("brand"),
        "product_family_id": website.get("product_family_id"),
        "product_family": website.get("product_family"),
        "asset_type": "page_scan_marker",
        "asset_role": website.get("entity_scope"),
        "source_page_url": page_url,
        "image_url": "",
        "local_path": "",
        "file_name": "",
        "mime_type": "",
        "file_bytes": "",
        "captured_at": captured_at,
        "confidence": "official_site_scan_marker",
        "review_status": status,
        "notes": notes[:500],
    }


def anchor_terms(source: dict[str, Any]) -> list[str]:
    terms = []
    for field in ["product_family", "brand", "standard_product_name"]:
        for part in re.split(r"[/,;|()（）]+", norm(source.get(field))):
            part = norm(part)
            if len(compact(part)) >= 3:
                terms.append(part)
    output = []
    seen = set()
    for term in terms:
        key = compact(term)
        if key and key not in seen:
            seen.add(key)
            output.append(term)
    return output


def relevant_text_for_source(source: dict[str, Any], text: str) -> str:
    terms = anchor_terms(source)
    if not terms:
        return text[:12000]
    normalized_text = norm_ascii(text)
    windows = []
    for term in terms:
        term_key = norm_ascii(term)
        if not term_key:
            continue
        start = 0
        while True:
            pos = normalized_text.find(term_key, start)
            if pos < 0:
                break
            windows.append(text[max(0, pos - 700) : min(len(text), pos + len(term) + 700)])
            start = pos + len(term_key)
            if len(windows) >= 8:
                break
    if not windows:
        return ""
    return " ".join(windows)


def spec_value_matches_product_context(source: dict[str, Any], value: str) -> bool:
    context_text = norm_ascii(
        " ".join(
            [
                norm(source.get("brand")),
                norm(source.get("product_family")),
                norm(source.get("category_l1")),
                norm(source.get("category_l2")),
                norm(source.get("tech_type")),
                norm(source.get("standard_product_name")),
            ]
        )
    )
    context = compact(context_text)
    context_words = set(re.findall(r"[a-z0-9]+", context_text))
    value_key = compact(value)
    def context_has(term: str) -> bool:
        term_key = compact(term)
        if not term_key:
            return False
        if len(term_key) <= 3:
            return term_key in context_words
        return term_key in context

    guarded_terms = [
        (
            ["onabotulinumtoxina", "daxibotulinumtoxina", "botulinumtoxin"],
            ["botox", "botulinum", "toxin", "neurotoxin", "daxxify", "dysport", "xeomin", "nabota", "botulax", "letibotulinum", "prabotulinum"],
        ),
        (
            ["hyaluronicacid", "crosslinkedha"],
            ["ha", "hyaluronic", "hyaluronicacid", "crosslinkedha", "juvederm", "restylane", "skinvive", "volite", "teoxane", "rha", "harmonyca", "hybrid", "neauvia", "stimulate"],
        ),
        (
            ["ha"],
            ["ha", "hyaluronic", "hyaluronicacid", "crosslinkedha", "juvederm", "restylane", "skinvive", "volite", "teoxane", "rha", "harmonyca", "hybrid", "neauvia", "stimulate"],
        ),
        (
            ["calciumhydroxylapatite", "caha"],
            ["caha", "calciumhydroxylapatite", "hydroxylapatite", "radiesse", "facetem", "harmonyca", "stimulate", "biostimulator"],
        ),
        (
            ["polycaprolactone", "pcl", "polyllacticacid", "plla", "pdlla", "pmma"],
            ["pcl", "plla", "pdlla", "pmma", "biostimulator", "ellanse", "sculptra", "lanluma"],
        ),
    ]
    for value_terms, required_context in guarded_terms:
        if any(term in value_key for term in value_terms):
            return any(context_has(term) for term in required_context)
    return True


def spec_rows_from_text(source: dict[str, Any], text: str, source_kind: str) -> list[dict[str, Any]]:
    rows = []
    source_text = re.sub(r"\s+", " ", text)
    if not source_text:
        return rows
    source_text = relevant_text_for_source(source, source_text)
    if not source_text:
        return rows
    family_name = norm(source.get("product_family"))
    brand = norm(source.get("brand"))
    captured_at = source.get("captured_at") or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    for spec_name, category, pattern in SPEC_PATTERNS:
        seen_values = set()
        for match in pattern.finditer(source_text[:12000]):
            value = norm(match.group(0))
            key = compact(value)
            if not key or key in seen_values:
                continue
            if not spec_value_matches_product_context(source, value):
                continue
            seen_values.add(key)
            start = max(0, match.start() - 160)
            end = min(len(source_text), match.end() + 160)
            excerpt = source_text[start:end].strip()
            unit_match = re.search(r"\b(mL|ml|cc|U|unit|units|IU|mg|mcg|g|nm|mm|cm|Hz|kHz|MHz|W|J/cm2|J/cm²)\b", value, re.I)
            rows.append(
                {
                    "spec_id": stable_id("spec", source.get("website_id") or source.get("source_evidence_id"), spec_name, value),
                    "company_id": source.get("company_id"),
                    "company": source.get("company"),
                    "brand": brand,
                    "product_family_id": source.get("product_family_id"),
                    "product_family": family_name,
                    "product_id": source.get("product_id") or "",
                    "standard_product_name": source.get("standard_product_name") or brand or family_name,
                    "source_page_url": source.get("official_website_url") or source.get("source_url") or "",
                    "source_title": source.get("source_title") or "",
                    "source_evidence_id": source.get("source_evidence_id") or "",
                    "source_query_type": source.get("source_query_type") or source_kind,
                    "spec_name": spec_name,
                    "spec_value": value,
                    "spec_unit": unit_match.group(1) if unit_match else "",
                    "spec_category": category,
                    "evidence_excerpt": excerpt[:600],
                    "captured_at": captured_at,
                    "confidence": "official_site_spec_candidate" if source_kind == "website_html" else "official_search_excerpt_spec_candidate",
                    "review_status": "candidate",
                    "notes": "Specification candidate from official page/catalog text. Treat as commercial/spec fact; registration claims still need regulator evidence.",
                }
            )
            if len(rows) >= 12:
                break
    return rows


def build_specs_from_evidence(evidence_rows: list[dict[str, Any]], websites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    family_by_company, _sku_by_family = load_family_indexes()
    website_by_evidence: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for website in websites:
        website_by_evidence[norm(website.get("source_evidence_id"))].append(website)
    rows_by_id: dict[str, dict[str, Any]] = {}
    for raw in evidence_rows:
        if norm(raw.get("query_type")) not in {
            "official_product_portfolio",
            "official_ifu_catalog",
            "product_official_page",
            "product_ifu_labeling",
            "product_certificate_registration",
        }:
            continue
        if not official_candidate_allowed(raw):
            continue
        text = " ".join([norm(raw.get("title")), norm(raw.get("evidence_excerpt")), norm(raw.get("raw_text"))[:3500]])
        sources = [row for row in website_by_evidence.get(norm(raw.get("evidence_id")), []) if row.get("entity_scope") == "product_line"]
        if not sources:
            for family in match_family_rows(raw, family_by_company):
                sources.append(website_row(raw, "product_line", datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"), product_family=family))
        for source in sources[:4]:
            for item in spec_rows_from_text(source, text, "official_evidence_excerpt"):
                rows_by_id[item["spec_id"]] = item
    return list(rows_by_id.values())


def build_assets_and_page_specs(
    websites: list[dict[str, Any]],
    limit_websites: int,
    timeout: int,
    max_images_per_site: int,
    max_pages_per_site: int,
    max_page_fetches: int,
    sleep_seconds: float,
    force_assets: bool,
    skip_image_downloads: bool,
    download_logos_only: bool,
) -> tuple[int, list[dict[str, Any]]]:
    captured_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    existing_assets = read_csv(COMPANY_MEDIA_ASSET_INDEX_PATH)
    existing_asset_ids = {norm(row.get("asset_id")) for row in existing_assets if norm(row.get("asset_id"))}
    processed_website_ids = {norm(row.get("website_id")) for row in existing_assets if norm(row.get("website_id"))}
    asset_candidates = websites if force_assets else [row for row in websites if norm(row.get("website_id")) not in processed_website_ids]
    selected = asset_candidates[:limit_websites]
    ASSET_ROOT.mkdir(parents=True, exist_ok=True)
    sink = CsvSink(COMPANY_MEDIA_ASSET_INDEX_PATH, ASSET_FIELDS, append=bool(existing_assets))
    page_specs: dict[str, dict[str, Any]] = {}
    page_fetches = 0
    written_ids: set[str] = set(existing_asset_ids)

    def write_asset(row: dict[str, Any]) -> bool:
        asset_id = norm(row.get("asset_id"))
        if asset_id and asset_id in written_ids:
            return False
        sink.write(row)
        if asset_id:
            written_ids.add(asset_id)
        return True

    try:
        for website in selected:
            if max_page_fetches and page_fetches >= max_page_fetches:
                break
            site_written = False
            root = PROJECT_DIR / website["asset_folder"]
            for subdir in ["logo", "products", "raw", "metadata"]:
                (root / subdir).mkdir(parents=True, exist_ok=True)
            (root / "metadata" / "website.json").write_text(json.dumps(website, ensure_ascii=False, indent=2), encoding="utf-8")
            page_url = website.get("official_website_url") or website.get("source_url")
            pages = [page_url]
            source_url = website.get("source_url")
            if source_url and source_url not in pages:
                pages.append(source_url)
            pages = [url for url in pages if url][:max_pages_per_site]
            if not pages:
                write_asset(
                    marker_asset_row(
                        website,
                        "",
                        captured_at,
                        "processed_no_url",
                        "No fetchable official_website_url or source_url was available for this official website candidate.",
                    )
                )
                continue
            added = 0
            for page in pages:
                if max_page_fetches and page_fetches >= max_page_fetches:
                    break
                page_fetches += 1
                try:
                    page_html = fetch_text(page, timeout)
                    parser = MediaParser()
                    parser.feed(page_html)
                    for item in spec_rows_from_text(website, parser.page_text(), "website_html"):
                        page_specs[item["spec_id"]] = item
                    candidates = [] if skip_image_downloads else image_candidates(page, page_html, website.get("entity_scope", "website"))
                    if download_logos_only:
                        candidates = [item for item in candidates if item.get("asset_type") == "logo_candidate"]
                except Exception as exc:  # noqa: BLE001
                    site_written = write_asset(error_asset_row(website, page, captured_at, exc)) or site_written
                    continue
                for candidate in candidates:
                    if added >= max_images_per_site:
                        break
                    asset_type = candidate["asset_type"]
                    target_dir = root / ("products" if asset_type == "product_image_candidate" else "logo")
                    try:
                        downloaded = download_image(candidate["image_url"], target_dir, asset_type, timeout, 3_500_000)
                        status = "downloaded"
                        notes = candidate.get("hint", "")
                    except Exception as exc:  # noqa: BLE001
                        downloaded = {"local_path": "", "file_name": "", "mime_type": "", "file_bytes": ""}
                        status = "download_failed"
                        notes = str(exc)[:500]
                    site_written = write_asset(
                        {
                            "asset_id": stable_id("asset", website.get("website_id"), candidate["image_url"], asset_type),
                            "entity_scope": website.get("entity_scope"),
                            "website_id": website.get("website_id"),
                            "company_id": website.get("company_id"),
                            "company": website.get("company"),
                            "brand": website.get("brand"),
                            "product_family_id": website.get("product_family_id"),
                            "product_family": website.get("product_family"),
                            "asset_type": asset_type,
                            "asset_role": candidate["asset_role"],
                            "source_page_url": page,
                            "image_url": candidate["image_url"],
                            "local_path": downloaded["local_path"],
                            "file_name": downloaded["file_name"],
                            "mime_type": downloaded["mime_type"],
                            "file_bytes": downloaded["file_bytes"],
                            "captured_at": captured_at,
                            "confidence": "official_site_asset_candidate",
                            "review_status": status,
                            "notes": notes,
                        }
                    ) or site_written
                    if status == "downloaded":
                        added += 1
                if sleep_seconds:
                    time.sleep(sleep_seconds)
            if not site_written:
                marker_status = "processed_specs_only" if skip_image_downloads else ("processed_no_logo" if download_logos_only else "processed_no_asset")
                marker_notes = (
                    "Official page was fetched for text/spec extraction; image download is intentionally paused."
                    if skip_image_downloads
                    else (
                        "Official page was fetched, but no downloadable logo candidate or fetch error row was created."
                        if download_logos_only
                        else "Official page was fetched, but no downloadable logo/product image candidate or fetch error row was created."
                    )
                )
                write_asset(
                    marker_asset_row(
                        website,
                        pages[0],
                        captured_at,
                        marker_status,
                        marker_notes,
                    )
                )
    finally:
        sink.close()
    return sink.count, list(page_specs.values())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit-websites", type=int, default=80)
    parser.add_argument("--limit-companies", type=int, default=None, help="Deprecated alias for --limit-websites.")
    parser.add_argument("--max-images-per-site", type=int, default=3)
    parser.add_argument("--max-images-per-company", type=int, default=None, help="Deprecated alias for --max-images-per-site.")
    parser.add_argument("--max-pages-per-site", type=int, default=2)
    parser.add_argument("--max-page-fetches", type=int, default=20)
    parser.add_argument("--force-assets", action="store_true", help="Retry websites that already have asset index rows.")
    parser.add_argument(
        "--skip-image-downloads",
        action="store_true",
        help="Fetch official pages and extract product specifications, but do not download logo/product images.",
    )
    parser.add_argument(
        "--download-logos-only",
        action="store_true",
        help="Fetch official pages and download only logo candidates; product images stay paused.",
    )
    parser.add_argument("--timeout", type=int, default=12)
    parser.add_argument("--sleep", type=float, default=0.03)
    args = parser.parse_args()

    if args.limit_companies is not None:
        args.limit_websites = args.limit_companies
    if args.max_images_per_company is not None:
        args.max_images_per_site = args.max_images_per_company

    evidence = read_official_evidence()
    websites = build_website_master(evidence)
    company_view = build_company_website_view(websites)
    excerpt_specs = build_specs_from_evidence(evidence, websites)

    write_csv(OFFICIAL_WEBSITE_MASTER_PATH, websites, WEBSITE_FIELDS)
    write_csv(COMPANY_OFFICIAL_WEBSITE_PATH, company_view, COMPANY_WEBSITE_FIELDS)
    asset_rows, page_specs = build_assets_and_page_specs(
        websites,
        args.limit_websites,
        args.timeout,
        args.max_images_per_site,
        args.max_pages_per_site,
        args.max_page_fetches,
        args.sleep,
        args.force_assets,
        args.skip_image_downloads,
        args.download_logos_only,
    )
    spec_by_id = {
        norm(row.get("spec_id")): row
        for row in read_csv(PRODUCT_SPECIFICATION_EVIDENCE_PATH)
        if norm(row.get("spec_id")) and spec_value_matches_product_context(row, row.get("spec_value"))
    }
    for row in excerpt_specs:
        spec_by_id[row["spec_id"]] = row
    for row in page_specs:
        spec_by_id[row["spec_id"]] = row
    specs = sorted(spec_by_id.values(), key=lambda row: (norm(row.get("company")), norm(row.get("brand")), norm(row.get("product_family")), norm(row.get("spec_category"))))
    write_csv(PRODUCT_SPECIFICATION_EVIDENCE_PATH, specs, SPEC_FIELDS)

    downloaded = 0
    if COMPANY_MEDIA_ASSET_INDEX_PATH.exists():
        with COMPANY_MEDIA_ASSET_INDEX_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            downloaded = sum(1 for row in csv.DictReader(handle) if row.get("review_status") == "downloaded")
    print(
        json.dumps(
            {
                "official_website_master_rows": len(websites),
                "company_official_website_rows": len(company_view),
                "asset_rows": asset_rows,
                "downloaded_assets": downloaded,
                "image_downloads_paused": args.skip_image_downloads,
                "download_logos_only": args.download_logos_only,
                "product_specification_rows": len(specs),
                "asset_root": str(ASSET_ROOT),
                "website_master_path": str(OFFICIAL_WEBSITE_MASTER_PATH),
                "company_website_path": str(COMPANY_OFFICIAL_WEBSITE_PATH),
                "asset_index_path": str(COMPANY_MEDIA_ASSET_INDEX_PATH),
                "product_specification_path": str(PRODUCT_SPECIFICATION_EVIDENCE_PATH),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
