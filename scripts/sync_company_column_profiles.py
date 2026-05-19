"""Build company profile data for the dashboard.

This bridges the A-to-Z company-column workflow in briefing_v6 with the
dashboard. It reads structured caches and local assets, then writes a compact
browser data file used by company profile pages.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import csv
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
DB_PATH = DATA_DIR / "global_aesthetics.db"
OUT_JSON = DATA_DIR / "company_profiles_bridge.json"
OUT_JS = WEB_DIR / "company-profiles-data.js"
ASSET_OUT = WEB_DIR / "assets" / "company_profiles"
COMPANY_LOGO_MANIFEST = DATA_DIR / "company_logo_manifest.csv"

BRIEFING_ROOT = Path("E:/shared/code/briefing_v6")
BRIEFING_DATA = BRIEFING_ROOT / "data"
BRIEFING_ASSETS = BRIEFING_ROOT / "assets" / "company_column"

LOCAL_COMPANY_IMAGE_DIRS = {
    "Skin Tech": Path("E:/shared/Downloads/Skin Tech Proposal"),
}


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return re.sub(r"\s+", " ", text)


def url_slug(value: str) -> str:
    text = clean_text(value).lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "company"


def file_slug(value: str) -> str:
    text = clean_text(value)
    text = re.sub(r"[^A-Za-z0-9]+", "_", text)
    return text.strip("_") or "Company"


def norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean_text(value).lower())


def rel_web_path(path: Path) -> str:
    return "./" + path.relative_to(WEB_DIR).as_posix()


def write_text_lf(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def copy_asset(src: Path, company_slug: str) -> str:
    dest_dir = ASSET_OUT / company_slug
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", src.name)
    dest = dest_dir / safe_name
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copy2(src, dest)
    return rel_web_path(dest)


def collect_assets(company: str, cache_stem: str) -> dict[str, list[str]]:
    company_slug = url_slug(company)
    image_exts = {".png", ".jpg", ".jpeg", ".webp"}
    media = {"covers": [], "products": [], "references": []}

    for folder_name, bucket, limit in [
        ("covers", "covers", 3),
        ("products", "products", 10),
        ("references", "references", 3),
    ]:
        folder = BRIEFING_ASSETS / folder_name
        if not folder.exists():
            continue
        matches = [
            path
            for path in folder.iterdir()
            if path.is_file()
            and path.suffix.lower() in image_exts
            and (cache_stem.lower() in path.stem.lower() or file_slug(company).lower() in path.stem.lower())
        ]
        for path in sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            media[bucket].append(copy_asset(path, company_slug))

    local_folder = LOCAL_COMPANY_IMAGE_DIRS.get(company)
    if local_folder and local_folder.exists():
        local_matches = [p for p in local_folder.iterdir() if p.is_file() and p.suffix.lower() in image_exts]
        for path in sorted(local_matches)[:8]:
            media["products"].append(copy_asset(path, company_slug))

    for key in media:
        seen = set()
        unique = []
        for item in media[key]:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        media[key] = unique
    return media


def load_briefing_state() -> tuple[dict[str, list[str]], dict[str, str]]:
    state = read_json(BRIEFING_DATA / "company_column_state.json", {})
    by_company: dict[str, list[str]] = defaultdict(list)
    db_by_company: dict[str, str] = {}
    for date, item in (state.get("date_to_company") or {}).items():
        company = clean_text(item.get("company"))
        if not company:
            continue
        by_company[company].append(date)
        if item.get("db_path"):
            db_by_company[company] = item["db_path"]
    return dict(by_company), db_by_company


def load_briefing_caches() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, str]]:
    caches: dict[str, dict[str, Any]] = {}
    suggestions: dict[str, dict[str, Any]] = {}
    stems: dict[str, str] = {}

    cache_dir = BRIEFING_DATA / "company_research_cache"
    if cache_dir.exists():
        for path in cache_dir.glob("*.json"):
            payload = read_json(path, {})
            company = clean_text(payload.get("company") or payload.get("database_snapshot", {}).get("company"))
            if company:
                caches[norm_key(company)] = payload
                stems[norm_key(company)] = path.stem

    suggestion_dir = BRIEFING_DATA / "company_database_suggestions"
    if suggestion_dir.exists():
        for path in suggestion_dir.glob("*.json"):
            payload = read_json(path, {})
            company = clean_text(payload.get("company"))
            if company:
                suggestions[norm_key(company)] = payload
                stems.setdefault(norm_key(company), path.stem)

    return caches, suggestions, stems


def load_logo_manifest() -> dict[str, str]:
    logos: dict[str, str] = {}
    for row in read_csv(COMPANY_LOGO_MANIFEST):
        company = clean_text(row.get("company"))
        web_path = clean_text(row.get("web_path"))
        if clean_text(row.get("status")) == "ok" and company and web_path:
            logos[norm_key(company)] = web_path
    return logos


def load_dashboard_companies() -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        companies = [dict(row) for row in conn.execute("SELECT * FROM companies ORDER BY company").fetchall()]
        products_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in conn.execute("SELECT * FROM products ORDER BY company, brand, core_product").fetchall():
            item = dict(row)
            company = clean_text(item.get("company"))
            if company:
                products_by_company[company].append(item)
    finally:
        conn.close()
    return companies, dict(products_by_company)


def product_summary(products: list[dict[str, Any]]) -> dict[str, Any]:
    tracks = Counter(clean_text(p.get("category_l1")) or "Unknown" for p in products)
    forms = Counter(clean_text(p.get("category_l2")) or "Unknown" for p in products)
    techs = Counter(clean_text(p.get("tech_type_std")) or "Unknown" for p in products)
    brands = Counter(clean_text(p.get("brand")) for p in products if clean_text(p.get("brand")))
    return {
        "tracks": tracks.most_common(),
        "forms": forms.most_common(24),
        "technologies": techs.most_common(24),
        "brand_count": len(brands),
    }


def format_intro(company: dict[str, Any], products: list[dict[str, Any]]) -> dict[str, str]:
    name = clean_text(company.get("company"))
    location = clean_text(company.get("location_full") or company.get("hq_country") or company.get("region"))
    role = clean_text(company.get("business_role")) or "company"
    ownership = clean_text(company.get("ownership"))
    track = clean_text(company.get("primary_track")) or "aesthetic medicine"
    count = len(products)
    zh_bits = [name]
    if location:
        zh_bits.append(f"位于 {location}")
    if ownership:
        zh_bits.append(f"{ownership} 企业")
    if role:
        zh_bits.append(f"业务角色为 {role}")
    intro_zh = "，".join(zh_bits) + f"。当前库内记录 {count} 条产品线，主赛道为 {track}。"
    intro_en = f"{name} is tracked as a {ownership or 'profiled'} {role.lower()} in {location or 'the global aesthetics database'}, with {count} product lines currently mapped under {track}."
    return {"zh": intro_zh, "en": intro_en}


def build_profile(
    company: dict[str, Any],
    products: list[dict[str, Any]],
    schedule: dict[str, list[str]],
    db_paths: dict[str, str],
    caches: dict[str, dict[str, Any]],
    suggestions: dict[str, dict[str, Any]],
    stems: dict[str, str],
    logos: dict[str, str],
) -> dict[str, Any]:
    name = clean_text(company.get("company"))
    key = norm_key(name)
    cache = caches.get(key, {})
    snapshot = cache.get("database_snapshot") or {}
    suggestion = suggestions.get(key, {})
    suggestion_items = suggestion.get("suggestions") or []
    cache_stem = stems.get(key) or file_slug(name)
    source_count = len(cache.get("sources") or [])
    high_suggestions = sum(1 for item in suggestion_items if clean_text(item.get("confidence")).lower() == "high")
    media = collect_assets(name, cache_stem)
    media["logo"] = logos.get(key, "")
    summary = product_summary(products)
    profile_company = {**company}
    for field in ["country", "region", "location", "ownership", "business_role", "status", "parent_company", "stock_code", "primary_track"]:
        value = snapshot.get(field)
        if value and not clean_text(profile_company.get(field)):
            profile_company[field] = value
    intro = format_intro(profile_company, products)
    product_rows = []
    for product in products:
        product_rows.append(
            {
                "record_id": product.get("record_id"),
                "brand": clean_text(product.get("brand")),
                "core_product": clean_text(product.get("core_product")),
                "category_l1": clean_text(product.get("category_l1")),
                "category_l2": clean_text(product.get("category_l2")),
                "tech_type_std": clean_text(product.get("tech_type_std")),
                "introduction": clean_text(product.get("introduction")),
                "ce_status": clean_text(product.get("ce_status")),
                "fda_510k_number": clean_text(product.get("fda_510k_number")),
            }
        )
    first_letter = (name[:1] or "#").upper()
    if not first_letter.isalpha():
        first_letter = "#"
    return {
        "slug": url_slug(name),
        "letter": first_letter,
        "company": name,
        "country": clean_text(company.get("hq_country") or snapshot.get("country") or snapshot.get("location")),
        "region": clean_text(company.get("region") or snapshot.get("region")),
        "location": clean_text(company.get("location_full") or snapshot.get("location")),
        "ownership": clean_text(company.get("ownership") or snapshot.get("ownership")),
        "business_role": clean_text(company.get("business_role") or snapshot.get("business_role")),
        "status": clean_text(company.get("status") or snapshot.get("status")),
        "parent_company": clean_text(company.get("parent_company") or snapshot.get("parent_company")),
        "stock_code": clean_text(company.get("stock_code") or snapshot.get("stock_code")),
        "primary_track": clean_text(company.get("primary_track") or snapshot.get("primary_track")),
        "product_count": len(products),
        "brand_count": summary["brand_count"],
        "briefing_dates": sorted(schedule.get(name, [])),
        "briefing_ready": bool(cache),
        "briefing_db_path": db_paths.get(name, ""),
        "source_count": source_count,
        "suggestion_count": len(suggestion_items),
        "high_confidence_suggestions": high_suggestions,
        "portfolio_complex": len(products) >= 8 or summary["brand_count"] >= 8 or len(summary["tracks"]) >= 2,
        "intro": intro,
        "media": media,
        "summary": summary,
        "products": product_rows,
    }


def main() -> None:
    schedule, db_paths = load_briefing_state()
    caches, suggestions, stems = load_briefing_caches()
    logos = load_logo_manifest()
    companies, products_by_company = load_dashboard_companies()

    profiles = [
        build_profile(company, products_by_company.get(clean_text(company.get("company")), []), schedule, db_paths, caches, suggestions, stems, logos)
        for company in companies
        if clean_text(company.get("company"))
    ]
    profiles.sort(key=lambda item: (item["company"].lower(), item["slug"]))

    letter_groups: dict[str, int] = Counter(item["letter"] if item["letter"].isalpha() else "#" for item in profiles)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": {
            "dashboard_db": str(DB_PATH),
            "briefing_root": str(BRIEFING_ROOT),
            "company_logo_manifest": str(COMPANY_LOGO_MANIFEST),
        },
        "summary": {
            "companies": len(profiles),
            "briefing_ready": sum(1 for item in profiles if item["briefing_ready"]),
            "with_images": sum(1 for item in profiles if item["media"]["covers"] or item["media"]["products"]),
            "with_logos": sum(1 for item in profiles if item["media"].get("logo")),
            "complex_portfolios": sum(1 for item in profiles if item["portfolio_complex"]),
        },
        "letters": dict(sorted(letter_groups.items())),
        "companies": profiles,
    }

    write_text_lf(OUT_JSON, json.dumps(payload, ensure_ascii=False, indent=2))
    write_text_lf(
        OUT_JS,
        "window.COMPANY_PROFILE_DATA = "
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
    )
    print(f"company profiles: {len(profiles)}")
    print(f"briefing-ready: {payload['summary']['briefing_ready']}")
    print(f"with images: {payload['summary']['with_images']}")
    print(f"with logos: {payload['summary']['with_logos']}")
    print(f"wrote: {OUT_JSON}")
    print(f"wrote: {OUT_JS}")


if __name__ == "__main__":
    main()
